import unittest
import os
import tempfile
import time
from src.audio.audio_engine import audio_engine

class TestAudioEngine(unittest.TestCase):
    def test_master_volume_limits(self):
        # Test default volume
        self.assertGreaterEqual(audio_engine.master_volume, 0.0)
        self.assertLessEqual(audio_engine.master_volume, 2.0)

        # Set and test valid master volume
        audio_engine.set_master_volume(0.5)
        self.assertEqual(audio_engine.master_volume, 0.5)

        # Set volume exceeding limits
        audio_engine.set_master_volume(1.5)  # Max master limit is 1.0
        self.assertEqual(audio_engine.master_volume, 1.0)

        audio_engine.set_master_volume(-0.5)  # Min is 0.0
        self.assertEqual(audio_engine.master_volume, 0.0)

    def test_play_missing_file(self):
        # Attempting to play non-existent file should fail gracefully
        success = audio_engine.play_sound("dummy-id", "non_existent_file.mp3")
        self.assertFalse(success)

    def test_audio_playback_logic(self):
        # Generate a temporary valid silent wave file to test loader integration
        # (This is only executable if pygame.mixer is fully initialized)
        import pygame
        if not pygame.mixer.get_init():
            self.skipTest("Pygame audio mixer is not initialized on this platform.")

        # Create a simple 1-second silent WAV file byte payload
        # RIFF header, format chunk, data chunk for 44100Hz, 16bit, mono, silence
        sample_rate = 44100
        duration = 0.5
        num_samples = int(sample_rate * duration)
        
        # WAV file header block
        byte_data = bytearray()
        byte_data.extend(b'RIFF')
        byte_data.extend((36 + num_samples * 2).to_bytes(4, 'little'))
        byte_data.extend(b'WAVEfmt ')
        byte_data.extend((16).to_bytes(4, 'little')) # Subchunk1Size
        byte_data.extend((1).to_bytes(2, 'little'))   # AudioFormat (PCM)
        byte_data.extend((1).to_bytes(2, 'little'))   # NumChannels (1)
        byte_data.extend(sample_rate.to_bytes(4, 'little'))
        byte_data.extend((sample_rate * 2).to_bytes(4, 'little')) # ByteRate
        byte_data.extend((2).to_bytes(2, 'little'))   # BlockAlign
        byte_data.extend((16).to_bytes(2, 'little'))  # BitsPerSample
        byte_data.extend(b'data')
        byte_data.extend((num_samples * 2).to_bytes(4, 'little'))
        byte_data.extend(b'\x00' * (num_samples * 2))  # Silence samples

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(byte_data)
            temp_file_path = f.name

        try:
            # Play the sound
            sound_id = "test-sound-1"
            success = audio_engine.play_sound(sound_id, temp_file_path, volume=0.8)
            self.assertTrue(success)
            
            # Check is_playing flag
            self.assertTrue(audio_engine.is_playing(sound_id))
            
            # Test individual sound volume change
            audio_engine.set_sound_volume(sound_id, 0.5)
            # Find the active channel record
            active_channels = audio_engine.active_channels.get(sound_id, [])
            self.assertEqual(len(active_channels), 1)
            self.assertEqual(active_channels[0]["individual_volume"], 0.5)
            
            # Test master volume adjustment
            audio_engine.set_master_volume(0.6)
            self.assertEqual(audio_engine.master_volume, 0.6)
            
            # Stop the sound
            audio_engine.stop_sound(sound_id)
            self.assertFalse(audio_engine.is_playing(sound_id))

        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def test_device_listing_and_defaults(self):
        from src.config import config_manager
        # Verify that get_available_devices returns a list
        devices = audio_engine.get_available_devices()
        self.assertIsInstance(devices, list)
        
        # Verify that get_available_microphones returns a list
        mics = audio_engine.get_available_microphones()
        self.assertIsInstance(mics, list)
        
        # Verify default config settings
        self.assertEqual(config_manager.get("primary_audio_device"), "Default")
        self.assertFalse(config_manager.get("virtual_mic_enabled"))
        self.assertEqual(config_manager.get("virtual_mic_device"), "")
        self.assertEqual(config_manager.get("mic_device"), "Default")
        self.assertEqual(config_manager.get("mic_volume"), 1.0)
        self.assertFalse(config_manager.get("mic_muted"))
        self.assertEqual(config_manager.get("soundboard_playback_volume"), 1.0)
        self.assertFalse(config_manager.get("soundboard_muted"))

if __name__ == "__main__":
    unittest.main()

