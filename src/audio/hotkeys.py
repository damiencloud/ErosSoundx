from pynput import keyboard
from src.logger import logger
from src.audio.audio_engine import audio_engine
from src.config import config_manager

# Common OS-level hotkeys to prevent capturing them or warning the user
RESERVED_OS_HOTKEYS = {
    "<alt>+<tab>",
    "<ctrl>+<alt>+<delete>",
    "<cmd>+l",
    "<cmd>+d",
    "<alt>+<f4>",
}

def normalize_hotkey(hotkey_str: str) -> str:
    """
    Normalizes human-readable hotkey combinations (e.g. 'Ctrl+Shift+F1') 
    to the format required by pynput (e.g. '<ctrl>+<shift>+<f1>').
    """
    if not hotkey_str or not hotkey_str.strip():
        return ""
        
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    normalized_parts = []
    
    for part in parts:
        if part in ["ctrl", "control"]:
            normalized_parts.append("<ctrl>")
        elif part == "alt":
            normalized_parts.append("<alt>")
        elif part in ["shift", "shft"]:
            normalized_parts.append("<shift>")
        elif part in ["win", "cmd", "command", "super"]:
            normalized_parts.append("<cmd>")
        elif part.startswith("f") and len(part) > 1 and part[1:].isdigit():
            normalized_parts.append(f"<{part}>")
        elif part in ["space", "enter", "tab", "up", "down", "left", "right"]:
            normalized_parts.append(f"<{part}>")
        elif part in ["esc", "escape"]:
            normalized_parts.append("<esc>")
        elif part in ["del", "delete"]:
            normalized_parts.append("<delete>")
        else:
            normalized_parts.append(part)
            
    return "+".join(normalized_parts)

def is_os_reserved(hotkey_str: str) -> bool:
    """
    Checks if a hotkey string normalizes to a common OS-reserved shortcut.
    """
    norm = normalize_hotkey(hotkey_str)
    return norm in RESERVED_OS_HOTKEYS

def validate_hotkey_format(hotkey_str: str) -> bool:
    """
    Validates that the hotkey format is correct, does not contain empty/trailing parts,
    and includes at least one non-modifier/base key.
    """
    if not hotkey_str or not hotkey_str.strip():
        return False
    parts = [p.strip() for p in hotkey_str.split("+")]
    if not parts or any(not p for p in parts):
        return False
    # Check if there is at least one non-modifier key
    modifiers = {"ctrl", "control", "alt", "shift", "shft", "win", "cmd", "command", "super"}
    base_keys = [p for p in parts if p.lower() not in modifiers]
    if not base_keys:
        return False
    return True

class HotkeyEngine:
    """
    Asynchronous Global Hotkey Service.
    Hooks into OS-level keyboard events to play sounds from anywhere.
    """
    def __init__(self):
        self.raw_hotkeys = {}       # Maps sound_id -> raw_hotkey_string
        self.bindings = {}          # Maps normalized_hotkey_string -> sound_metadata_dict
        self.listener = None        # Holds the pynput GlobalHotKeys listener thread
        
    def check_conflict(self, hotkey_str: str, ignore_sound_id: str = None) -> str:
        """
        Checks if a hotkey combination is already registered.
        Returns:
            - "panic" if it conflicts with the panic key
            - conflicting sound ID if a collision is found with another sound
            - empty string if no conflict is found
        """
        norm_key = normalize_hotkey(hotkey_str)
        if not norm_key:
            return ""

        # Check against Panic Hotkey
        panic_hotkey_str = config_manager.get("panic_hotkey", "Escape")
        if normalize_hotkey(panic_hotkey_str) == norm_key:
            return "panic"

        for sound_id, sound_data in self.bindings.items():
            if sound_data["normalized_key"] == norm_key and sound_data["sound_id"] != ignore_sound_id:
                return sound_data["sound_id"]
        return ""

    def register(self, sound_id: str, file_path: str, volume: float, hotkey_str: str, sound_name: str = ""):
        """
        Registers or updates a hotkey binding.
        Requires calling reload() to restart the listener thread and apply changes.
        """
        self.unregister(sound_id)
        
        norm_key = normalize_hotkey(hotkey_str)
        if not norm_key:
            return

        self.raw_hotkeys[sound_id] = hotkey_str
        self.bindings[norm_key] = {
            "sound_id": sound_id,
            "sound_name": sound_name,
            "file_path": file_path,
            "volume": volume,
            "normalized_key": norm_key
        }
        logger.info(f"Registered hotkey bind: {hotkey_str} ({norm_key}) for sound '{sound_name}'")

    def unregister(self, sound_id: str):
        """
        Removes a sound card's keybinding registry.
        """
        raw_key = self.raw_hotkeys.pop(sound_id, None)
        if raw_key:
            norm_key = normalize_hotkey(raw_key)
            self.bindings.pop(norm_key, None)
            logger.info(f"Unregistered hotkey bind for sound: {sound_id}")

    def clear(self):
        """
        Wipes all hotkey registers and stops active hooks.
        """
        self.stop()
        self.raw_hotkeys.clear()
        self.bindings.clear()

    def start(self):
        """
        Spins up the global keyboard listener daemon thread mapping bindings to audio playback callbacks.
        """
        if self.listener and self.listener.running:
            return

        panic_hotkey_str = config_manager.get("panic_hotkey", "Escape")
        norm_panic_key = normalize_hotkey(panic_hotkey_str)

        if not self.bindings and not norm_panic_key:
            logger.debug("No hotkey bindings or panic key to monitor.")
            return

        # Prepare pynput GlobalHotKeys mappings
        hotkeys_map = {}
        for norm_key, data in self.bindings.items():
            # Capture data inside closure safely using default args
            def play_trigger(d=data):
                logger.info(f"Hotkey '{d['normalized_key']}' triggered. Playing sound: {d['sound_name']}")
                audio_engine.play_sound(d["sound_id"], d["file_path"], d["volume"])
            
            hotkeys_map[norm_key] = play_trigger

        if norm_panic_key:
            def panic_trigger():
                logger.info(f"Panic hotkey '{norm_panic_key}' triggered. Stopping all sounds.")
                audio_engine.stop_all()
            hotkeys_map[norm_panic_key] = panic_trigger

        try:
            self.listener = keyboard.GlobalHotKeys(hotkeys_map)
            self.listener.daemon = True  # Thread stops automatically when main app exits
            self.listener.start()
            logger.info(f"Global hotkey listener started with {len(hotkeys_map)} binds.")
        except Exception as e:
            logger.error(f"Failed to start global keyboard listener: {e}")

    def stop(self):
        """
        Stops the global keyboard hook listener safely.
        """
        if self.listener:
            try:
                self.listener.stop()
                logger.info("Global hotkey listener stopped.")
            except Exception as e:
                logger.error(f"Error stopping keyboard listener: {e}")
            self.listener = None

    def reload(self):
        """
        Reloads active keyboard hooks by restarting the listener thread.
        This must be called after changing bindings.
        """
        self.stop()
        self.start()

# Global hotkey manager instance
hotkey_manager = HotkeyEngine()
