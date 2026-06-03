import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'  # Silence pygame support message in stdout
import pygame
from src.logger import logger
from src.config import config_manager

class AudioEngine:
    """
    Engine to manage multi-channel audio playback using pygame.mixer.
    Supports low-latency playbacks, simultaneous sounds, master and individual volumes.
    """
    def __init__(self):
        self.sound_cache = {}          # Maps file paths to pygame.mixer.Sound objects
        self.active_channels = {}      # Maps sound_id to list of dicts: {"channel": Channel, "individual_volume": float}
        self.master_volume = float(config_manager.get("master_volume", 1.0))
        self.initialized = False

    def initialize(self):
        """
        Runs the actual pygame.mixer initialization. Safe to run from background thread.
        """
        if self.initialized:
            return
        try:
            # pre_init parameters optimized for low-latency desktop soundboards:
            # 44.1kHz, 16-bit signed, stereo, 512 byte buffer (sub-50ms latency)
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            
            # Increase channels pool from default 8 to 32 to support intensive overlaps
            pygame.mixer.set_num_channels(32)
            self.initialized = True
            logger.info("Pygame audio engine mixer initialized with 32 channels.")
        except Exception as e:
            logger.error(f"Failed to initialize pygame audio mixer: {e}. Audio functions will be disabled.")

    def play_sound(self, sound_id: str, file_path: str, volume: float = 1.0) -> bool:
        """
        Loads and plays a sound file on the first free audio channel.
        Applies individual volume scaled by the master volume.
        """
        if not self.initialized:
            self.initialize()

        if not pygame.mixer.get_init():
            logger.error("Audio engine is not initialized.")
            return False

        if not os.path.exists(file_path):
            logger.error(f"Cannot play sound: audio file not found at: {file_path}")
            return False

        try:
            # Load into sound cache if not already cached
            if file_path not in self.sound_cache:
                self.sound_cache[file_path] = pygame.mixer.Sound(file_path)
                logger.debug(f"Loaded sound into audio engine cache: {file_path}")
                
            sound_obj = self.sound_cache[file_path]

            # Find an available mixer channel
            channel = pygame.mixer.find_channel(force=True)  # force=True overrides oldest playing channel if all 32 are busy
            if not channel:
                logger.error("No free audio channels available for playback.")
                return False

            # Set scale (individual volume offset * master volume)
            combined_volume = max(0.0, min(1.0, float(volume))) * self.master_volume
            channel.set_volume(combined_volume)
            
            # Start playing
            channel.play(sound_obj)

            # Register channel tracker
            if sound_id not in self.active_channels:
                self.active_channels[sound_id] = []
                
            # Clean up finished channels before adding the new one
            self.active_channels[sound_id] = [c for c in self.active_channels[sound_id] if c["channel"].get_busy()]
            self.active_channels[sound_id].append({
                "channel": channel,
                "individual_volume": float(volume)
            })

            logger.info(f"Triggered audio playback for sound: {sound_id} (volume: {combined_volume:.2f})")
            return True
        except Exception as e:
            logger.error(f"Failed to play audio file: {e}")
            return False

    def stop_sound(self, sound_id: str):
        """
        Stops all active channels playing the given sound ID.
        """
        if sound_id in self.active_channels:
            # Copy list to iterate safely
            items = list(self.active_channels[sound_id])
            for item in items:
                channel = item["channel"]
                if channel.get_busy():
                    channel.stop()
            self.active_channels[sound_id] = []
            logger.info(f"Stopped playback for sound: {sound_id}")

    def stop_all(self):
        """
        Stops all audio mixer channels immediately.
        """
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            self.active_channels.clear()
            logger.info("All audio playbacks stopped.")

    def set_master_volume(self, volume: float):
        """
        Updates the master volume scaling factor.
        Dynamically adjusts the volume of all active channels playing.
        """
        self.master_volume = max(0.0, min(1.0, float(volume)))
        config_manager.set("master_volume", self.master_volume)
        logger.debug(f"Master volume changed to: {self.master_volume:.2f}")

        # Dynamically scale volume on all active channels
        for sound_id, channels in self.active_channels.items():
            # Clean up finished channels
            self.active_channels[sound_id] = [c for c in channels if c["channel"].get_busy()]
            for item in self.active_channels[sound_id]:
                combined = item["individual_volume"] * self.master_volume
                item["channel"].set_volume(combined)

    def set_sound_volume(self, sound_id: str, volume: float):
        """
        Updates the volume level of active channels for a specific sound ID.
        Allows real-time slider adjustments to reflect immediately.
        """
        volume = max(0.0, min(1.0, float(volume)))
        if sound_id in self.active_channels:
            # Clean up finished channels
            self.active_channels[sound_id] = [c for c in self.active_channels[sound_id] if c["channel"].get_busy()]
            for item in self.active_channels[sound_id]:
                item["individual_volume"] = volume
                combined = volume * self.master_volume
                item["channel"].set_volume(combined)

    def is_playing(self, sound_id: str) -> bool:
        """
        Checks if a sound is currently playing on any active channel.
        """
        if sound_id in self.active_channels:
            # Clean up finished channels
            self.active_channels[sound_id] = [c for c in self.active_channels[sound_id] if c["channel"].get_busy()]
            return len(self.active_channels[sound_id]) > 0
        return False

# Global audio engine instance
audio_engine = AudioEngine()

