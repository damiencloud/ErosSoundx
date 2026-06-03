import threading
import time
from src.logger import logger
from src.database.sqlite_db import get_macro_steps, get_sound_by_id
from src.audio.audio_engine import audio_engine

class MacroRunner(threading.Thread):
    def __init__(self, macro_id, steps, manager):
        super().__init__()
        self.macro_id = macro_id
        self.steps = steps
        self.manager = manager
        self.cancel_event = threading.Event()
        self.daemon = True

    def run(self):
        logger.info(f"Starting macro execution: {self.macro_id}")
        try:
            for step in self.steps:
                if self.cancel_event.is_set():
                    logger.info(f"Macro {self.macro_id} cancelled.")
                    break

                action_type = step.get("action_type")
                if action_type == "play":
                    sound_id = step.get("sound_id")
                    if sound_id:
                        sound = get_sound_by_id(sound_id)
                        if sound:
                            logger.debug(f"Macro playing sound: {sound['name']} ({sound_id})")
                            audio_engine.play_sound(
                                sound_id=sound["id"],
                                file_path=sound["file_path"],
                                volume=sound.get("volume", 1.0)
                            )
                        else:
                            logger.warning(f"Macro step play failed: sound_id '{sound_id}' not found in DB.")
                
                elif action_type == "delay":
                    delay_val = step.get("delay_seconds", 0.0)
                    if delay_val and delay_val > 0:
                        logger.debug(f"Macro delaying for {delay_val} seconds.")
                        # wait returns True if the event was set, False if timed out
                        interrupted = self.cancel_event.wait(delay_val)
                        if interrupted:
                            logger.info(f"Macro {self.macro_id} delay interrupted by cancellation.")
                            break
        except Exception as e:
            logger.error(f"Error executing macro {self.macro_id}: {e}")
        finally:
            self.manager._remove_runner(self)

    def cancel(self):
        self.cancel_event.set()

class MacroManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.active_runners = set()
        self.runners_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def play_macro(self, macro_id):
        """
        Loads and executes a macro in the background.
        """
        # Fetch macro steps from SQLite
        steps = get_macro_steps(macro_id)
        if not steps:
            logger.warning(f"No steps found for macro: {macro_id}")
            return False

        # Create and start background thread runner
        with self.runners_lock:
            runner = MacroRunner(macro_id, steps, self)
            self.active_runners.add(runner)
            runner.start()
        return True

    def cancel_all(self):
        """
        Cancels all running macros immediately.
        """
        with self.runners_lock:
            if not self.active_runners:
                return
            logger.info(f"Cancelling {len(self.active_runners)} active macros.")
            for runner in list(self.active_runners):
                runner.cancel()
            self.active_runners.clear()

    def _remove_runner(self, runner):
        with self.runners_lock:
            self.active_runners.discard(runner)

# Singleton export
macro_manager = MacroManager.get_instance()
