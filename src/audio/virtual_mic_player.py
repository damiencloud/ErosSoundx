import os
import sys
import time
import queue
import threading
import traceback

# Silence pygame support message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import sounddevice as sd
import numpy as np

# Thread-safe queue for stdin commands
command_queue = queue.Queue()

def stdin_reader():
    """
    Reads commands from stdin and pushes them to the command queue.
    """
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            command_queue.put(line.strip())
        except Exception:
            break

class RealTimeMixer:
    def __init__(self, vmic_name, mic_name=None):
        self.vmic_name = vmic_name
        self.mic_name = mic_name
        
        self.active_sounds = []        # List of dicts: {"sound_id": str, "samples": np.ndarray, "index": int, "volume": float}
        self.sound_cache = {}          # Maps file path to float32 np.ndarray of samples
        
        # Volumes and mutes
        self.master_volume = 1.0
        self.mic_volume = 1.0
        self.mic_muted = False
        self.sbd_volume = 1.0
        self.sbd_muted = False
        
        # Live levels (thread-safe, updated in callback, read by main thread)
        self.latest_mic_rms = 0.0
        self.latest_sbd_rms = 0.0
        self.stream_latency_ms = 0.0
        self.lock = threading.Lock()
        
        # Pygame mixer for decoding files (lazy initialized)
        self.decoder_initialized = False

    # find_device_indices removed in favor of robust API-aware resolution in start_stream

    def lazy_init_decoder(self):
        if self.decoder_initialized:
            return
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            self.decoder_initialized = True
        except Exception as e:
            sys.stderr.write(f"DECODER_ERROR:Failed to init pygame decoder: {e}\n")
            sys.stderr.flush()

    def resample_audio(self, samples, orig_rate, target_rate):
        if orig_rate == target_rate:
            return samples
        num_samples = len(samples)
        duration = num_samples / orig_rate
        num_target_samples = int(duration * target_rate)
        
        orig_times = np.linspace(0, duration, num_samples, endpoint=False)
        target_times = np.linspace(0, duration, num_target_samples, endpoint=False)
        
        resampled = np.zeros((num_target_samples, 2), dtype=samples.dtype)
        resampled[:, 0] = np.interp(target_times, orig_times, samples[:, 0])
        resampled[:, 1] = np.interp(target_times, orig_times, samples[:, 1])
        return resampled

    def decode_audio_file(self, file_path):
        """
        Decodes an audio file to raw float32 stereo samples using pygame.
        """
        if file_path in self.sound_cache:
            return self.sound_cache[file_path]
            
        self.lazy_init_decoder()
        
        try:
            sound = pygame.mixer.Sound(file_path)
            raw_bytes = sound.get_raw()
            
            # Convert raw bytes (16-bit signed stereo) to numpy array
            samples = np.frombuffer(raw_bytes, dtype=np.int16)
            
            # Reshape to stereo
            samples = samples.reshape(-1, 2)
            
            # Convert to float32 normalized samples (-1.0 to 1.0)
            float_samples = samples.astype(np.float32) / 32768.0
            
            # Resample to the active stream sample rate if different
            stream_rate = int(self.stream.samplerate) if hasattr(self, 'stream') else 44100
            if stream_rate != 44100:
                float_samples = self.resample_audio(float_samples, 44100, stream_rate)
            
            self.sound_cache[file_path] = float_samples
            return float_samples
        except Exception as e:
            sys.stderr.write(f"DECODE_ERROR:Failed to decode '{file_path}': {e}\n")
            sys.stderr.flush()
            return None

    def audio_callback(self, indata, outdata, frames, time_info, status):
        """
        Full-duplex stream callback: Mixes microphone input and soundboard playbacks.
        """
        # indata has shape (frames, mic_channels)
        # Convert mono microphone input to stereo by duplicating columns
        mic_channels = indata.shape[1]
        if mic_channels == 1:
            mic_mono = indata[:, 0]
            mic_stereo = np.column_stack((mic_mono, mic_mono))
        else:
            mic_stereo = indata[:, :2]  # take first 2 channels if multi-channel

        # Scale microphone input
        scale_mic = self.mic_volume if not self.mic_muted else 0.0
        scaled_mic = mic_stereo * scale_mic

        # Initialize mixed soundboard buffer
        soundboard_mixed = np.zeros((frames, 2), dtype=np.float32)

        # Mix playing sounds
        with self.lock:
            for snd in list(self.active_sounds):
                samples = snd["samples"]
                idx = snd["index"]
                vol = snd["volume"]
                
                avail = len(samples) - idx
                chunk_len = min(frames, avail)
                
                if chunk_len > 0:
                    soundboard_mixed[:chunk_len] += samples[idx : idx + chunk_len] * vol
                    snd["index"] += chunk_len
                    
                if snd["index"] >= len(samples):
                    self.active_sounds.remove(snd)

        # Scale soundboard output
        scale_sbd = self.sbd_volume if not self.sbd_muted else 0.0
        scaled_sbd = soundboard_mixed * scale_sbd

        # Combine microphone and soundboard
        mixed_output = scaled_mic + scaled_sbd

        # Clipping protection: Clamp output to [-1.0, 1.0]
        np.clip(mixed_output, -1.0, 1.0, out=outdata)

        # Calculate live levels (RMS)
        self.latest_mic_rms = float(np.sqrt(np.mean(scaled_mic ** 2))) if scale_mic > 0 else 0.0
        self.latest_sbd_rms = float(np.sqrt(np.mean(scaled_sbd ** 2))) if scale_sbd > 0 else 0.0

    def start_stream(self):
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()

        def name_matches(dev_name, target_name):
            if not target_name:
                return False
            d_low = dev_name.lower()
            t_low = target_name.lower()
            return d_low == t_low or d_low in t_low or t_low in d_low

        # Priority list of Host APIs: WASAPI first for ultra low latency (< 50ms)
        api_priority = ["wasapi", "directsound", "mme"]
        
        # Resolve microphone name
        mic_name_to_use = self.mic_name
        if self.mic_name == "Default":
            try:
                default_idx = sd.default.device[0]
                mic_name_to_use = devices[default_idx]['name']
            except Exception:
                pass

        errors = []
        stream_opened = False

        for api_name in api_priority:
            # Find host API ID by name
            api_id = None
            for i, api in enumerate(host_apis):
                if api_name in api['name'].lower():
                    api_id = i
                    break
            if api_id is None:
                continue

            # Find matching devices on this API
            mic_idx = None
            vmic_idx = None

            for i, d in enumerate(devices):
                if d['hostapi'] == api_id:
                    if mic_idx is None and d['max_input_channels'] > 0 and name_matches(d['name'], mic_name_to_use):
                        mic_idx = i
                    if vmic_idx is None and d['max_output_channels'] > 0 and name_matches(d['name'], self.vmic_name):
                        vmic_idx = i

            # If we don't have mic_name selected or no mic is found, we can do output-only stream on this API
            if not self.mic_name:
                mic_idx = None
            elif mic_idx is None:
                # If a microphone was requested but not found on this API, skip to next API
                continue

            if vmic_idx is None:
                # If virtual mic device not found on this API, skip
                continue

            try:
                vmic_info = sd.query_devices(vmic_idx, 'output')
                srate = int(vmic_info.get('default_samplerate', 44100))

                if mic_idx is not None:
                    mic_info = sd.query_devices(mic_idx, 'input')
                    mic_channels = min(2, mic_info['max_input_channels'])
                    
                    self.stream = sd.Stream(
                        device=(mic_idx, vmic_idx),
                        samplerate=srate,
                        blocksize=256,
                        channels=(mic_channels, 2),
                        dtype='float32',
                        callback=self.audio_callback
                    )
                else:
                    self.stream = sd.OutputStream(
                        device=vmic_idx,
                        samplerate=srate,
                        blocksize=256,
                        channels=2,
                        dtype='float32',
                        callback=self.audio_callback_output_only
                    )
                
                self.stream.start()
                stream_opened = True
                break
            except Exception as e:
                errors.append(f"{api_name.upper()} error: {e}")

        # If all priority APIs failed, try ultimate fallback (original independent search & default device)
        if not stream_opened:
            try:
                # Fallback to independent search (might mix host APIs but is a last resort)
                vmic_idx = None
                for i, d in enumerate(devices):
                    if d['max_output_channels'] > 0 and name_matches(d['name'], self.vmic_name):
                        vmic_idx = i
                        break
                if vmic_idx is None:
                    vmic_idx = sd.default.device[1]

                mic_idx = None
                if self.mic_name and self.mic_name != "Default":
                    for i, d in enumerate(devices):
                        if d['max_input_channels'] > 0 and name_matches(d['name'], self.mic_name):
                            mic_idx = i
                            break
                if self.mic_name == "Default" or (self.mic_name and mic_idx is None):
                    mic_idx = sd.default.device[0]

                vmic_info = sd.query_devices(vmic_idx, 'output')
                srate = int(vmic_info.get('default_samplerate', 44100))

                if mic_idx is not None:
                    mic_info = sd.query_devices(mic_idx, 'input')
                    mic_channels = min(2, mic_info['max_input_channels'])
                    self.stream = sd.Stream(
                        device=(mic_idx, vmic_idx),
                        samplerate=srate,
                        blocksize=256,
                        channels=(mic_channels, 2),
                        dtype='float32',
                        callback=self.audio_callback
                    )
                else:
                    self.stream = sd.OutputStream(
                        device=vmic_idx,
                        samplerate=srate,
                        blocksize=256,
                        channels=2,
                        dtype='float32',
                        callback=self.audio_callback_output_only
                    )
                self.stream.start()
                stream_opened = True
            except Exception as e:
                errors.append(f"Fallback error: {e}")

        if not stream_opened:
            sys.stderr.write(f"INIT_ERROR:Failed to start PortAudio stream. Attempts: {', '.join(errors)}\n")
            sys.stderr.flush()
            return False

        # Retrieve loopback latency in milliseconds
        lat = self.stream.latency
        total_lat = sum(lat) if isinstance(lat, tuple) else lat
        self.stream_latency_ms = total_lat * 1000.0
        return True

    def audio_callback_output_only(self, outdata, frames, time_info, status):
        """
        Output-only stream callback: Mixes soundboard playback only.
        """
        soundboard_mixed = np.zeros((frames, 2), dtype=np.float32)

        with self.lock:
            for snd in list(self.active_sounds):
                samples = snd["samples"]
                idx = snd["index"]
                vol = snd["volume"]
                
                avail = len(samples) - idx
                chunk_len = min(frames, avail)
                
                if chunk_len > 0:
                    soundboard_mixed[:chunk_len] += samples[idx : idx + chunk_len] * vol
                    snd["index"] += chunk_len
                    
                if snd["index"] >= len(samples):
                    self.active_sounds.remove(snd)

        scale_sbd = self.sbd_volume if not self.sbd_muted else 0.0
        scaled_sbd = soundboard_mixed * scale_sbd

        np.clip(scaled_sbd, -1.0, 1.0, out=outdata)
        
        self.latest_mic_rms = 0.0
        self.latest_sbd_rms = float(np.sqrt(np.mean(scaled_sbd ** 2))) if scale_sbd > 0 else 0.0

    def play_sound(self, sound_id, file_path, volume):
        samples = self.decode_audio_file(file_path)
        if samples is None:
            return
            
        with self.lock:
            # Prevent duplication of same sound playing on same channel if needed, or allow layering
            self.active_sounds.append({
                "sound_id": sound_id,
                "samples": samples,
                "index": 0,
                "volume": volume
            })

    def stop_sound(self, sound_id):
        with self.lock:
            self.active_sounds = [s for s in self.active_sounds if s["sound_id"] != sound_id]

    def stop_all(self):
        with self.lock:
            self.active_sounds.clear()

    def close(self):
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        if self.decoder_initialized:
            pygame.mixer.quit()

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("ERROR: Missing target virtual microphone output device name.\n")
        sys.stderr.flush()
        sys.exit(1)
        
    vmic_name = sys.argv[1]
    mic_name = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "" else None
    
    mixer = RealTimeMixer(vmic_name, mic_name)
    if not mixer.start_stream():
        sys.exit(1)
        
    # Send READY signal to stdout
    sys.stdout.write("READY\n")
    sys.stdout.flush()
    
    # Start stdin listener thread
    threading.Thread(target=stdin_reader, daemon=True).start()
    
    last_level_time = time.time()
    
    # Main execution loop
    while True:
        try:
            # Process command queue
            while not command_queue.empty():
                line = command_queue.get_nowait()
                if not line:
                    continue
                    
                parts = line.split("|")
                cmd = parts[0]
                
                if cmd == "PLAY":
                    sound_id = parts[1]
                    file_path = parts[2]
                    volume = float(parts[3])
                    mixer.play_sound(sound_id, file_path, volume)
                    
                elif cmd == "VOLUME":
                    sound_id = parts[1]
                    volume = float(parts[2])
                    with mixer.lock:
                        for snd in mixer.active_sounds:
                            if snd["sound_id"] == sound_id:
                                snd["volume"] = volume

                elif cmd == "STOP":
                    sound_id = parts[1]
                    mixer.stop_sound(sound_id)
                    
                elif cmd == "STOP_ALL":
                    mixer.stop_all()
                    
                elif cmd == "MASTER_VOLUME":
                    mixer.master_volume = float(parts[1])
                    
                elif cmd == "MIC_VOLUME":
                    mixer.mic_volume = float(parts[1])
                    
                elif cmd == "MIC_MUTE":
                    mixer.mic_muted = (parts[1] == "1")
                    
                elif cmd == "SBD_VOLUME":
                    mixer.sbd_volume = float(parts[1])
                    
                elif cmd == "SBD_MUTE":
                    mixer.sbd_muted = (parts[1] == "1")
                    
                elif cmd == "QUIT":
                    mixer.close()
                    sys.exit(0)
                    
            # Periodically report live levels to stdout (every 100ms)
            now = time.time()
            if now - last_level_time >= 0.10:
                # Thread-safe read of levels
                mic_rms = mixer.latest_mic_rms
                sbd_rms = mixer.latest_sbd_rms
                latency = mixer.stream_latency_ms
                
                sys.stdout.write(f"LEVELS|{mic_rms:.5f}|{sbd_rms:.5f}|{latency:.1f}\n")
                sys.stdout.flush()
                last_level_time = now
                
            time.sleep(0.01)  # sleep 10ms to keep CPU low
            
        except SystemExit:
            break
        except Exception as e:
            sys.stderr.write(f"ERROR: {e}\n{traceback.format_exc()}\n")
            sys.stderr.flush()
            time.sleep(1.0)
            
    mixer.close()

if __name__ == "__main__":
    main()
