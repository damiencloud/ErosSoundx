import os
import json
import zipfile
import uuid
import shutil
import tempfile
import time
from src.logger import logger
from src.auth import auth_manager
from src.database.sqlite_db import get_db_connection, get_sounds, get_macro_steps
from src.soundboard_manager import soundboard_manager

class PackManager:
    @staticmethod
    def export_pack(soundboard_id, export_path):
        """
        Exports a soundboard, its sounds, and dependent macros to a versioned .sbx (ZIP) archive.
        """
        logger.info(f"Starting export for soundboard {soundboard_id} to {export_path}")
        try:
            # 1. Fetch soundboard metadata
            soundboard = None
            with get_db_connection() as conn:
                row = conn.execute("SELECT id, name, category FROM soundboards WHERE id = ?", (soundboard_id,)).fetchone()
                if row:
                    soundboard = dict(row)

            if not soundboard:
                logger.error(f"Export failed: Soundboard {soundboard_id} not found.")
                return False

            # 2. Fetch sounds
            sounds = get_sounds(soundboard_id)
            sound_ids = {s["id"] for s in sounds}

            # 3. Fetch dependent macros and steps
            # Find macros that reference at least one sound in this board
            dependent_macro_ids = set()
            macro_steps_to_export = []
            
            # Query all macro steps containing a sound from this board
            if sound_ids:
                placeholders = ",".join("?" for _ in sound_ids)
                query = f"SELECT id, macro_id, position, action_type, sound_id, delay_seconds FROM macro_steps WHERE sound_id IN ({placeholders})"
                with get_db_connection() as conn:
                    rows = conn.execute(query, tuple(sound_ids)).fetchall()
                    for r in rows:
                        dependent_macro_ids.add(r["macro_id"])

            # Fetch macro definitions and all steps for these macros
            macros_to_export = []
            if dependent_macro_ids:
                placeholders = ",".join("?" for _ in dependent_macro_ids)
                with get_db_connection() as conn:
                    macro_rows = conn.execute(f"SELECT id, name FROM macros WHERE id IN ({placeholders})", tuple(dependent_macro_ids)).fetchall()
                    macros_to_export = [dict(m) for m in macro_rows]

                    step_rows = conn.execute(f"SELECT id, macro_id, position, action_type, sound_id, delay_seconds FROM macro_steps WHERE macro_id IN ({placeholders})", tuple(dependent_macro_ids)).fetchall()
                    macro_steps_to_export = [dict(s) for s in step_rows]

            # 4. Compile manifest.json
            sounds_metadata = []
            for s in sounds:
                sounds_metadata.append({
                    "old_id": s["id"],
                    "name": s["name"],
                    "hotkey": s["hotkey"],
                    "volume": s["volume"],
                    "duration": s["duration"],
                    "is_favorite": s["is_favorite"],
                    "file_name": os.path.basename(s["file_path"])
                })

            manifest = {
                "format_version": "1.0",
                "soundboard": {
                    "name": soundboard["name"],
                    "category": soundboard["category"]
                },
                "sounds": sounds_metadata,
                "macros": macros_to_export,
                "macro_steps": macro_steps_to_export
            }

            # 5. Build ZIP file
            # Work in a temporary zip file then move it to prevent corruption
            temp_zip_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip")
            os.close(temp_zip_fd)

            with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # Write manifest
                zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))
                
                # Write sound files
                for s in sounds:
                    if os.path.exists(s["file_path"]):
                        arcname = os.path.join("sounds", os.path.basename(s["file_path"]))
                        zip_file.write(s["file_path"], arcname)
                    else:
                        logger.warning(f"Audio file missing during export: {s['file_path']}")

            # Move temp zip file to target destination
            if os.path.exists(export_path):
                os.remove(export_path)
            shutil.move(temp_zip_path, export_path)
            logger.info("Soundboard exported successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to export soundboard pack: {e}")
            return False

    @staticmethod
    def import_pack(pack_path, progress_callback=None):
        """
        Imports a soundboard package, updating references, copying files, and generating new UUIDs.
        """
        logger.info(f"Starting import from pack: {pack_path}")
        temp_dir = tempfile.mkdtemp()
        try:
            # 1. Unzip the pack to temp directory
            with zipfile.ZipFile(pack_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            manifest_path = os.path.join(temp_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                logger.error("Import failed: manifest.json not found in archive.")
                return False

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            # Validate version
            if manifest.get("format_version") != "1.0":
                logger.error("Import failed: Unsupported package format version.")
                return False

            # Verify sounds exist
            sounds_data = manifest.get("sounds", [])
            for s in sounds_data:
                sound_file_path = os.path.join(temp_dir, "sounds", s["file_name"])
                if not os.path.exists(sound_file_path):
                    logger.error(f"Import failed: Missing audio file in archive: {s['file_name']}")
                    return False

            # 2. Setup ID Mappings
            new_sb_id = str(uuid.uuid4())
            sound_id_map = {}
            macro_id_map = {}

            user_id = auth_manager.get_user_id() or "guest_user"
            user_cache_dir = soundboard_manager.get_user_cache_dir()

            # Insert Soundboard
            sb_info = manifest["soundboard"]
            with get_db_connection() as conn:
                t = int(time.time())
                conn.execute(
                    "INSERT INTO soundboards (id, user_id, name, category, is_favorite, is_synced, created_at, updated_at) VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
                    (new_sb_id, user_id, sb_info["name"] + " (Imported)", sb_info.get("category", "General"), t, t)
                )
                conn.commit()
            
            total_steps = len(sounds_data) + len(manifest.get("macros", [])) + len(manifest.get("macro_steps", []))
            current_step = 0

            # 3. Import sounds
            for s in sounds_data:
                old_sound_id = s["old_id"]
                new_sound_id = str(uuid.uuid4())
                sound_id_map[old_sound_id] = new_sound_id

                # Resolve file extension
                _, ext = os.path.splitext(s["file_name"])
                dest_file_name = f"{new_sound_id}{ext}"
                dest_file_path = os.path.join(user_cache_dir, dest_file_name)

                # Copy file to cache
                src_file_path = os.path.join(temp_dir, "sounds", s["file_name"])
                shutil.copy2(src_file_path, dest_file_path)

                # Save sound metadata
                with get_db_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO sounds (id, soundboard_id, user_id, name, file_path, hotkey, volume, duration, is_favorite, is_synced, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (new_sound_id, new_sb_id, user_id, s["name"], dest_file_path, s.get("hotkey"), s.get("volume", 1.0), s.get("duration", 0.0), s.get("is_favorite", 0), t, t)
                    )
                    conn.commit()
                current_step += 1
                if progress_callback:
                    progress_callback(int((current_step / total_steps) * 100))

            # 4. Import macros
            macros_data = manifest.get("macros", [])
            for m in macros_data:
                old_macro_id = m["id"]
                new_macro_id = str(uuid.uuid4())
                macro_id_map[old_macro_id] = new_macro_id

                with get_db_connection() as conn:
                    conn.execute(
                        "INSERT INTO macros (id, user_id, name, is_synced, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
                        (new_macro_id, user_id, m["name"] + " (Imported)", t, t)
                    )
                    conn.commit()
                current_step += 1
                if progress_callback:
                    progress_callback(int((current_step / total_steps) * 100))

            # 5. Import macro steps
            steps_data = manifest.get("macro_steps", [])
            for st in steps_data:
                old_macro_id = st["macro_id"]
                new_macro_id = macro_id_map.get(old_macro_id)
                if not new_macro_id:
                    continue  # skip orphan steps

                # Map sound_id to new sound ID
                old_sound_id = st.get("sound_id")
                new_sound_id = sound_id_map.get(old_sound_id) # None if it's a delay step or external

                new_step_id = str(uuid.uuid4())
                with get_db_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO macro_steps (id, macro_id, position, action_type, sound_id, delay_seconds, is_synced, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (new_step_id, new_macro_id, st["position"], st["action_type"], new_sound_id, st.get("delay_seconds"), t, t)
                    )
                    conn.commit()
                current_step += 1
                if progress_callback:
                    progress_callback(int((current_step / total_steps) * 100))

            # Trigger change notification on soundboard manager
            soundboard_manager.notify_change()
            
            # Wake sync manager to upload imported items to Supabase
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception:
                pass

            logger.info("Import completed successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to import package: {e}")
            return False
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
