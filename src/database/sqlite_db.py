import sqlite3
import os
import time
from contextlib import contextmanager
from src.logger import logger

# Database file location
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT_DIR, "eros_soundx.db")

@contextmanager
def get_db_connection():
    """
    Context manager to obtain an SQLite connection and ensure it closes.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys constraint enforcement (disabled by default in SQLite)
    conn.execute("PRAGMA foreign_keys = ON;")
    # Performance PRAGMAs (WAL mode, Normal sync, 2MB Cache)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -2000;")
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite transaction error: {e}")
        raise
    finally:
        conn.close()

def init_db():
    """
    Initializes the local SQLite database schema.
    """
    logger.info("Initializing SQLite database at: %s", DB_PATH)
    
    schema = """
    -- Table to manage local cached login sessions
    CREATE TABLE IF NOT EXISTS local_sessions (
        user_id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        access_token TEXT NOT NULL,
        refresh_token TEXT NOT NULL,
        expires_at INTEGER NOT NULL
    );

    -- Table for soundboards structure
    CREATE TABLE IF NOT EXISTS soundboards (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'General',
        is_favorite INTEGER DEFAULT 0,
        is_synced INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL
    );

    -- Table for sounds structure
    CREATE TABLE IF NOT EXISTS sounds (
        id TEXT PRIMARY KEY,
        soundboard_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        supabase_storage_path TEXT,
        hotkey TEXT,
        volume REAL DEFAULT 1.0,
        duration REAL DEFAULT 0.0,
        is_favorite INTEGER DEFAULT 0,
        is_synced INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY(soundboard_id) REFERENCES soundboards(id) ON DELETE CASCADE
    );

    -- Table for settings structure
    CREATE TABLE IF NOT EXISTS settings (
        user_id TEXT PRIMARY KEY,
        theme TEXT DEFAULT 'Dark',
        master_volume REAL DEFAULT 1.0,
        default_device TEXT,
        remember_me INTEGER DEFAULT 1,
        is_synced INTEGER DEFAULT 0,
        updated_at INTEGER NOT NULL
    );

    -- Table for deleted records tombstones
    CREATE TABLE IF NOT EXISTS deleted_records (
        id TEXT PRIMARY KEY,
        table_name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        deleted_at INTEGER NOT NULL
    );

    -- Table for macros structure
    CREATE TABLE IF NOT EXISTS macros (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        is_synced INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL
    );

    -- Table for macro steps structure
    CREATE TABLE IF NOT EXISTS macro_steps (
        id TEXT PRIMARY KEY,
        macro_id TEXT NOT NULL,
        position INTEGER NOT NULL,
        action_type TEXT NOT NULL, -- 'play' or 'delay'
        sound_id TEXT, -- foreign key to sounds.id (nullable)
        delay_seconds REAL, -- delay in seconds (nullable)
        is_synced INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY(macro_id) REFERENCES macros(id) ON DELETE CASCADE
    );

    -- Performance Indexes
    CREATE INDEX IF NOT EXISTS idx_sounds_sb ON sounds(soundboard_id);
    CREATE INDEX IF NOT EXISTS idx_sounds_fav ON sounds(is_favorite);
    CREATE INDEX IF NOT EXISTS idx_soundboards_usr ON soundboards(user_id);
    CREATE INDEX IF NOT EXISTS idx_macro_steps_macro ON macro_steps(macro_id);
    """
    
    try:
        with get_db_connection() as conn:
            conn.executescript(schema)
            conn.commit()

            # --- MIGRATION: Add is_favorite to soundboards if missing ---
            # Safe to run on every startup; PRAGMA returns column info without side effects.
            existing_cols = [
                row[1] for row in conn.execute("PRAGMA table_info(soundboards);").fetchall()
            ]
            if "is_favorite" not in existing_cols:
                conn.execute(
                    "ALTER TABLE soundboards ADD COLUMN is_favorite INTEGER DEFAULT 0;"
                )
                conn.commit()
                logger.info("Migration applied: soundboards.is_favorite column added.")

            # --- MIGRATION: Add created_at to soundboards if missing ---
            if "created_at" not in existing_cols:
                conn.execute(
                    "ALTER TABLE soundboards ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0;"
                )
                conn.commit()
                logger.info("Migration applied: soundboards.created_at column added.")

            # --- MIGRATIONS: Add duration + created_at to sounds if missing ---
            sound_cols = [
                row[1] for row in conn.execute("PRAGMA table_info(sounds);").fetchall()
            ]
            if "duration" not in sound_cols:
                conn.execute(
                    "ALTER TABLE sounds ADD COLUMN duration REAL DEFAULT 0.0;"
                )
                conn.commit()
                logger.info("Migration applied: sounds.duration column added.")

            if "created_at" not in sound_cols:
                conn.execute(
                    "ALTER TABLE sounds ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0;"
                )
                conn.commit()
                logger.info("Migration applied: sounds.created_at column added.")

        logger.info("SQLite database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        raise

# Local session helpers
def save_local_session(user_id, email, access_token, refresh_token, expires_at):
    """
    Saves or updates a local user session cache.
    """
    query = """
    INSERT OR REPLACE INTO local_sessions (user_id, email, access_token, refresh_token, expires_at)
    VALUES (?, ?, ?, ?, ?)
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query, (user_id, email, access_token, refresh_token, int(expires_at)))
            conn.commit()
        logger.debug("Successfully saved user session locally for: %s", email)
        return True
    except Exception as e:
        logger.error("Failed to save local session in SQLite: %s", e)
        return False

