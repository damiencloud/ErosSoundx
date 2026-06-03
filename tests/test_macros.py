import unittest
import os
import time
import uuid
from src.database.sqlite_db import (
    init_db, create_macro, rename_macro, delete_macro,
    get_macros, get_macro_by_id, get_macro_steps,
    clear_macro_steps, add_macro_step, create_soundboard, add_sound
)
from src.macro_manager import macro_manager

class TestSoundMacros(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Setup test IDs
        self.user_id = "test_user_macros"
        self.macro_id = str(uuid.uuid4())
        self.soundboard_id = str(uuid.uuid4())
        self.sound_id = str(uuid.uuid4())

        # Cleanup existing macros for test user
        macros = get_macros(self.user_id)
        for m in macros:
            delete_macro(m["id"])

        # Create dummy soundboard and sound to reference in macros
        create_soundboard(self.soundboard_id, self.user_id, "Test SB")
        add_sound(
            sound_id=self.sound_id,
            soundboard_id=self.soundboard_id,
            user_id=self.user_id,
            name="Beep",
            file_path="tests/assets/dummy_beep.wav",
            volume=0.5
        )

    def test_macro_crud(self):
        # 1. Create macro
        success = create_macro(self.macro_id, self.user_id, "Intro Sound Macro")
        self.assertTrue(success)

        # Verify exists
        macro = get_macro_by_id(self.macro_id)
        self.assertIsNotNone(macro)
        self.assertEqual(macro["name"], "Intro Sound Macro")

        # 2. Rename macro
        success = rename_macro(self.macro_id, "Outro Sound Macro")
        self.assertTrue(success)
        macro = get_macro_by_id(self.macro_id)
        self.assertEqual(macro["name"], "Outro Sound Macro")

        # 3. Add steps
        # Add a play sound step
        step1_id = str(uuid.uuid4())
        success = add_macro_step(
            step_id=step1_id,
            macro_id=self.macro_id,
            position=0,
            action_type="play",
            sound_id=self.sound_id,
            delay_seconds=None
        )
        self.assertTrue(success)

        # Add a delay step
        step2_id = str(uuid.uuid4())
        success = add_macro_step(
            step_id=step2_id,
            macro_id=self.macro_id,
            position=1,
            action_type="delay",
            sound_id=None,
            delay_seconds=1.5
        )
        self.assertTrue(success)

        # Verify steps count and ordering
        steps = get_macro_steps(self.macro_id)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["action_type"], "play")
        self.assertEqual(steps[0]["sound_id"], self.sound_id)
        self.assertEqual(steps[1]["action_type"], "delay")
        self.assertEqual(steps[1]["delay_seconds"], 1.5)

        # 4. Clear steps
        success = clear_macro_steps(self.macro_id)
        self.assertTrue(success)
        steps = get_macro_steps(self.macro_id)
        self.assertEqual(len(steps), 0)

        # 5. Delete macro
        success = delete_macro(self.macro_id)
        self.assertTrue(success)
        macro = get_macro_by_id(self.macro_id)
        self.assertIsNone(macro)

    def test_macro_manager_execution(self):
        # Create a macro with a short delay and verify it runs and is cancelable
        create_macro(self.macro_id, self.user_id, "Manager Test Macro")
        
        # Step 1: Delay 5 seconds (we will cancel it early)
        step_id = str(uuid.uuid4())
        add_macro_step(
            step_id=step_id,
            macro_id=self.macro_id,
            position=0,
            action_type="delay",
            sound_id=None,
            delay_seconds=5.0
        )

        start_time = time.time()
        
        # Trigger play
        success = macro_manager.play_macro(self.macro_id)
        self.assertTrue(success)
        
        # Let it start running briefly
        time.sleep(0.2)
        
        # Verify active runner exists
        self.assertGreater(len(macro_manager.active_runners), 0)

        # Cancel all running macros
        macro_manager.cancel_all()
        
        # Let background thread clean up
        time.sleep(0.2)

        # Verify active runners cleared
        self.assertEqual(len(macro_manager.active_runners), 0)
        
        duration = time.time() - start_time
        # Duration should be less than 2.0s since the 5s delay was cancelled
        self.assertLess(duration, 2.0)

if __name__ == "__main__":
    unittest.main()
