import unittest
import os
import sqlite3
from src.database.sqlite_db import (
    get_db_connection, 
    init_db, 
    save_local_session, 
    get_last_local_session, 
    clear_local_sessions,
    DB_PATH
)

class TestSqliteDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize db schema if not already initialized
        init_db()

    def setUp(self):
        # Clear database records prior to each test
        clear_local_sessions()

    def test_database_connection(self):
        # Connection succeeds and returns dict-based rows
        with get_db_connection() as conn:
            row = conn.execute("SELECT 1 as val").fetchone()
            self.assertEqual(row["val"], 1)

    def test_save_and_get_session(self):
        # Save a session
        success = save_local_session(
            user_id="test-uuid-1234",
            email="tester@example.com",
            access_token="fake_access_token",
            refresh_token="fake_refresh_token",
            expires_at=9999999999
        )
        self.assertTrue(success)

        # Retrieve session
        session = get_last_local_session()
        self.assertIsNotNone(session)
        self.assertEqual(session["user_id"], "test-uuid-1234")
        self.assertEqual(session["email"], "tester@example.com")
        self.assertEqual(session["access_token"], "fake_access_token")
        self.assertEqual(session["refresh_token"], "fake_refresh_token")
        self.assertEqual(session["expires_at"], 9999999999)

    def test_clear_session(self):
        # Save session
        save_local_session(
            user_id="test-uuid-5678",
            email="tester2@example.com",
            access_token="tok",
            refresh_token="ref",
            expires_at=12345
        )
        
        # Verify it exists
        self.assertIsNotNone(get_last_local_session())

        # Clear
        clear_local_sessions()

        # Verify it is empty
        self.assertIsNone(get_last_local_session())

if __name__ == "__main__":
    unittest.main()
