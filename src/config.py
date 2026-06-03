import os
import json
from src.logger import logger

class ConfigManager:
    """
    Manages local application configuration stored in config.json.
    """
    def __init__(self, filename="config.json"):
        # Resolve config file path relative to root directory
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filepath = os.path.join(self.root_dir, filename)
        
        self.defaults = {
            "theme": "Dark",            # "Dark", "Light", "System"
            "window_width": 900,
            "window_height": 600,
            "supabase_url": "",
            "supabase_key": "",
            "remember_me": True,
            "last_session": {},          # Caches user profile & session tokens if remember_me is True
            "streamer_mode": False       # Hides sensitive info in UI if True
        }

        self.config = {}
        self.load()

    def load(self):
        """
        Loads the config from disk, falling back to defaults if missing or corrupt.
        """
        if not os.path.exists(self.filepath):
            logger.info("Configuration file not found. Generating default config at: %s", self.filepath)
            self.config = self.defaults.copy()
            self.save()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
                
            # Merge loaded config with defaults to ensure all keys exist
            self.config = self.defaults.copy()
            self.config.update(loaded_config)
            logger.debug("Configuration successfully loaded from: %s", self.filepath)
        except Exception as e:
            logger.error("Failed to load configuration file: %s. Using default configurations.", e)
            self.config = self.defaults.copy()

    def save(self):
        """
        Saves the current configuration to disk.
        """
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            logger.debug("Configuration saved to: %s", self.filepath)
        except Exception as e:
            logger.error("Failed to save configuration file: %s", e)

    def get(self, key, default=None):
        """
        Retrieves a configuration value.
        """
        return self.config.get(key, default if default is not None else self.defaults.get(key))

    def set(self, key, value):
        """
        Sets a configuration value and saves to disk.
        """
        self.config[key] = value
        self.save()

    def reset_to_defaults(self):
        """
        Resets all configurations to default.
        """
        self.config = self.defaults.copy()
        self.save()
        logger.info("Configuration reset to defaults.")

# Instantiate a global settings manager
config_manager = ConfigManager()
