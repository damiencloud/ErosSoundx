import unittest
import os
import tempfile
from src.database.sqlite_db import init_db
from src.soundboard_manager import soundboard_manager
from src.auth import auth_manager

class TestSoundboardManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Force guest mode for testing CRUD operations locally
        auth_manager.current_user = None
        self.user_id = soundboard_manager.get_effective_user_id()
        
        # Clear existing entries in soundboards
        for board in soundboard_manager.get_boards():
            soundboard_manager.delete_board(board["id"])

    def test_create_and_get_boards(self):
        # Create soundboard
        sb_id = soundboard_manager.create_board("Meme Sounds", "Gaming")
        self.assertNotEqual(sb_id, "")

        # Fetch soundboards
        boards = soundboard_manager.get_boards()
        self.assertEqual(len(boards), 1)
        self.assertEqual(boards[0]["id"], sb_id)
        self.assertEqual(boards[0]["name"], "Meme Sounds")
        self.assertEqual(boards[0]["category"], "Gaming")

    def test_rename_and_categorize_board(self):
        sb_id = soundboard_manager.create_board("Old Name", "Gaming")
        
        # Rename
        success_rename = soundboard_manager.rename_board(sb_id, "New Name")
        self.assertTrue(success_rename)
        
        # Categorize
        success_cat = soundboard_manager.update_board_category(sb_id, "Stream")
        self.assertTrue(success_cat)
        
        # Verify changes
        boards = soundboard_manager.get_boards()
        self.assertEqual(boards[0]["name"], "New Name")
        self.assertEqual(boards[0]["category"], "Stream")

    def test_sound_card_crud_operations(self):
        sb_id = soundboard_manager.create_board("Board A")
        
        # Generate a dummy physical audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            temp_audio_path = f.name

        try:
            # Add sound card (metadata + caching)
            sound_id = soundboard_manager.add_sound_card(
                soundboard_id=sb_id,
                name="Airhorn",
                source_file_path=temp_audio_path,
                hotkey="Ctrl+Alt+A"
            )
            self.assertNotEqual(sound_id, "")

            # Verify local caching worked
            cached_sounds = soundboard_manager.get_board_sounds(sb_id)
            self.assertEqual(len(cached_sounds), 1)
            self.assertEqual(cached_sounds[0]["name"], "Airhorn")
            self.assertEqual(cached_sounds[0]["hotkey"], "Ctrl+Alt+A")
            self.assertTrue(os.path.exists(cached_sounds[0]["file_path"]))

            # Toggle favorite status
            soundboard_manager.toggle_favorite(sound_id, True)
            fav_sounds = soundboard_manager.get_favorites()
            self.assertEqual(len(fav_sounds), 1)
            self.assertEqual(fav_sounds[0]["id"], sound_id)

            # Update details
            soundboard_manager.update_sound_card(sound_id, "Super Airhorn", "Ctrl+Alt+S", 1.5)
            updated = soundboard_manager.get_board_sounds(sb_id)[0]
            self.assertEqual(updated["name"], "Super Airhorn")
            self.assertEqual(updated["hotkey"], "Ctrl+Alt+S")
            self.assertEqual(updated["volume"], 1.5)

            # Delete sound card and ensure cache file is removed
            cached_file_path = updated["file_path"]
            success_del = soundboard_manager.remove_sound_card(sound_id)
            self.assertTrue(success_del)
            self.assertFalse(os.path.exists(cached_file_path))
            self.assertEqual(len(soundboard_manager.get_board_sounds(sb_id)), 0)

        finally:
            # Cleanup temporary source file
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

    def test_cascading_delete_board(self):
        sb_id = soundboard_manager.create_board("Board B")
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"more audio data")
            temp_path = f.name

        try:
            sound_id = soundboard_manager.add_sound_card(sb_id, "Beep", temp_path)
            cached_sound = soundboard_manager.get_board_sounds(sb_id)[0]
            cached_file_path = cached_sound["file_path"]
            self.assertTrue(os.path.exists(cached_file_path))
            
            # Delete Board
            soundboard_manager.delete_board(sb_id)
            
            # Confirm cache file and records are cleared
            self.assertFalse(os.path.exists(cached_file_path))
            self.assertEqual(len(soundboard_manager.get_board_sounds(sb_id)), 0)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_favorite_board(self):
        """
        Verifies that toggle_board_favorite() correctly persists the is_favorite
        flag in SQLite and that the value can be toggled back to 0.
        """
        sb_id = soundboard_manager.create_board("FavTestBoard")
        self.assertNotEqual(sb_id, "")

        # Initially not a favorite
        boards = soundboard_manager.get_boards()
        target = next((b for b in boards if b["id"] == sb_id), None)
        self.assertIsNotNone(target)
        self.assertEqual(target.get("is_favorite", 0), 0)

        # Favorite it
        success = soundboard_manager.toggle_board_favorite(sb_id, True)
        self.assertTrue(success)
        boards = soundboard_manager.get_boards()
        target = next((b for b in boards if b["id"] == sb_id), None)
        self.assertEqual(target["is_favorite"], 1)

        # Unfavorite it
        success = soundboard_manager.toggle_board_favorite(sb_id, False)
        self.assertTrue(success)
        boards = soundboard_manager.get_boards()
        target = next((b for b in boards if b["id"] == sb_id), None)
        self.assertEqual(target["is_favorite"], 0)

    def test_favorite_board_sort_order(self):
        """
        Verifies that get_boards() returns favorited boards at position 0
        and that the remainder is sorted alphabetically.
        """
        # Create three boards with names deliberately out of alphabetical order
        id_a = soundboard_manager.create_board("Alpha")
        id_z = soundboard_manager.create_board("Zeta")
        id_m = soundboard_manager.create_board("Mango")

        self.assertTrue(all([id_a, id_z, id_m]))

        # Favorite "Zeta" – it should jump to position 0
        soundboard_manager.toggle_board_favorite(id_z, True)

        boards = soundboard_manager.get_boards()
        self.assertGreaterEqual(len(boards), 3)

        # The very first board should be the favorited one
        self.assertEqual(boards[0]["id"], id_z)
        self.assertEqual(boards[0]["is_favorite"], 1)

        # The remaining unfavorited boards should be in ascending name order
        unfav = [b for b in boards if b["is_favorite"] == 0]
        unfav_names = [b["name"] for b in unfav]
        self.assertEqual(unfav_names, sorted(unfav_names))


    def _make_wav(self, duration_seconds=2, sample_rate=44100) -> str:
        """
        Helper: writes a minimal valid PCM WAV file to a temp path.
        Returns the absolute file path.
        """
        import struct, wave, tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        num_frames = sample_rate * duration_seconds
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f"<{num_frames}h", *([0] * num_frames)))
        return tmp.name

    def test_sound_duration_stored_on_add(self):
        """
        Verifies that add_sound_card() auto-detects the WAV duration and
        persists it so that get_board_sounds() returns a non-zero duration.
        """
        sb_id = soundboard_manager.create_board("DurationBoard")
        wav_path = self._make_wav(duration_seconds=3)

        try:
            sound_id = soundboard_manager.add_sound_card(sb_id, "Test Tone", wav_path)
            self.assertNotEqual(sound_id, "", "add_sound_card should return a UUID")

            sounds = soundboard_manager.get_board_sounds(sb_id)
            self.assertEqual(len(sounds), 1)

            # Duration should be approximately 3 seconds (within 0.5 s tolerance)
            dur = sounds[0].get("duration", 0.0)
            self.assertGreater(dur, 0.0, "Duration should be non-zero for a valid WAV")
            self.assertAlmostEqual(dur, 3.0, delta=0.5)

            # created_at should be a positive Unix timestamp
            self.assertGreater(sounds[0].get("created_at", 0), 0)
        finally:
            import os
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_rename_sound(self):
        """
        Verifies that rename_sound() updates the sound's display name
        in SQLite and that get_board_sounds() reflects the change.
        """
        sb_id = soundboard_manager.create_board("RenameBoard")
        wav_path = self._make_wav()

        try:
            sound_id = soundboard_manager.add_sound_card(sb_id, "Original Name", wav_path)
            self.assertNotEqual(sound_id, "")

            success = soundboard_manager.rename_sound(sound_id, "Renamed Sound")
            self.assertTrue(success)

            sounds = soundboard_manager.get_board_sounds(sb_id)
            self.assertEqual(sounds[0]["name"], "Renamed Sound")

            # Renaming to an empty string should be rejected
            fail = soundboard_manager.rename_sound(sound_id, "   ")
            self.assertFalse(fail)
        finally:
            import os
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_move_sound_between_boards(self):
        """
        Verifies that move_sound() transfers a sound to a different soundboard:
        - Source board becomes empty
        - Destination board contains the moved sound with its original name intact
        """
        src_id  = soundboard_manager.create_board("Source Board")
        dest_id = soundboard_manager.create_board("Destination Board")
        wav_path = self._make_wav()

        try:
            sound_id = soundboard_manager.add_sound_card(src_id, "Travel Sound", wav_path)
            self.assertNotEqual(sound_id, "")

            # Confirm it starts on the source board
            self.assertEqual(len(soundboard_manager.get_board_sounds(src_id)), 1)
            self.assertEqual(len(soundboard_manager.get_board_sounds(dest_id)), 0)

            success = soundboard_manager.move_sound(sound_id, dest_id)
            self.assertTrue(success)

            # Source board must now be empty
            self.assertEqual(len(soundboard_manager.get_board_sounds(src_id)), 0)

            # Destination board must contain the sound with name intact
            dest_sounds = soundboard_manager.get_board_sounds(dest_id)
            self.assertEqual(len(dest_sounds), 1)
            self.assertEqual(dest_sounds[0]["id"], sound_id)
            self.assertEqual(dest_sounds[0]["name"], "Travel Sound")

            # Moving with an empty ID should fail gracefully
            self.assertFalse(soundboard_manager.move_sound("", dest_id))
            self.assertFalse(soundboard_manager.move_sound(sound_id, ""))
        finally:
            import os
            if os.path.exists(wav_path):
                os.remove(wav_path)

if __name__ == "__main__":
    unittest.main()
