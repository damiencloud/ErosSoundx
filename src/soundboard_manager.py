import uuid
import os
import wave
import struct
import shutil
from src.logger import logger
from src.auth import auth_manager
from src.database import sqlite_db

class SoundboardManager:
    """
    Service layer to manage soundboard groups and individual sound metadata.
    """
    def __init__(self):
        # Resolve a local cache directory for storing copied audio files
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_dir = os.path.join(root_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.on_change_callbacks = []

    def register_change_callback(self, callback):
        """
        Registers a callback that fires whenever soundboards or sounds are updated.
        """
        if callback not in self.on_change_callbacks:
            self.on_change_callbacks.append(callback)

    def notify_change(self):
        """
        Triggers all registered change callbacks.
        """
        for cb in self.on_change_callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"Error in soundboard manager change callback: {e}")

    def get_effective_user_id(self) -> str:
        """
        Returns the logged in Supabase user UUID, falling back to a guest identifier if offline.
        """
        if auth_manager.is_logged_in():
            return auth_manager.get_user_id()
        return "guest_user"

    def get_user_cache_dir(self) -> str:
        """
        Returns the cache path isolated for the current active user session.
        """
        user_dir = os.path.join(self.cache_dir, self.get_effective_user_id())
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        """
        Computes the SHA256 checksum of the specified file.
        """
        import hashlib
        sha_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha_hash.update(byte_block)
            return sha_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate SHA256 hash for {file_path}: {e}")
            return ""

    @staticmethod
    def _detect_duration(file_path: str) -> float:
        """
        Returns the duration of an audio file in seconds.

        Supports WAV natively via the stdlib `wave` module.
        For MP3 files, performs a lightweight frame-count estimation using
        the MPEG Layer III header without requiring mutagen or any external
        library.  Returns 0.0 if duration cannot be determined.
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        try:
            if ext == ".wav":
                with wave.open(file_path, "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    return round(frames / float(rate), 2) if rate > 0 else 0.0

            elif ext == ".mp3":
                # Scan MP3 frames to estimate duration.
                # MPEG1 Layer3 frames: each carries 1152 samples at the stream sample rate.
                duration = 0.0
                with open(file_path, "rb") as f:
                    data = f.read()

                i = 0
                frames_found = 0
                sample_rate = 0
                while i < len(data) - 3:
                    # Look for frame sync: 0xFF 0xFx
                    if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
                        b1 = data[i + 1]
                        b2 = data[i + 2]
                        version = (b1 >> 3) & 0x03  # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
                        layer   = (b1 >> 1) & 0x03  # 1=L3
                        bitrate_idx = (b2 >> 4) & 0x0F
                        sr_idx  = (b2 >> 2) & 0x03

                        # MPEG1 Layer3 bitrate table (kbps)
                        bitrates = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0]
                        # Sample-rate table: [44100,48000,32000]
                        sample_rates = {3: [44100,48000,32000], 2: [22050,24000,16000], 0: [11025,12000,8000]}

                        if layer == 1 and version in sample_rates and bitrate_idx < 15:
                            sr = sample_rates[version][sr_idx] if sr_idx < 3 else 0
                            br = bitrates[bitrate_idx] * 1000
                            if sr > 0 and br > 0:
                                samples_per_frame = 1152
                                frame_size = (samples_per_frame // 8 * br) // sr + (1 if (b2 >> 1) & 1 else 0)
                                if sample_rate == 0:
                                    sample_rate = sr
                                frames_found += 1
                                duration += samples_per_frame / sr
                                i += max(frame_size, 1)
                                continue
                    i += 1

                return round(duration, 2) if frames_found > 0 else 0.0

        except Exception as e:
            logger.debug(f"Duration detection failed for {file_path}: {e}")

        return 0.0

    # --- SOUNDBOARD CRUD SERVICES ---

    def create_board(self, name: str, category: str = "General") -> str:
        """
        Creates a new local soundboard, returning its generated UUID if successful, else "".
        """
        if not name.strip():
            logger.warning("Attempted to create soundboard with empty name.")
            return ""

        sb_id = str(uuid.uuid4())
        user_id = self.get_effective_user_id()
        success = sqlite_db.create_soundboard(sb_id, user_id, name.strip(), category)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed: {e}")
            self.notify_change()
        return sb_id if success else ""

    def get_boards(self) -> list:
        """
        Fetches all soundboards owned by the active session profile.
        """
        user_id = self.get_effective_user_id()
        return sqlite_db.get_soundboards(user_id)

    def rename_board(self, sb_id: str, new_name: str) -> bool:
        """
        Renames a soundboard.
        """
        if not new_name.strip():
            logger.warning("Attempted to rename soundboard to an empty name.")
            return False
        success = sqlite_db.rename_soundboard(sb_id, new_name.strip())
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed: {e}")
            self.notify_change()
        return success

    def update_board_category(self, sb_id: str, new_category: str) -> bool:
        """
        Updates the category label of a soundboard.
        """
        success = sqlite_db.update_soundboard_category(sb_id, new_category.strip())
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed: {e}")
            self.notify_change()
        return success

    def delete_board(self, sb_id: str) -> bool:
        """
        Deletes a soundboard and cascades to delete all associated sound cards.
        """
        # Note: Foreign Key CASCADE in SQLite handles child deletions in sounds table automatically.
        # However, we must also clean up any physical cached files.
        sounds = self.get_board_sounds(sb_id)
        success = sqlite_db.delete_soundboard(sb_id)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed: {e}")
            for s in sounds:
                if os.path.exists(s["file_path"]):
                    try:
                        os.remove(s["file_path"])
                        logger.debug(f"Removed orphaned local cache sound file: {s['file_path']}")
                    except Exception as e:
                        logger.warning(f"Failed to delete cache file {s['file_path']}: {e}")
            self.notify_change()
        return success

    def toggle_board_favorite(self, sb_id: str, is_favorite: bool) -> bool:
        """
        Toggles the favorite state of a soundboard.

        Favorited boards are sorted to the front of the board list and
        rendered with a ★ prefix in the UI. The change is immediately
        persisted to SQLite and queued for Supabase synchronization.

        Args:
            sb_id:       UUID of the soundboard to update.
            is_favorite: True to mark as favorite, False to remove.

        Returns:
            True on success, False if the DB write failed.
        """
        if not sb_id:
            logger.warning("toggle_board_favorite called with empty sb_id.")
            return False

        success = sqlite_db.update_soundboard_favorite(sb_id, 1 if is_favorite else 0)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed after board favorite toggle: {e}")
            self.notify_change()
        return success

    # --- SOUND CARD CRUD SERVICES (METADATA + LOCAL CACHE COPYING) ---

    def add_sound_card(self, soundboard_id: str, name: str, source_file_path: str, hotkey: str = None) -> str:
        """
        Adds a sound to a soundboard.

        Copies the audio file to the user's isolated local cache folder and
        auto-detects the duration (seconds) from the file header before inserting
        the metadata row into SQLite.
        """
        if not name.strip() or not source_file_path:
            logger.warning("Missing name or source file path when adding sound card.")
            return ""

        if not os.path.exists(source_file_path):
            logger.error(f"Source audio file does not exist: {source_file_path}")
            return ""

        sound_id = str(uuid.uuid4())
        user_id = self.get_effective_user_id()

        # Detect duration before copying so we don't touch the original file twice
        duration = self._detect_duration(source_file_path)

        # Calculate isolated cache destination path
        _, ext = os.path.splitext(source_file_path)
        dest_filename = f"{sound_id}{ext}"
        dest_path = os.path.join(self.get_user_cache_dir(), dest_filename)

        try:
            shutil.copy2(source_file_path, dest_path)
            logger.debug(f"Cached audio file copied to: {dest_path}")
        except Exception as e:
            logger.error(f"Failed to cache audio file: {e}")
            return ""

        # Compute SHA256 hash of the cached file
        sha256_hash = self._compute_sha256(dest_path)

        success = sqlite_db.add_sound(
            sound_id=sound_id,
            soundboard_id=soundboard_id,
            user_id=user_id,
            name=name.strip(),
            file_path=dest_path,
            hotkey=hotkey,
            volume=1.0,
            is_favorite=0,
            duration=duration,
            sha256_hash=sha256_hash
        )

        if not success:
            # Rollback file copy on database insert failure
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return ""

        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.trigger_sync()
        except Exception as e:
            logger.debug(f"Sync trigger failed: {e}")

        # Register hotkey binding if one was provided
        if hotkey:
            try:
                from src.audio.hotkeys import hotkey_manager
                hotkey_manager.register(sound_id, dest_path, 1.0, hotkey, name.strip())
                hotkey_manager.reload()
            except Exception as e:
                logger.error(f"Failed to register keybinding on sound card add: {e}")

        self.notify_change()
        return sound_id

    def get_board_sounds(self, soundboard_id: str) -> list:
        """
        Fetches all sound cards belonging to a soundboard.
        """
        return sqlite_db.get_sounds(soundboard_id)

    def get_favorites(self) -> list:
        """
        Fetches all sound cards marked as favorite across all soundboards for the active user.
        """
        user_id = self.get_effective_user_id()
        return sqlite_db.get_favorite_sounds(user_id)

    def toggle_favorite(self, sound_id: str, is_favorite: bool) -> bool:
        """
        Toggles the favorite state of a sound.
        """
        success = sqlite_db.update_sound_favorite(sound_id, 1 if is_favorite else 0)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed: {e}")
            self.notify_change()
        return success

    def rename_sound(self, sound_id: str, new_name: str) -> bool:
        """
        Renames a sound without modifying any other field.

        This is a lighter-weight alternative to update_sound_card(), which
        also handles hotkeys and volume. Use this when only the display name
        needs to change.

        Args:
            sound_id: UUID of the sound to rename.
            new_name: The desired new display name (must not be empty).

        Returns:
            True on success, False if validation fails or the DB write fails.
        """
        new_name = new_name.strip()
        if not new_name:
            logger.warning("rename_sound called with empty name.")
            return False
        success = sqlite_db.rename_sound(sound_id, new_name)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed after sound rename: {e}")
            self.notify_change()
        return success

    def move_sound(self, sound_id: str, new_soundboard_id: str) -> bool:
        """
        Moves a sound to a different soundboard.

        Only the soundboard_id foreign key is updated; the cached audio file
        remains in its original location and all other metadata is preserved.

        Args:
            sound_id:          UUID of the sound to move.
            new_soundboard_id: UUID of the destination soundboard.

        Returns:
            True on success, False if either ID is empty or the DB write fails.
        """
        if not sound_id or not new_soundboard_id:
            logger.warning("move_sound called with empty sound_id or soundboard_id.")
            return False
        success = sqlite_db.move_sound(sound_id, new_soundboard_id)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed after sound move: {e}")
            self.notify_change()
        return success

    def update_sound_card(self, sound_id: str, name: str, hotkey: str, volume: float) -> bool:
        """
        Updates metadata fields on a sound card.
        """
        if not name.strip():
            return False
        # Limit volume range between 0.0 and 2.0
        volume = max(0.0, min(2.0, float(volume)))
        
        # Query existing file path first for hotkey manager reference
        sound_info = sqlite_db.get_sound_by_id(sound_id)
        file_path = sound_info["file_path"] if sound_info else ""

        success = sqlite_db.update_sound_metadata(sound_id, name.strip(), hotkey, volume)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed: {e}")
            try:
                from src.audio.hotkeys import hotkey_manager
                if hotkey and file_path:
                    hotkey_manager.register(sound_id, file_path, volume, hotkey, name.strip())
                else:
                    hotkey_manager.unregister(sound_id)
                hotkey_manager.reload()
            except Exception as e:
                logger.error(f"Failed to update keybinding on metadata change: {e}")
            self.notify_change()
        return success

    def update_sound_volume(self, sound_id: str, volume: float) -> bool:
        """
        Updates the volume level of a sound card in database and updates keybinding volume configuration.
        """
        volume = max(0.0, min(1.0, float(volume)))
        success = sqlite_db.update_sound_volume(sound_id, volume)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed after volume update: {e}")
            try:
                from src.audio.hotkeys import hotkey_manager
                sound_info = sqlite_db.get_sound_by_id(sound_id)
                if sound_info and sound_info.get("hotkey"):
                    hotkey_manager.register(
                        sound_id=sound_id,
                        file_path=sound_info["file_path"],
                        volume=volume,
                        hotkey_str=sound_info["hotkey"],
                        sound_name=sound_info["name"]
                    )
                    hotkey_manager.reload()
            except Exception as e:
                logger.debug(f"Failed to update hotkey volume: {e}")
            self.notify_change()
        return success


    def remove_sound_card(self, sound_id: str) -> bool:
        """
        Deletes a sound card record and clears its physical cache file.
        """
        # Fetch metadata first to locate file path
        # In a real environment we might query by ID, let's just query or try to delete
        # We can find file path by deleting or query.
        # Actually, let's find the file path manually using the cache folder if we know the ID
        user_dir = self.get_user_cache_dir()
        
        # Scan for files matching sound_id
        target_path = None
        for filename in os.listdir(user_dir):
            base, _ = os.path.splitext(filename)
            if base == sound_id:
                target_path = os.path.join(user_dir, filename)
                break

        success = sqlite_db.delete_sound(sound_id)
        if success:
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.debug(f"Sync trigger failed: {e}")
            try:
                from src.audio.hotkeys import hotkey_manager
                hotkey_manager.unregister(sound_id)
                hotkey_manager.reload()
            except Exception as e:
                logger.error(f"Failed to unregister keybinding on sound card removal: {e}")

            if target_path and os.path.exists(target_path):
                try:
                    os.remove(target_path)
                    logger.debug(f"Cleared sound cache file: {target_path}")
                except Exception as e:
                    logger.warning(f"Failed to clear cache file {target_path}: {e}")
            self.notify_change()
                
        return success

# Global soundboard manager instance
soundboard_manager = SoundboardManager()
