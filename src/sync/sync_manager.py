import os
import time
import threading
from src.logger import logger
from src.config import config_manager
from src.auth import auth_manager
from src.database import sqlite_db
from src.database.supabase_db import get_supabase_client, test_supabase_connection

class SyncManager:
    """
    Background cloud synchronization worker.
    Manages syncing settings, deletions, soundboards, and sounds (metadata and audio files).
    Uses timestamp-based conflict resolution and exponential backoff retry.
    """
    def __init__(self, sync_interval=30):
        self.sync_interval = sync_interval
        self.backoff_interval = 10
        self.max_backoff = 300
        
        self.trigger_event = threading.Event()
        self.stop_event = threading.Event()
        
        self.sync_thread = None
        self.is_syncing = False
        self.last_sync_time = 0
        
        # Callback to apply loaded settings to UI if updated remotely
        self.settings_applied_callback = None
        
        # Real-time status indicators and observers list
        self.status = "idle"  # "idle", "syncing", "offline", "error"
        self.status_listeners = []

    def set_status(self, new_status):
        """
        Updates the sync manager status and notifies all registered observers.
        """
        self.status = new_status
        for listener in list(self.status_listeners):
            try:
                listener(self.status, self.last_sync_time)
            except Exception as e:
                logger.error(f"Sync: Error notifying status listener: {e}")

    def start(self):
        """
        Starts the background sync loop thread.
        """
        if self.sync_thread and self.sync_thread.is_alive():
            return
            
        self.stop_event.clear()
        self.trigger_event.clear()
        self.sync_thread = threading.Thread(target=self._sync_loop, name="SyncWorker", daemon=True)
        self.sync_thread.start()
        logger.info("Background sync loop started.")

    def stop(self):
        """
        Stops the background sync loop thread.
        """
        self.stop_event.set()
        self.trigger_event.set()  # Wake up from wait
        if self.sync_thread:
            self.sync_thread.join(timeout=2.0)
            logger.info("Background sync loop stopped.")

    def trigger_sync(self):
        """
        Wakes up the sync thread to perform a synchronization immediately.
        """
        logger.debug("Sync trigger received. Waking up background sync worker.")
        self.trigger_event.set()

    def _sync_loop(self):
        """
        Background loop waiting for triggers or timeouts to execute sync runs.
        """
        # Small startup delay
        time.sleep(2)
        
        while not self.stop_event.is_set():
            # Wait for event trigger or periodic interval
            interval = self.backoff_interval if self.backoff_interval > 10 else self.sync_interval
            self.trigger_event.wait(timeout=interval)
            
            if self.stop_event.is_set():
                break
                
            self.trigger_event.clear()
            
            if not auth_manager.is_logged_in():
                self.set_status("idle")
                continue
                
            # Run sync
            self.is_syncing = True
            self.set_status("syncing")
            try:
                # Check internet connection first
                if not test_supabase_connection():
                    logger.debug("Sync loop: Supabase connection offline. Skipping sync run.")
                    self.set_status("offline")
                    # Keep same backoff, do not increment excessively if just offline
                    time.sleep(5)
                    continue
                    
                success = self.perform_sync()
                
                if success:
                    # Reset backoff on success
                    self.backoff_interval = 10
                    self.last_sync_time = time.time()
                    self.set_status("idle")
                else:
                    # Exponential backoff on failed API calls
                    self.backoff_interval = min(self.backoff_interval * 2, self.max_backoff)
                    logger.warning(f"Sync run encountered errors. Will retry in {self.backoff_interval} seconds.")
                    self.set_status("error")
            except Exception as e:
                logger.error(f"Error in background sync loop: {e}")
                self.backoff_interval = min(self.backoff_interval * 2, self.max_backoff)
                self.set_status("error")
            finally:
                self.is_syncing = False


    def perform_sync(self) -> bool:
        """
        Executes the full sync flow. Returns True if completely successful, else False.
        """
        user_id = auth_manager.get_user_id()
        client = get_supabase_client()
        if not client:
            return False
            
        logger.info("Sync: Starting synchronization cycle...")
        
        try:
            # 1. Sync settings
            logger.debug("Sync: Syncing user settings...")
            self._sync_settings(client, user_id)
            
            # 2. Sync deletions (tombstones)
            logger.debug("Sync: Processing pending deletions...")
            self._sync_deletions(client, user_id)
            
            # 3. Sync soundboards
            logger.debug("Sync: Syncing soundboard metadata...")
            self._sync_soundboards(client, user_id)
            
            # 4. Sync sounds (uploads / downloads / metadata)
            logger.debug("Sync: Syncing sounds and files...")
            self._sync_sounds(client, user_id)
            
            logger.info("Sync: Synchronization cycle completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Sync: Sync cycle failed: {e}")
            return False

    def _sync_settings(self, client, user_id):
        """
        Synchronizes user configuration between config.json, SQLite and Supabase.
        """
        # Fetch current SQLite cache settings
        local_sett = sqlite_db.get_settings(user_id)
        
        # Load active variables from config_manager
        current_theme = config_manager.get("theme", "Dark")
        current_volume = config_manager.get("master_volume", 1.0)
        current_remember = 1 if config_manager.get("remember_me", True) else 0
        
        # If no local DB settings record exists or if it doesn't match config.json
        needs_local_save = False
        if not local_sett:
            needs_local_save = True
        else:
            diff = (
                local_sett["theme"] != current_theme or
                abs(local_sett["master_volume"] - current_volume) > 0.01 or
                local_sett["remember_me"] != current_remember
            )
            if diff:
                needs_local_save = True
                
        if needs_local_save:
            sqlite_db.save_settings(user_id, current_theme, current_volume, "", current_remember, is_synced=0)
            local_sett = sqlite_db.get_settings(user_id)

        # Retrieve remote settings from Supabase
        remote_response = client.table("settings").select("*").eq("user_id", user_id).execute()
        remote_sett_list = remote_response.data
        remote_sett = remote_sett_list[0] if remote_sett_list else None

        if not remote_sett:
            # Remote doesn't have settings, push local
            logger.debug("Sync: Remote settings missing. Uploading local settings.")
            payload = {
                "user_id": user_id,
                "theme": local_sett["theme"],
                "master_volume": float(local_sett["master_volume"]),
                "remember_me": int(local_sett["remember_me"]),
                "updated_at": int(local_sett["updated_at"])
            }
            client.table("settings").upsert(payload).execute()
            sqlite_db.save_settings(user_id, local_sett["theme"], local_sett["master_volume"], "", local_sett["remember_me"], is_synced=1, updated_at=local_sett["updated_at"])
        else:
            # Conflict resolution: compare updated_at
            local_time = local_sett["updated_at"]
            remote_time = remote_sett["updated_at"]
            
            if local_sett["is_synced"] == 0 or local_time > remote_time:
                # Local settings are newer: upload local
                logger.debug("Sync: Local settings are newer. Uploading local settings.")
                payload = {
                    "user_id": user_id,
                    "theme": local_sett["theme"],
                    "master_volume": float(local_sett["master_volume"]),
                    "remember_me": int(local_sett["remember_me"]),
                    "updated_at": int(local_sett["updated_at"])
                }
                client.table("settings").upsert(payload).execute()
                sqlite_db.save_settings(user_id, local_sett["theme"], local_sett["master_volume"], "", local_sett["remember_me"], is_synced=1, updated_at=local_sett["updated_at"])
            elif local_time < remote_time:
                # Remote settings are newer: pull remote and overwrite local
                logger.debug("Sync: Remote settings are newer. Restoring remote settings locally.")
                sqlite_db.save_settings(user_id, remote_sett["theme"], remote_sett["master_volume"], "", remote_sett["remember_me"], is_synced=1, updated_at=remote_sett["updated_at"])
                
                # Apply changes to local configuration manager
                config_manager.set("theme", remote_sett["theme"])
                config_manager.set("master_volume", remote_sett["master_volume"])
                config_manager.set("remember_me", remote_sett["remember_me"] == 1)
                
                # Trigger callback to apply changes to UI thread-safely
                if self.settings_applied_callback:
                    if hasattr(self.settings_applied_callback, "__self__") and hasattr(self.settings_applied_callback.__self__, "after"):
                        self.settings_applied_callback.__self__.after(0, self.settings_applied_callback)
                    else:
                        self.settings_applied_callback()

    def _sync_deletions(self, client, user_id):
        """
        Pushes locally deleted records to the cloud.
        """
        tombstones = sqlite_db.get_deleted_records(user_id)
        if not tombstones:
            return

        success_ids = []
        for t in tombstones:
            t_id = t["id"]
            tbl = t["table_name"]
            try:
                # Delete remotely
                client.table(tbl).delete().eq("id", t_id).execute()
                success_ids.append(t_id)
                logger.debug(f"Sync: Deleted remote record {t_id} from table '{tbl}'")
            except Exception as e:
                logger.error(f"Sync: Failed to delete remote record {t_id} from '{tbl}': {e}")

        # Clear successfully synced tombstones
        if success_ids:
            sqlite_db.clear_deleted_records(success_ids)

    def _sync_soundboards(self, client, user_id):
        """
        Synchronizes soundboards metadata.
        """
        local_boards = sqlite_db.get_soundboards(user_id)
        local_map = {b["id"]: b for b in local_boards}
        
        # Get remote
        remote_response = client.table("soundboards").select("*").eq("user_id", user_id).execute()
        remote_boards = remote_response.data
        remote_map = {b["id"]: b for b in remote_boards}

        # Process local soundboards (upload new/updated)
        boards_to_upsert = []
        local_synced_ids = []
        for b_id, b in local_map.items():
            if b_id not in remote_map:
                # Local only – push to remote
                boards_to_upsert.append({
                    "id": b["id"],
                    "user_id": b["user_id"],
                    "name": b["name"],
                    "category": b["category"],
                    "is_favorite": int(b.get("is_favorite", 0)),
                    "created_at": int(b.get("created_at", b["updated_at"])),
                    "updated_at": int(b["updated_at"])
                })
                local_synced_ids.append(b_id)
            else:
                # Present on both
                r = remote_map[b_id]
                if b["is_synced"] == 0 or b["updated_at"] > r["updated_at"]:
                    # Local is newer
                    boards_to_upsert.append({
                        "id": b["id"],
                        "user_id": b["user_id"],
                        "name": b["name"],
                        "category": b["category"],
                        "is_favorite": int(b.get("is_favorite", 0)),
                        "created_at": int(b.get("created_at", b["updated_at"])),
                        "updated_at": int(b["updated_at"])
                    })
                    local_synced_ids.append(b_id)
                elif b["updated_at"] < r["updated_at"]:
                    # Remote is newer – pull down, restore is_favorite + created_at from remote
                    sqlite_db.save_remote_soundboard(
                        r["id"], r["user_id"], r["name"], r["category"],
                        r["updated_at"],
                        is_favorite=int(r.get("is_favorite", 0)),
                        created_at=r.get("created_at")
                    )
                    logger.debug(f"Sync: Pulled newer remote soundboard: {r['name']}")

        if boards_to_upsert:
            client.table("soundboards").upsert(boards_to_upsert).execute()
            sqlite_db.mark_soundboards_synced(local_synced_ids)
            logger.info(f"Sync: Pushed {len(boards_to_upsert)} soundboard updates to Supabase.")

        # Process remote-only soundboards (pull down)
        for r_id, r in remote_map.items():
            if r_id not in local_map:
                sqlite_db.save_remote_soundboard(
                    r["id"], r["user_id"], r["name"], r["category"],
                    r["updated_at"],
                    is_favorite=int(r.get("is_favorite", 0)),
                    created_at=r.get("created_at")
                )
                logger.info(f"Sync: Restored missing soundboard: {r['name']}")

    def _sync_sounds(self, client, user_id):
        """
        Synchronizes sounds metadata and transfers physical audio files.
        """
        # Build local isolated cache path for file downloads
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        user_cache_dir = os.path.join(root_dir, "cache", user_id)
        os.makedirs(user_cache_dir, exist_ok=True)

        local_sounds = []
        # Query SQLite sounds for user_id
        try:
            with sqlite_db.get_db_connection() as conn:
                rows = conn.execute("SELECT id, soundboard_id, user_id, name, file_path, supabase_storage_path, hotkey, volume, is_favorite, is_synced, updated_at FROM sounds WHERE user_id = ?", (user_id,)).fetchall()
                local_sounds = [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Sync: Failed to query sounds: {e}")
            
        local_map = {s["id"]: s for s in local_sounds}

        # Fetch remote
        remote_response = client.table("sounds").select("*").eq("user_id", user_id).execute()
        remote_sounds = remote_response.data
        remote_map = {s["id"]: s for s in remote_sounds}

        # Verify storage bucket "sounds" exists
        bucket = client.storage.from_("sounds")
        try:
            client.storage.get_bucket("sounds")
        except Exception:
            try:
                client.storage.create_bucket("sounds", options={"public": False})
            except Exception as e:
                logger.debug(f"Sync: Bucket check/create skipped: {e}")

        sounds_to_upsert = []
        synced_sound_ids = []

        # Process local-only and updated sounds
        for s_id, s in local_map.items():
            # Check if file needs upload
            needs_upload = False
            remote_path = s["supabase_storage_path"]
            
            if not remote_path or remote_path == "":
                # Generate path: users/[user_id]/[sound_id].[ext]
                _, ext = os.path.splitext(s["file_path"])
                remote_path = f"users/{user_id}/{s_id}{ext}"
                needs_upload = True
            
            # If path exists but let's double check if we need to force file upload
            if needs_upload and os.path.exists(s["file_path"]):
                try:
                    logger.debug(f"Sync: Uploading file for sound '{s['name']}' to: {remote_path}")
                    with open(s["file_path"], "rb") as f:
                        bucket.upload(
                            path=remote_path,
                            file=f,
                            file_options={"cache-control": "3600", "upsert": "true"}
                        )
                    # Update local schema storage path and flag it as unsynced (so metadata is pushed)
                    s["supabase_storage_path"] = remote_path
                    sqlite_db.update_sound_storage_path(s_id, remote_path)
                    s["is_synced"] = 0
                except Exception as upload_err:
                    logger.error(f"Sync: Failed to upload file for sound '{s['name']}': {upload_err}")
                    continue  # Retry file upload in next loop before syncing metadata

            # Check if metadata needs upserting
            if s_id not in remote_map:
                sounds_to_upsert.append({
                    "id": s["id"],
                    "soundboard_id": s["soundboard_id"],
                    "user_id": s["user_id"],
                    "name": s["name"],
                    "supabase_storage_path": s["supabase_storage_path"],
                    "hotkey": s["hotkey"],
                    "volume": float(s["volume"]),
                    "is_favorite": int(s["is_favorite"]),
                    "updated_at": int(s["updated_at"])
                })
                synced_sound_ids.append(s_id)
            else:
                r = remote_map[s_id]
                if s["is_synced"] == 0 or s["updated_at"] > r["updated_at"]:
                    sounds_to_upsert.append({
                        "id": s["id"],
                        "soundboard_id": s["soundboard_id"],
                        "user_id": s["user_id"],
                        "name": s["name"],
                        "supabase_storage_path": s["supabase_storage_path"],
                        "hotkey": s["hotkey"],
                        "volume": float(s["volume"]),
                        "is_favorite": int(s["is_favorite"]),
                        "updated_at": int(s["updated_at"])
                    })
                    synced_sound_ids.append(s_id)
                elif s["updated_at"] < r["updated_at"]:
                    # Remote metadata is newer, pull metadata
                    sqlite_db.save_remote_sound(
                        r["id"], r["soundboard_id"], r["user_id"], r["name"],
                        s["file_path"], r["supabase_storage_path"], r["hotkey"],
                        r["volume"], r["is_favorite"], r["updated_at"]
                    )
                    logger.debug(f"Sync: Pulled newer remote sound metadata: {r['name']}")

        # Push metadata updates to Supabase
        if sounds_to_upsert:
            client.table("sounds").upsert(sounds_to_upsert).execute()
            sqlite_db.mark_sounds_synced(synced_sound_ids)
            logger.info(f"Sync: Pushed {len(sounds_to_upsert)} sound card metadata updates.")

        # Process remote-only sounds (restore)
        for r_id, r in remote_map.items():
            if r_id not in local_map:
                # Calculate file cache location
                r_path = r["supabase_storage_path"]
                if not r_path:
                    continue
                    
                _, ext = os.path.splitext(r_path)
                local_file_path = os.path.join(user_cache_dir, f"{r_id}{ext}")
                
                # Insert row locally first
                sqlite_db.save_remote_sound(
                    r["id"], r["soundboard_id"], r["user_id"], r["name"],
                    local_file_path, r["supabase_storage_path"], r["hotkey"],
                    r["volume"], r["is_favorite"], r["updated_at"]
                )
                logger.info(f"Sync: Restored sound metadata: {r['name']}")

                # Download file object
                try:
                    logger.info(f"Sync: Downloading remote sound file: {r_path}")
                    response_data = bucket.download(r_path)
                    with open(local_file_path, "wb") as f:
                        f.write(response_data)
                    logger.info(f"Sync: Cached sound file restored to {local_file_path}")
                except Exception as dl_err:
                    logger.error(f"Sync: Failed to download audio file {r_path}: {dl_err}")

        # Final check: Download missing audio files for existing local records
        for s_id, s in local_map.items():
            if s_id in remote_map:
                r = remote_map[s_id]
                # If local file does not exist on disk but we have remote path, download it
                if not os.path.exists(s["file_path"]) and s["supabase_storage_path"]:
                    try:
                        logger.info(f"Sync: Cache hit but local file missing. Re-downloading: {s['supabase_storage_path']}")
                        response_data = bucket.download(s["supabase_storage_path"])
                        os.makedirs(os.path.dirname(s["file_path"]), exist_ok=True)
                        with open(s["file_path"], "wb") as f:
                            f.write(response_data)
                        logger.info(f"Sync: Successfully restored cached file: {s['file_path']}")
                    except Exception as redl_err:
                        logger.error(f"Sync: Failed to re-download missing cache file {s['supabase_storage_path']}: {redl_err}")

# Global sync manager singleton
sync_manager = SyncManager()
