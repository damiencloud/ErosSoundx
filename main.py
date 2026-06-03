import sys
import os
import time
import threading
import customtkinter as ctk

# Ensure workspace paths are in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.logger import logger
from src.database.sqlite_db import init_db
from src.audio.audio_engine import audio_engine
from src.ui.app import ErosSoundXApp
from src.bug_tracker import BugTracker

class SplashScreen(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure borderless window
        self.overrideredirect(True)
        self.configure(fg_color="#0c0f12")

        # Window dimensions and centering
        width = 450
        height = 280
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Top border frame (neon cyan glow effect)
        glow_bar = ctk.CTkFrame(self, height=4, fg_color="#00f0ff", corner_radius=0)
        glow_bar.pack(fill="x", side="top")

        # Title Label
        title_label = ctk.CTkLabel(
            self,
            text="ErosSoundX",
            font=ctk.CTkFont(family="Segoe UI", size=36, weight="bold"),
            text_color="#00f0ff"
        )
        title_label.pack(expand=True, pady=(40, 5))

        # Subtitle
        subtitle_label = ctk.CTkLabel(
            self,
            text="CYBERPUNK AUDIO TRANSMITTER",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#bc00dd"
        )
        subtitle_label.pack(pady=(0, 20))

        # Status text
        self.status_label = ctk.CTkLabel(
            self,
            text="Initializing Core Systems...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#8e9aaf"
        )
        self.status_label.pack(pady=(0, 10))

        # Progress bar
        self.progress = ctk.CTkProgressBar(
            self,
            width=320,
            height=6,
            corner_radius=3,
            progress_color="#bc00dd",
            fg_color="#1a1c30"
        )
        self.progress.set(0.0)
        self.progress.pack(pady=(0, 40))

        # Run initialization in a background thread
        self.init_thread = threading.Thread(target=self.run_initialization, daemon=True)
        self.init_thread.start()

    def update_status(self, text, val):
        def set_status():
            self.status_label.configure(text=text)
            self.progress.set(val)
        self.after(0, set_status)

    def run_initialization(self):
        start_time = time.time()
        
        try:
            # 1. Initialize SQLite Database schema & tuning
            self.update_status("Loading Database WAL Schemas...", 0.25)
            init_db()
            time.sleep(0.3)  # smooth transition

            # 2. Lazy pre-initialize pygame audio mixer
            self.update_status("Pre-initializing Pygame Audio Engine...", 0.6)
            audio_engine.initialize()
            time.sleep(0.3)

            # 3. Finalize setup
            self.update_status("Configuring Hotkeys & Session Layers...", 0.85)
            time.sleep(0.3)

            # Ensure splash screen displays for at least 1.5s to feel premium
            elapsed = time.time() - start_time
            if elapsed < 1.5:
                time.sleep(1.5 - elapsed)

            self.update_status("Connection Ready.", 1.0)
            time.sleep(0.2)

            # Exit splash and start app on Tkinter main thread
            self.after(0, self.launch_main_app)
        except Exception as e:
            logger.critical(f"Initialization crashed: {e}")
            self.after(0, self.destroy)
            sys.exit(1)

    def launch_main_app(self):
        self.destroy()
        
        # Instantiate the main application window
        app = ErosSoundXApp()
        
        # Initialize BugTracker global exception hooking
        BugTracker.initialize(app)
        
        # Run CustomTkinter main loop
        app.mainloop()

def main():
    logger.info("Launching ErosSoundX Boot Splash...")
    splash = SplashScreen()
    splash.mainloop()
    logger.info("ErosSoundX Application closed.")

if __name__ == "__main__":
    main()