def get_last_local_session():
    """
    Retrieves the most recent local session from the cache.
    """
    query = "SELECT user_id, email, access_token, refresh_token, expires_at FROM local_sessions LIMIT 1"
    try:
        with get_db_connection() as conn:
            row = conn.execute(query).fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error("Failed to query local session from SQLite: %s", e)
        return None

def clear_local_sessions():
    """
    Deletes all records from the local session cache.
    """
    query = "DELETE FROM local_sessions"
    try:
        with get_db_connection() as conn:
            conn.execute(query)
            conn.commit()
        logger.debug("Cleared local session cache.")
        return True
    except Exception as e:
        logger.error("Failed to clear local session cache: %s", e)
        return False

# --- PHASE 2 CRUD OPERATIONS FOR SOUNDBOARDS ---

def create_soundboard(sb_id, user_id, name, category='General'):
    """
    Inserts a new soundboard row. Both created_at and updated_at are set to
    the current Unix timestamp so the record's birth time is preserved.
    """
    now = int(time.time())
    query = """
    INSERT INTO soundboards (id, user_id, name, category, is_favorite, is_synced, created_at, updated_at)
    VALUES (?, ?, ?, ?, 0, 0, ?, ?)
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query, (sb_id, user_id, name, category, now, now))
            conn.commit()
        logger.info(f"Created local soundboard: {name} ({sb_id})")
        return True
    except Exception as e:
        logger.error(f"Failed to create soundboard in SQLite: {e}")
        return False

def get_soundboards(user_id):
    """
    Returns all soundboards for the given user ordered by:
      1. is_favorite DESC  (favorites float to the top)
      2. name ASC          (then alphabetically)
    """
    query = """
    SELECT id, user_id, name, category, is_favorite, is_synced, created_at, updated_at
    FROM soundboards
    WHERE user_id = ?
    ORDER BY is_favorite DESC, name ASC
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (user_id,)).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve soundboards: {e}")
        return []

def rename_soundboard(sb_id, new_name):
    query = "UPDATE soundboards SET name = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (new_name, int(time.time()), sb_id))
            conn.commit()
        logger.info(f"Renamed soundboard {sb_id} to: {new_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to rename soundboard: {e}")
        return False

def update_soundboard_category(sb_id, new_category):
    query = "UPDATE soundboards SET category = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (new_category, int(time.time()), sb_id))
            conn.commit()
        logger.info(f"Updated soundboard {sb_id} category to: {new_category}")
        return True
    except Exception as e:
        logger.error(f"Failed to update soundboard category: {e}")
        return False

