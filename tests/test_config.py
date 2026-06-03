import unittest
import os
import json
from src.config import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        # Use a temporary test config file
        self.test_filename = "test_config_temp.json"
        self.manager = ConfigManager(filename=self.test_filename)

    def tearDown(self):
        # Clean up temporary test file
        if os.path.exists(self.manager.filepath):
            try:
                os.remove(self.manager.filepath)
            except OSError:
                pass

    def test_default_values(self):
        # Validate defaults are loaded when file doesn't exist
        self.assertEqual(self.manager.get("theme"), "Dark")
        self.assertEqual(self.manager.get("window_width"), 900)
        self.assertEqual(self.manager.get("remember_me"), True)

    def test_set_and_get(self):
        # Set a custom key
        self.manager.set("theme", "Light")
        self.assertEqual(self.manager.get("theme"), "Light")

        # Set a new key not in defaults
        self.manager.set("custom_key", "custom_value")
        self.assertEqual(self.manager.get("custom_key"), "custom_value")

    def test_persistence(self):
        # Save a setting
        self.manager.set("window_width", 1080)
        
        # Instantiate a new manager with same file to verify file-save read
        new_manager = ConfigManager(filename=self.test_filename)
        self.assertEqual(new_manager.get("window_width"), 1080)

    def test_reset_to_defaults(self):
        self.manager.set("theme", "Light")
        self.manager.reset_to_defaults()
        self.assertEqual(self.manager.get("theme"), "Dark")

if __name__ == "__main__":
    unittest.main()
