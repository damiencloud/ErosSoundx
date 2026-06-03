import unittest
from src.audio.hotkeys import hotkey_manager, normalize_hotkey

class TestHotkeyEngine(unittest.TestCase):
    def setUp(self):
        hotkey_manager.clear()

    def tearDown(self):
        hotkey_manager.clear()

    def test_normalize_hotkey(self):
        # Modifier and standard keys
        self.assertEqual(normalize_hotkey("Ctrl+Alt+A"), "<ctrl>+<alt>+a")
        self.assertEqual(normalize_hotkey("ctrl+shift+b"), "<ctrl>+<shift>+b")
        
        # F-keys normalization
        self.assertEqual(normalize_hotkey("Ctrl+Shift+F12"), "<ctrl>+<shift>+<f12>")
        self.assertEqual(normalize_hotkey("f5"), "<f5>")

        # Special keys normalization
        self.assertEqual(normalize_hotkey("Alt+Space"), "<alt>+<space>")
        self.assertEqual(normalize_hotkey("Escape"), "<esc>")

        # Empty inputs
        self.assertEqual(normalize_hotkey(""), "")
        self.assertEqual(normalize_hotkey("   "), "")

    def test_register_and_unregister(self):
        # Register a hotkey
        hotkey_manager.register(
            sound_id="sound-1",
            file_path="cache/beep.wav",
            volume=0.8,
            hotkey_str="Ctrl+Alt+S",
            sound_name="Beep Sound"
        )
        
        self.assertIn("sound-1", hotkey_manager.raw_hotkeys)
        self.assertIn("<ctrl>+<alt>+s", hotkey_manager.bindings)
        self.assertEqual(hotkey_manager.raw_hotkeys["sound-1"], "Ctrl+Alt+S")

        # Unregister the hotkey
        hotkey_manager.unregister("sound-1")
        self.assertNotIn("sound-1", hotkey_manager.raw_hotkeys)
        self.assertNotIn("<ctrl>+<alt>+s", hotkey_manager.bindings)

    def test_conflict_detection(self):
        # Register initial key
        hotkey_manager.register(
            sound_id="sound-a",
            file_path="cache/a.mp3",
            volume=1.0,
            hotkey_str="Ctrl+Shift+D",
            sound_name="Sound A"
        )

        # Check conflict with exact same key string (different sound)
        conflict_id = hotkey_manager.check_conflict("Ctrl+Shift+D", ignore_sound_id="sound-b")
        self.assertEqual(conflict_id, "sound-a")

        # Check conflict with case-insensitive / alternate spacing key string
        conflict_id_alt = hotkey_manager.check_conflict("  ctrl + shift + d  ", ignore_sound_id="sound-b")
        self.assertEqual(conflict_id_alt, "sound-a")

        # Check conflict ignoring the registered sound itself (e.g. updating same sound)
        conflict_self = hotkey_manager.check_conflict("Ctrl+Shift+D", ignore_sound_id="sound-a")
        self.assertEqual(conflict_self, "")

        # Check conflict for a non-conflicting key
        no_conflict = hotkey_manager.check_conflict("Ctrl+Shift+E", ignore_sound_id="sound-b")
        self.assertEqual(no_conflict, "")

    def test_validate_hotkey_format(self):
        from src.audio.hotkeys import validate_hotkey_format
        # Valid cases
        self.assertTrue(validate_hotkey_format("Ctrl+Alt+A"))
        self.assertTrue(validate_hotkey_format("f12"))
        self.assertTrue(validate_hotkey_format("Alt+Tab"))
        self.assertTrue(validate_hotkey_format("Shift+x"))

        # Invalid cases
        self.assertFalse(validate_hotkey_format(""))
        self.assertFalse(validate_hotkey_format("Ctrl+Alt+"))
        self.assertFalse(validate_hotkey_format("Ctrl+"))
        self.assertFalse(validate_hotkey_format("+a"))
        self.assertFalse(validate_hotkey_format("Ctrl")) # Just a modifier is invalid
        self.assertFalse(validate_hotkey_format("Alt+Shift")) # Modifiers only

    def test_is_os_reserved(self):
        from src.audio.hotkeys import is_os_reserved
        self.assertTrue(is_os_reserved("Alt+Tab"))
        self.assertTrue(is_os_reserved("Ctrl+Alt+Del"))
        self.assertTrue(is_os_reserved("Win+L"))
        self.assertTrue(is_os_reserved("Alt+F4"))
        
        self.assertFalse(is_os_reserved("Ctrl+Alt+A"))
        self.assertFalse(is_os_reserved("F5"))

    def test_panic_conflict_detection(self):
        from src.config import config_manager
        # Set panic key in config mock-style
        config_manager.set("panic_hotkey", "Ctrl+Shift+K")

        # Now checking a conflict with Ctrl+Shift+K should return "panic"
        conflict = hotkey_manager.check_conflict("Ctrl+Shift+K")
        self.assertEqual(conflict, "panic")

        # Registering sound with Ctrl+Shift+A should not conflict
        hotkey_manager.register("sound-xyz", "some_file.mp3", 1.0, "Ctrl+Shift+A", "Sound XYZ")
        self.assertEqual(hotkey_manager.check_conflict("Ctrl+Shift+A"), "sound-xyz")
        
        # Cleanup config
        config_manager.set("panic_hotkey", "Escape")

if __name__ == "__main__":
    unittest.main()