def update_soundboard_favorite(sb_id: str, is_favorite: int) -> bool:
    """
    Sets the is_favorite flag (0 or 1) on a soundboard row and marks it
    unsynced so the change is pushed to Supabase on the next sync cycle.
    """
    query = "UPDATE soundboards SET is_favorite = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (int(is_favorite), int(time.time()), sb_id))
            conn.commit()
        logger.info(f"Soundboard {sb_id} favorite status set to {is_favorite}.")
        return True
    except Exception as e:
        logger.error(f"Failed to update soundboard favorite status: {e}")
        return False

def delete_soundboard(sb_id):
    # Fetch user_id and log tombstone before deleting
    user_id = None
    query_select = "SELECT user_id FROM soundboards WHERE id = ?"
    query_delete = "DELETE FROM soundboards WHERE id = ?"
    try:
        with get_db_connection() as conn:
            row = conn.execute(query_select, (sb_id,)).fetchone()
            if row:
                user_id = row["user_id"]
                conn.execute(
                    "INSERT OR REPLACE INTO deleted_records (id, table_name, user_id, deleted_at) VALUES (?, 'soundboards', ?, ?)",
                    (sb_id, user_id, int(time.time()))
                )
            conn.execute(query_delete, (sb_id,))
            conn.commit()
        logger.info(f"Deleted soundboard: {sb_id} (tombstone logged)")
        return True
    except Exception as e:
        logger.error(f"Failed to delete soundboard: {e}")
        return False

# --- SOUND CRUD OPERATIONS ---

def add_sound(sound_id, soundboard_id, user_id, name, file_path,
             hotkey=None, volume=1.0, is_favorite=0, duration=0.0):
    """
    Inserts a new sound record. Both created_at and updated_at are set to the
    current Unix timestamp. Duration is stored in seconds (float).
    """
    now = int(time.time())
    query = """
    INSERT INTO sounds (
        id, soundboard_id, user_id, name, file_path,
        hotkey, volume, duration, is_favorite, is_synced,
        created_at, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query, (
                sound_id, soundboard_id, user_id, name, file_path,
                hotkey, volume, float(duration), is_favorite,
                now, now
            ))
            conn.commit()
        logger.info(f"Added local sound: {name} ({sound_id})")
        return True
    except Exception as e:
        logger.error(f"Failed to add sound in SQLite: {e}")
        return False

def get_sounds(soundboard_id):
    """
    Returns all sounds for a soundboard ordered alphabetically by name.
    """
    query = """
    SELECT id, soundboard_id, user_id, name, file_path, supabase_storage_path,
           hotkey, volume, duration, is_favorite, is_synced, created_at, updated_at
    FROM sounds
    WHERE soundboard_id = ?
    ORDER BY name ASC
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (soundboard_id,)).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve sounds: {e}")
        return []

