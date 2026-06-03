import unittest
import os
import time
from unittest.mock import MagicMock, patch
from src.database import sqlite_db
from src.sync.sync_manager import SyncManager

class TestSyncManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sqlite_db.init_db()

    def setUp(self):
        # Clear tables
        self.user_id = "test-sync-user-123"
        with sqlite_db.get_db_connection() as conn:
            conn.execute("DELETE FROM deleted_records")
            conn.execute("DELETE FROM soundboards")
            conn.execute("DELETE FROM sounds")
            conn.execute("DELETE FROM settings")
            conn.commit()

    def tearDown(self):
        # Cleanup
        with sqlite_db.get_db_connection() as conn:
            conn.execute("DELETE FROM deleted_records")
            conn.execute("DELETE FROM soundboards")
            conn.execute("DELETE FROM sounds")
            conn.execute("DELETE FROM settings")
            conn.commit()

    def test_settings_sqlite_crud(self):
        # Verify initial get is None
        sett = sqlite_db.get_settings(self.user_id)
        self.assertIsNone(sett)

        # Save settings
        success = sqlite_db.save_settings(
            user_id=self.user_id,
            theme="Light",
            master_volume=0.75,
            default_device="Test Device",
            remember_me=1,
            is_synced=0
        )
        self.assertTrue(success)

        # Retrieve and verify
        sett = sqlite_db.get_settings(self.user_id)
        self.assertIsNotNone(sett)
        self.assertEqual(sett["theme"], "Light")
        self.assertEqual(sett["master_volume"], 0.75)
        self.assertEqual(sett["remember_me"], 1)
        self.assertEqual(sett["is_synced"], 0)

    def test_deletion_tombstone_logging(self):
        # Insert a dummy soundboard
        sb_id = "sb-dummy-123"
        sqlite_db.create_soundboard(sb_id, self.user_id, "Test Board")
        
        # Verify it exists
        boards = sqlite_db.get_soundboards(self.user_id)
        self.assertEqual(len(boards), 1)

        # Delete board and verify tombstone is logged
        success = sqlite_db.delete_soundboard(sb_id)
        self.assertTrue(success)

        # Retrieve tombstones
        tombstones = sqlite_db.get_deleted_records(self.user_id)
        self.assertEqual(len(tombstones), 1)
        self.assertEqual(tombstones[0]["id"], sb_id)
        self.assertEqual(tombstones[0]["table_name"], "soundboards")

        # Clear tombstones and verify empty
        clear_success = sqlite_db.clear_deleted_records([sb_id])
        self.assertTrue(clear_success)
        self.assertEqual(len(sqlite_db.get_deleted_records(self.user_id)), 0)

    @patch("src.sync.sync_manager.get_supabase_client")
    @patch("src.sync.sync_manager.test_supabase_connection")
    @patch("src.config.config_manager.get")
    def test_sync_settings_conflict_resolution(self, mock_config_get, mock_conn, mock_get_client):
        mock_conn.return_value = True
        
        # Mock config_manager gets to match local settings values
        def mock_get(key, default=None):
            if key == "theme":
                return "Dark"
            if key == "master_volume":
                return 0.5
            if key == "remember_me":
                return True
            return default
        mock_config_get.side_effect = mock_get
        
        # Mock Supabase responses
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Setup local settings row (older)
        sqlite_db.save_settings(
            user_id=self.user_id,
            theme="Dark",
            master_volume=0.5,
            default_device="",
            remember_me=1,
            is_synced=1,
            updated_at=int(time.time()) - 100
        )
        
        # Setup remote settings row (newer)
        remote_data = [{
            "user_id": self.user_id,
            "theme": "Light",
            "master_volume": 0.8,
            "remember_me": 0,
            "updated_at": int(time.time())
        }]
        
        # Setup Supabase query chain mock
        mock_client.table().select().eq().execute.return_value = MagicMock(data=remote_data)
        
        # Instantiate sync manager and trigger settings sync
        manager = SyncManager()
        
        # We also mock config_manager set to avoid changing real configs
        with patch("src.config.config_manager.set") as mock_set:
            manager._sync_settings(mock_client, self.user_id)
            
            # Since remote was newer, local SQLite settings should have been overwritten
            local_sett = sqlite_db.get_settings(self.user_id)
            self.assertEqual(local_sett["theme"], "Light")
            self.assertEqual(local_sett["master_volume"], 0.8)
            self.assertEqual(local_sett["remember_me"], 0)
            
            # config_manager should have received updates
            mock_set.assert_any_call("theme", "Light")
            mock_set.assert_any_call("master_volume", 0.8)

if __name__ == "__main__":
    unittest.main()
