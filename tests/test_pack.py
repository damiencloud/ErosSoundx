import unittest
import os
import uuid
import tempfile
import json
import zipfile
from src.database.sqlite_db import (
    init_db, create_soundboard, add_sound, get_sounds, get_db_connection,
    create_macro, add_macro_step, get_macro_steps
)
from src.pack_manager import PackManager

class TestSoundPackManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.user_id = "test_user_pack"
        
        # Clean database records for test users to ensure test isolation
        with get_db_connection() as conn:
            conn.execute("DELETE FROM macro_steps WHERE macro_id IN (SELECT id FROM macros WHERE user_id IN (?, 'guest_user'))", (self.user_id,))
            conn.execute("DELETE FROM macros WHERE user_id IN (?, 'guest_user')", (self.user_id,))
            conn.execute("DELETE FROM sounds WHERE user_id IN (?, 'guest_user')", (self.user_id,))
            conn.execute("DELETE FROM soundboards WHERE user_id IN (?, 'guest_user')", (self.user_id,))
            conn.commit()

        self.sb_id = str(uuid.uuid4())
        self.sound_id = str(uuid.uuid4())
        
        # Create soundboard & sound
        create_soundboard(self.sb_id, self.user_id, "Export Board")
        
        # Create dummy sound file
        self.temp_sound_dir = tempfile.mkdtemp()
        self.dummy_sound_path = os.path.join(self.temp_sound_dir, "beep.wav")
        with open(self.dummy_sound_path, "wb") as f:
            # simple 1-byte file to simulate audio file
            f.write(b"\0")
            
        add_sound(
            sound_id=self.sound_id,
            soundboard_id=self.sb_id,
            user_id=self.user_id,
            name="Beep Sound",
            file_path=self.dummy_sound_path,
            volume=0.8,
            duration=0.5
        )

        # Create macro linking to this sound
        self.macro_id = str(uuid.uuid4())
        create_macro(self.macro_id, self.user_id, "Linked Macro")
        add_macro_step(
            step_id=str(uuid.uuid4()),
            macro_id=self.macro_id,
            position=0,
            action_type="play",
            sound_id=self.sound_id,
            delay_seconds=None
        )

        # Create a temp file path for export pack
        self.temp_pack_fd, self.temp_pack_path = tempfile.mkstemp(suffix=".sbx")
        os.close(self.temp_pack_fd)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_sound_dir, ignore_errors=True)
        if os.path.exists(self.temp_pack_path):
            os.remove(self.temp_pack_path)

    def test_export_and_import_pack(self):
        # 1. Export package
        success = PackManager.export_pack(self.sb_id, self.temp_pack_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.temp_pack_path))

        # Check inside zip file structure
        with zipfile.ZipFile(self.temp_pack_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertIn("sounds/beep.wav", namelist)

            # Read manifest
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["format_version"], "1.0")
            self.assertEqual(manifest["soundboard"]["name"], "Export Board")
            self.assertEqual(len(manifest["sounds"]), 1)
            self.assertEqual(manifest["sounds"][0]["name"], "Beep Sound")
            self.assertEqual(len(manifest["macros"]), 1)
            self.assertEqual(manifest["macros"][0]["name"], "Linked Macro")

        # 2. Import package (simulating a clean import on a different or same user)
        # We verify that a new soundboard, new sound, and new macro are created with new UUIDs
        from unittest.mock import patch
        with patch("src.auth.auth_manager.get_user_id", return_value=self.user_id):
            success = PackManager.import_pack(self.temp_pack_path)
        self.assertTrue(success)

        # Check that we have the new imported soundboard
        with get_db_connection() as conn:
            all_sbs = conn.execute("SELECT id, user_id, name FROM soundboards").fetchall()
            print("ALL SOUNDBOARDS IN DB:", [dict(r) for r in all_sbs])
            imported_sb = conn.execute(
                "SELECT id, name FROM soundboards WHERE user_id = ? AND name = ?", 
                (self.user_id, "Export Board (Imported)")
            ).fetchone()
            self.assertIsNotNone(imported_sb)
            new_sb_id = imported_sb["id"]
            
            # Check sound
            imported_sound = conn.execute(
                "SELECT id, name, file_path FROM sounds WHERE soundboard_id = ?",
                (new_sb_id,)
            ).fetchone()
            self.assertIsNotNone(imported_sound)
            self.assertEqual(imported_sound["name"], "Beep Sound")
            # Verify file actually exists in local cache
            self.assertTrue(os.path.exists(imported_sound["file_path"]))

            # Check macro
            imported_macro = conn.execute(
                "SELECT id, name FROM macros WHERE user_id = ? AND name = ?",
                (self.user_id, "Linked Macro (Imported)")
            ).fetchone()
            self.assertIsNotNone(imported_macro)
            
            # Check macro step maps to the new sound UUID!
            steps = get_macro_steps(imported_macro["id"])
            self.assertEqual(len(steps), 1)
            self.assertEqual(steps[0]["sound_id"], imported_sound["id"])
            self.assertNotEqual(steps[0]["sound_id"], self.sound_id) # must be mapped to new sound ID

if __name__ == "__main__":
    unittest.main()