def get_favorite_sounds(user_id):
    """
    Returns all sounds marked as favorite across all soundboards for this user.
    """
    query = """
    SELECT id, soundboard_id, user_id, name, file_path, supabase_storage_path,
           hotkey, volume, duration, is_favorite, is_synced, created_at, updated_at
    FROM sounds
    WHERE user_id = ? AND is_favorite = 1
    ORDER BY name ASC
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (user_id,)).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve favorite sounds: {e}")
        return []

def update_sound_favorite(sound_id, is_favorite):
    query = "UPDATE sounds SET is_favorite = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (int(is_favorite), int(time.time()), sound_id))
            conn.commit()
        logger.debug(f"Toggled favorite status ({is_favorite}) for sound: {sound_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to toggle sound favorite status: {e}")
        return False

def rename_sound(sound_id: str, new_name: str) -> bool:
    """
    Renames a sound without touching any other metadata.
    Marks the row unsynced so the change is pushed on the next sync cycle.
    """
    query = "UPDATE sounds SET name = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (new_name.strip(), int(time.time()), sound_id))
            conn.commit()
        logger.info(f"Renamed sound {sound_id} to: {new_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to rename sound: {e}")
        return False

def move_sound(sound_id: str, new_soundboard_id: str) -> bool:
    """
    Reassigns a sound to a different soundboard.
    The sound's file stays in place; only the foreign-key is updated.
    Marks the row unsynced so the change propagates on the next sync cycle.
    """
    query = "UPDATE sounds SET soundboard_id = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (new_soundboard_id, int(time.time()), sound_id))
            conn.commit()
        logger.info(f"Moved sound {sound_id} to soundboard {new_soundboard_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to move sound: {e}")
        return False


def update_sound_metadata(sound_id, name, hotkey, volume):
    query = "UPDATE sounds SET name = ?, hotkey = ?, volume = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (name, hotkey, volume, int(time.time()), sound_id))
            conn.commit()
        logger.debug(f"Updated sound card metadata: {sound_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update sound metadata: {e}")
        return False

def update_sound_volume(sound_id, volume):
    """
    Updates the volume setting for a sound in SQLite and marks the row as unsynced.
    """
    query = "UPDATE sounds SET volume = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (float(volume), int(time.time()), sound_id))
            conn.commit()
        logger.debug(f"Updated local SQLite volume for sound {sound_id}: {volume:.2f}")
        return True
    except Exception as e:
        logger.error(f"Failed to update sound volume in SQLite: {e}")
        return False


def delete_sound(sound_id):
    # Fetch user_id and log tombstone before deleting
    user_id = None
    query_select = "SELECT user_id FROM sounds WHERE id = ?"
    query_delete = "DELETE FROM sounds WHERE id = ?"
    try:
        with get_db_connection() as conn:
            row = conn.execute(query_select, (sound_id,)).fetchone()
            if row:
                user_id = row["user_id"]
                conn.execute(
                    "INSERT OR REPLACE INTO deleted_records (id, table_name, user_id, deleted_at) VALUES (?, 'sounds', ?, ?)",
                    (sound_id, user_id, int(time.time()))
                )
            conn.execute(query_delete, (sound_id,))
            conn.commit()
        logger.info(f"Deleted sound metadata: {sound_id} (tombstone logged)")
        return True
    except Exception as e:
        logger.error(f"Failed to delete sound: {e}")
        return False

def get_sound_by_id(sound_id):
    """
    Fetches a single sound record by its UUID. Returns None if not found.
    """
    query = """
    SELECT id, soundboard_id, user_id, name, file_path, supabase_storage_path,
           hotkey, volume, duration, is_favorite, is_synced, created_at, updated_at
    FROM sounds WHERE id = ?
    """
    try:
        with get_db_connection() as conn:
            row = conn.execute(query, (sound_id,)).fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve sound by ID: {e}")
        return None

# --- PHASE 5 SYNC AND SETTINGS OPERATIONS ---

def save_settings(user_id, theme, master_volume, default_device, remember_me, is_synced=0, updated_at=None):
    if updated_at is None:
        updated_at = int(time.time())
    query = """
    INSERT OR REPLACE INTO settings (user_id, theme, master_volume, default_device, remember_me, is_synced, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query, (user_id, theme, float(master_volume), default_device, int(remember_me), int(is_synced), int(updated_at)))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return False

def get_settings(user_id):
    query = "SELECT user_id, theme, master_volume, default_device, remember_me, is_synced, updated_at FROM settings WHERE user_id = ?"
    try:
        with get_db_connection() as conn:
            row = conn.execute(query, (user_id,)).fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve settings: {e}")
        return None

def get_deleted_records(user_id):
    query = "SELECT id, table_name, user_id, deleted_at FROM deleted_records WHERE user_id = ?"
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (user_id,)).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve deleted records: {e}")
        return []

def clear_deleted_records(record_ids):
    if not record_ids:
        return True
    placeholders = ",".join("?" for _ in record_ids)
    query = f"DELETE FROM deleted_records WHERE id IN ({placeholders})"
    try:
        with get_db_connection() as conn:
            conn.execute(query, tuple(record_ids))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to clear deleted records: {e}")
        return False

def save_remote_soundboard(sb_id, user_id, name, category, updated_at, is_favorite=0, created_at=None):
    """
    Upserts a soundboard record received from Supabase, preserving its
    is_favorite and created_at so remote data survives a re-sync or fresh install.
    Falls back to updated_at for created_at when the remote record pre-dates
    the column addition.
    """
    if created_at is None:
        created_at = updated_at  # safe fallback for legacy rows
    query = """
    INSERT OR REPLACE INTO soundboards (id, user_id, name, category, is_favorite, is_synced, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query, (sb_id, user_id, name, category, int(is_favorite), int(created_at), int(updated_at)))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save remote soundboard to SQLite: {e}")
        return False

def save_remote_sound(sound_id, soundboard_id, user_id, name, file_path, supabase_storage_path, hotkey, volume, is_favorite, updated_at):
    query = """
    INSERT OR REPLACE INTO sounds (id, soundboard_id, user_id, name, file_path, supabase_storage_path, hotkey, volume, is_favorite, is_synced, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query, (sound_id, soundboard_id, user_id, name, file_path, supabase_storage_path, hotkey, float(volume), int(is_favorite), int(updated_at)))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save remote sound to SQLite: {e}")
        return False

