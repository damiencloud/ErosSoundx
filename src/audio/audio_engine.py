import os
import sys
import threading
import time

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'  # Silence pygame support message in stdout
import pygame
from src.logger import logger
from src.config import config_manager

class AudioEngine:
    """
    Engine to manage multi-channel audio playback using pygame.mixer.
    Supports low-latency playbacks, simultaneous sounds, master and individual volumes.
    Also supports multiplexed routing to a Virtual Microphone (VB-CABLE) via a background subprocess.
    Now supports Microphone Passthrough and real-time Audio Mixing via PortAudio/sounddevice.
    """
    def __init__(self):
        self.sound_cache = {}          # Maps file paths to pygame.mixer.Sound objects
        self.active_channels = {}      # Maps sound_id to list of dicts: {"channel": Channel, "individual_volume": float}
        self.master_volume = float(config_manager.get("master_volume", 1.0))
        self.initialized = False
        
        # Subprocess routing state
        self.subprocess_handle = None
        self.virtual_mic_enabled = False
        self.virtual_mic_device = ""
        self.mic_device = "Default"
        
        # Live levels listener callback (UI updates)
        self.level_listener = None

    def register_level_listener(self, callback):
        """
        Registers a callback to receive real-time level and latency updates.
        Callback format: callback(mic_level: float, soundboard_level: float, latency_ms: float)
        """
        self.level_listener = callback

    def get_available_devices(self) -> list:
        """
        Returns a list of all available playback device names.
        """
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            outputs = []
            seen = set()
            for d in devices:
                if d['max_output_channels'] > 0:
                    name = d['name']
                    if name not in seen:
                        seen.add(name)
                        outputs.append(name)
            return outputs
        except Exception as e:
            logger.error(f"Failed to query available audio devices: {e}")
            return []

    def get_available_microphones(self) -> list:
        """
        Returns a list of all available input/microphone device names.
        """
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            mics = []
            seen = set()
            for d in devices:
                if d['max_input_channels'] > 0:
                    name = d['name']
                    if name not in seen:
                        seen.add(name)
                        mics.append(name)
            return mics
        except Exception as e:
            logger.error(f"Failed to query available microphones: {e}")
            return []

    def start_virtual_mic_process(self):
        """
        Spawns the virtual mic background player subprocess if enabled.
        """
        self.stop_virtual_mic_process()
        
        self.virtual_mic_enabled = config_manager.get("virtual_mic_enabled", False)
        self.virtual_mic_device = config_manager.get("virtual_mic_device", "")
        self.mic_device = config_manager.get("mic_device", "Default")
        
        if not self.virtual_mic_enabled or not self.virtual_mic_device:
            logger.debug("Virtual mic routing is disabled or device is empty.")
            return False
            
        logger.info(f"Starting virtual mic player for output: {self.virtual_mic_device}, mic input: {self.mic_device}")
        import subprocess
        
        script_path = os.path.join(os.path.dirname(__file__), "virtual_mic_player.py")
        
        try:
            # Pass both virtual mic device and physical mic device as arguments
            self.subprocess_handle = subprocess.Popen(
                [sys.executable, script_path, self.virtual_mic_device, self.mic_device],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Start stderr logging daemon thread
            threading.Thread(target=self._log_subprocess_output, daemon=True).start()
            
            # Wait for READY signal from subprocess (timeout after 2 seconds)
            ready = False
            line = self.subprocess_handle.stdout.readline()
            if line.strip() == "READY":
                ready = True
                
            if ready:
                logger.info("Virtual mic player subprocess initialized successfully.")
                
                # Send current levels and mute states to initialize the player
                self.send_subprocess_command(f"MASTER_VOLUME|{self.master_volume}")
                self.send_subprocess_command(f"MIC_VOLUME|{config_manager.get('mic_volume', 1.0)}")
                self.send_subprocess_command(f"MIC_MUTE|{'1' if config_manager.get('mic_muted', False) else '0'}")
                self.send_subprocess_command(f"SBD_VOLUME|{config_manager.get('soundboard_playback_volume', 1.0)}")
                self.send_subprocess_command(f"SBD_MUTE|{'1' if config_manager.get('soundboard_muted', False) else '0'}")
                
                # Start stdout listener thread to read levels and latency
                threading.Thread(target=self._read_subprocess_levels, daemon=True).start()
                return True
            else:
                logger.error("Virtual mic player subprocess failed to initialize.")
                self.stop_virtual_mic_process()
                return False
        except Exception as e:
            logger.error(f"Failed to start virtual mic player subprocess: {e}")
            self.subprocess_handle = None
            return False

    def stop_virtual_mic_process(self):
        """
        Gracefully terminates the virtual mic player subprocess.
        """
        if self.subprocess_handle:
            logger.info("Stopping virtual mic player subprocess.")
            try:
                self.send_subprocess_command("QUIT")
                self.subprocess_handle.stdin.close()
                self.subprocess_handle.wait(timeout=1.5)
            except Exception as e:
                logger.debug(f"Error waiting for virtual mic process termination: {e}")
                try:
                    self.subprocess_handle.kill()
                except Exception:
                    pass
            self.subprocess_handle = None

    def reload_virtual_mic(self):
        """
        Reloads (stops and restarts) the virtual mic player subprocess based on new settings.
        """
        self.stop_virtual_mic_process()
        self.start_virtual_mic_process()

    def _log_subprocess_output(self):
        """
        Reads stderr from the virtual mic player subprocess and prints logs.
        """
        proc = self.subprocess_handle
        if not proc:
            return
        while True:
            try:
                line = proc.stderr.readline()
                if not line:
                    break
                logger.error(f"VirtualMicPlayer [stderr]: {line.strip()}")
            except Exception:
                break

    def _read_subprocess_levels(self):
        """
        Reads stdout from the subprocess to receive live levels and latency.
        """
        proc = self.subprocess_handle
        if not proc:
            return
            
        while True:
            try:
                line = proc.stdout.readline()
                if not line:
                    break
                    
                line = line.strip()
                if line.startswith("LEVELS|"):
                    parts = line.split("|")
                    mic_level = float(parts[1])
                    sbd_level = float(parts[2])
                    latency_ms = float(parts[3])
                    
                    if self.level_listener:
                        self.level_listener(mic_level, sbd_level, latency_ms)
            except Exception:
                break

    def send_subprocess_command(self, cmd: str):
        """
        Sends a command string to the subprocess stdin pipe.
        """
        if self.subprocess_handle and self.subprocess_handle.poll() is None:
            try:
                self.subprocess_handle.stdin.write(cmd + "\n")
                self.subprocess_handle.stdin.flush()
            except Exception as e:
                logger.error(f"Failed to write command to virtual mic player: {e}")

    def initialize(self):
        """
        Runs the actual pygame.mixer initialization. Safe to run from background thread.
        """
        if self.initialized:
            return
        
        primary_device = config_manager.get("primary_audio_device", "Default")
        
        try:
            # pre_init parameters optimized for low-latency soundboards
            pygame.mixer.pre_init(44100, -16, 2, 512)
            
            if primary_device and primary_device != "Default":
                logger.info(f"Initializing primary audio device: {primary_device}")
                try:
                    pygame.mixer.init(devicename=primary_device)
                except Exception as e:
                    logger.warning(f"Failed to initialize chosen primary device '{primary_device}': {e}. Falling back to default device.")
                    pygame.mixer.init()
            else:
                logger.info("Initializing primary audio device: Default")
                pygame.mixer.init()
            
            pygame.mixer.set_num_channels(32)
            self.initialized = True
            logger.info("Pygame audio engine mixer initialized with 32 channels.")
            
            # Start virtual mic subprocess
            self.start_virtual_mic_process()
        except Exception as e:
            logger.error(f"Failed to initialize pygame audio mixer: {e}. Audio functions will be disabled.")

    def change_primary_device(self, device_name: str):
        """
        Switches the primary playback device and re-initializes the pygame mixer.
        """
        config_manager.set("primary_audio_device", device_name)
        
        self.stop_all()
        if pygame.mixer.get_init():
            pygame.mixer.quit()
            
        self.sound_cache.clear()
        self.initialized = False
        self.initialize()

    def play_sound(self, sound_id: str, file_path: str, volume: float = 1.0) -> bool:
        """
        Loads and plays a sound file locally.
        Also routes play command to virtual mic player if routing is active.
        """
        if not self.initialized:
            self.initialize()

        self.send_subprocess_command(f"PLAY|{sound_id}|{file_path}|{volume}")

        if not pygame.mixer.get_init():
            logger.error("Audio engine is not initialized locally.")
            return False

        if not os.path.exists(file_path):
            logger.error(f"Cannot play sound locally: audio file not found at: {file_path}")
            return False

        try:
            if file_path not in self.sound_cache:
                self.sound_cache[file_path] = pygame.mixer.Sound(file_path)
                logger.debug(f"Loaded sound into audio engine cache: {file_path}")
                
            sound_obj = self.sound_cache[file_path]

            channel = pygame.mixer.find_channel(force=True)
            if not channel:
                logger.error("No free audio channels available for local playback.")
                return False

            combined_volume = max(0.0, min(1.0, float(volume))) * self.master_volume
            channel.set_volume(combined_volume)
            channel.play(sound_obj)

            if sound_id not in self.active_channels:
                self.active_channels[sound_id] = []
                
            self.active_channels[sound_id] = [c for c in self.active_channels[sound_id] if c["channel"].get_busy()]
            self.active_channels[sound_id].append({
                "channel": channel,
                "individual_volume": float(volume)
            })

            logger.info(f"Triggered audio playback for sound: {sound_id} (volume: {combined_volume:.2f})")
            return True
        except Exception as e:
            logger.error(f"Failed to play audio file locally: {e}")
            return False

    def stop_sound(self, sound_id: str):
        """
        Stops active channels playing the given sound ID locally and on virtual mic.
        """
        self.send_subprocess_command(f"STOP|{sound_id}")
        
        if sound_id in self.active_channels:
            items = list(self.active_channels[sound_id])
            for item in items:
                channel = item["channel"]
                if channel.get_busy():
                    channel.stop()
            self.active_channels[sound_id] = []
            logger.info(f"Stopped playback for sound: {sound_id}")

    def stop_all(self):
        """
        Stops all audio mixer channels locally and on virtual mic.
        """
        self.send_subprocess_command("STOP_ALL")
        
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            self.active_channels.clear()
            logger.info("All local audio playbacks stopped.")

    def set_master_volume(self, volume: float):
        """
        Updates the master volume scaling factor.
        """
        self.master_volume = max(0.0, min(1.0, float(volume)))
        config_manager.set("master_volume", self.master_volume)
        logger.debug(f"Master volume changed to: {self.master_volume:.2f}")

        self.send_subprocess_command(f"MASTER_VOLUME|{self.master_volume}")

        for sound_id, channels in self.active_channels.items():
            self.active_channels[sound_id] = [c for c in channels if c["channel"].get_busy()]
            for item in self.active_channels[sound_id]:
                combined = item["individual_volume"] * self.master_volume
                item["channel"].set_volume(combined)

    def set_sound_volume(self, sound_id: str, volume: float):
        """
        Updates the local volume level of active channels for a specific sound ID.
        """
        volume = max(0.0, min(1.0, float(volume)))
        self.send_subprocess_command(f"VOLUME|{sound_id}|{volume}")
        
        if sound_id in self.active_channels:
            self.active_channels[sound_id] = [c for c in self.active_channels[sound_id] if c["channel"].get_busy()]
            for item in self.active_channels[sound_id]:
                item["individual_volume"] = volume
                combined = volume * self.master_volume
                item["channel"].set_volume(combined)

    def set_mic_volume(self, volume: float):
        """
        Updates physical microphone capture volume in the subprocess.
        """
        volume = max(0.0, min(1.0, float(volume)))
        config_manager.set("mic_volume", volume)
        self.send_subprocess_command(f"MIC_VOLUME|{volume}")

    def set_mic_mute(self, is_muted: bool):
        """
        Mutes/unmutes physical microphone capture in the subprocess.
        """
        config_manager.set("mic_muted", is_muted)
        self.send_subprocess_command(f"MIC_MUTE|{'1' if is_muted else '0'}")

    def set_virtual_mic_sbd_volume(self, volume: float):
        """
        Updates soundboard playback volume routed to the virtual mic.
        """
        volume = max(0.0, min(1.0, float(volume)))
        config_manager.set("soundboard_playback_volume", volume)
        self.send_subprocess_command(f"SBD_VOLUME|{volume}")

    def set_virtual_mic_sbd_mute(self, is_muted: bool):
        """
        Mutes/unmutes soundboard playback routed to the virtual mic.
        """
        config_manager.set("soundboard_muted", is_muted)
        self.send_subprocess_command(f"SBD_MUTE|{'1' if is_muted else '0'}")

    def is_playing(self, sound_id: str) -> bool:
        """
        Checks if a sound is currently playing locally.
        """
        if sound_id in self.active_channels:
            self.active_channels[sound_id] = [c for c in self.active_channels[sound_id] if c["channel"].get_busy()]
            return len(self.active_channels[sound_id]) > 0
        return False

    def generate_test_beep(self, file_path: str) -> bool:
        """
        Generates a 0.3-second 880Hz sine wave WAV file.
        """
        import wave
        import struct
        import math
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        sample_rate = 44100
        duration = 0.3
        frequency = 880.0
        num_samples = int(sample_rate * duration)
        
        try:
            with wave.open(file_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                
                for i in range(num_samples):
                    val = int(16383 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
                    data = struct.pack('<h', val)
                    wav_file.writeframesraw(data)
            logger.debug(f"Generated test beep WAV file at: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate test beep: {e}")
            return False

    def test_device_routing(self) -> bool:
        """
        Plays a programmatically generated test beep.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        test_file = os.path.join(root_dir, "cache", "test_beep.wav")
        
        if not os.path.exists(test_file):
            self.generate_test_beep(test_file)
            
        if os.path.exists(test_file):
            self.play_sound("test-beep-id", test_file, 1.0)
            return True
        return False

# Global audio engine instance
audio_engine = AudioEngine()