def mark_soundboards_synced(sb_ids):
    if not sb_ids:
        return True
    placeholders = ",".join("?" for _ in sb_ids)
    query = f"UPDATE soundboards SET is_synced = 1 WHERE id IN ({placeholders})"
    try:
        with get_db_connection() as conn:
            conn.execute(query, tuple(sb_ids))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to mark soundboards synced: {e}")
        return False

def mark_sounds_synced(sound_ids):
    if not sound_ids:
        return True
    placeholders = ",".join("?" for _ in sound_ids)
    query = f"UPDATE sounds SET is_synced = 1 WHERE id IN ({placeholders})"
    try:
        with get_db_connection() as conn:
            conn.execute(query, tuple(sound_ids))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to mark sounds synced: {e}")
        return False

def update_sound_storage_path(sound_id, storage_path):
    query = "UPDATE sounds SET supabase_storage_path = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (storage_path, int(time.time()), sound_id))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update sound storage path: {e}")
        return False

# --- MACROS & MACRO STEPS CRUD HELPERS ---

def create_macro(macro_id, user_id, name):
    query = """
    INSERT INTO macros (id, user_id, name, is_synced, created_at, updated_at)
    VALUES (?, ?, ?, 0, ?, ?)
    """
    t = int(time.time())
    try:
        with get_db_connection() as conn:
            conn.execute(query, (macro_id, user_id, name, t, t))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to create macro: {e}")
        return False

def rename_macro(macro_id, name):
    query = "UPDATE macros SET name = ?, is_synced = 0, updated_at = ? WHERE id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (name, int(time.time()), macro_id))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to rename macro: {e}")
        return False

def delete_macro(macro_id):
    macro_info = get_macro_by_id(macro_id)
    if not macro_info:
        return False
    user_id = macro_info["user_id"]
    
    query = "DELETE FROM macros WHERE id = ?"
    tombstone_query = "INSERT OR REPLACE INTO deleted_records (id, table_name, user_id, deleted_at) VALUES (?, 'macros', ?, ?)"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (macro_id,))
            conn.execute(tombstone_query, (macro_id, user_id, int(time.time())))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete macro: {e}")
        return False

def get_macros(user_id):
    query = "SELECT id, user_id, name, is_synced, created_at, updated_at FROM macros WHERE user_id = ? ORDER BY created_at ASC"
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (user_id,)).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve macros: {e}")
        return []

def get_macro_by_id(macro_id):
    query = "SELECT id, user_id, name, is_synced, created_at, updated_at FROM macros WHERE id = ?"
    try:
        with get_db_connection() as conn:
            row = conn.execute(query, (macro_id,)).fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve macro by id: {e}")
        return None

def clear_macro_steps(macro_id):
    query = "DELETE FROM macro_steps WHERE macro_id = ?"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (macro_id,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to clear macro steps: {e}")
        return False

def add_macro_step(step_id, macro_id, position, action_type, sound_id, delay_seconds):
    query = """
    INSERT INTO macro_steps (id, macro_id, position, action_type, sound_id, delay_seconds, is_synced, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
    """
    t = int(time.time())
    try:
        with get_db_connection() as conn:
            conn.execute(query, (step_id, macro_id, int(position), action_type, sound_id, float(delay_seconds) if delay_seconds is not None else None, t, t))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add macro step: {e}")
        return False

def get_macro_steps(macro_id):
    query = "SELECT id, macro_id, position, action_type, sound_id, delay_seconds, is_synced, created_at, updated_at FROM macro_steps WHERE macro_id = ? ORDER BY position ASC"
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (macro_id,)).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve macro steps: {e}")
        return []
