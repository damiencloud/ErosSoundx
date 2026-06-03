import customtkinter as ctk
import os
import threading
from src.config import config_manager
from src.auth import auth_manager
from src.database.sqlite_db import get_db_connection
from src.database.supabase_db import test_supabase_connection
from src.logger import logger

# Views are lazy loaded inside select_tab

class ErosSoundXApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Load styling and window preferences
        theme = config_manager.get("theme", "Dark")
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")  # We customize specific elements with high-end palettes

        self.title("ErosSoundX")
        
        # Window sizing and centering
        width = config_manager.get("window_width", 900)
        height = config_manager.get("window_height", 600)
        self.geometry(f"{width}x{height}")
        self.minsize(800, 500)
        self.center_window(width, height)

        # ---------------- LAYOUT STRUCTURE ----------------
        # Grid layout (1 row, 2 columns: Sidebar and Content Frame)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Left Navigation Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#0b0c10")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1) # Spacer row

        # Sidebar Title (Cyberpunk logo)
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="ErosSoundX", 
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#00f0ff"
        )
        self.logo_label.pack(pady=(30, 20), padx=20)

        # Navigation Buttons
        self.nav_buttons = {}
        
        self.create_nav_button("dashboard", "Dashboard", self.logo_label)
        self.create_nav_button("soundboard", "Soundboards", list(self.nav_buttons.values())[-1])
        self.create_nav_button("macros", "Sound Macros", list(self.nav_buttons.values())[-1])
        self.create_nav_button("auth", "Authentication", list(self.nav_buttons.values())[-1])
        self.create_nav_button("settings", "Settings", list(self.nav_buttons.values())[-1])

        # Bottom Connection Status Bar inside Sidebar
        self.status_container = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.status_container.pack(side="bottom", fill="x", padx=20, pady=(15, 10))

        # Panic Stop Button (Cyberpunk pink/coral neon design)
        self.stop_all_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="■ STOP ALL AUDIO",
            height=35,
            fg_color="#ff0055",
            text_color="#0b0c10",
            hover_color="#d00045",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.panic_stop
        )

        self.stop_all_btn.pack(side="bottom", fill="x", padx=20, pady=(10, 0))

        self.sqlite_status = ctk.CTkLabel(
            self.status_container, 
            text="● SQLite Checking", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#ffb703",
            anchor="w"
        )
        self.sqlite_status.pack(fill="x", pady=2)

        self.supabase_status = ctk.CTkLabel(
            self.status_container, 
            text="● Cloud Checking", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#ffb703",
            anchor="w"
        )
        self.supabase_status.pack(fill="x", pady=2)

        self.sync_status_lbl = ctk.CTkLabel(
            self.status_container,
            text="● Sync: Idle",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#8e9aaf",
            anchor="w"
        )
        self.sync_status_lbl.pack(fill="x", pady=2)


        # 2. Right Content Frame
        self.content_frame = ctk.CTkFrame(self, fg_color="#161726", corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew")

        # Initialize subviews (lazy loaded on select_tab)
        self.views = {}

        # Show initial tab
        self.select_tab("dashboard")

        # Bind closing protocol cleanly
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # ---------------- STARTUP FLOW ----------------
        self.startup_sequence()

    def create_nav_button(self, name, text, anchor_widget):
        btn = ctk.CTkButton(
            self.sidebar_frame,
            text=text,
            corner_radius=8,
            height=40,
            fg_color="transparent",
            text_color="#edf2f4",
            hover_color="#121320",
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=lambda n=name: self.select_tab(n)
        )

        btn.pack(fill="x", padx=15, pady=4)
        self.nav_buttons[name] = btn

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def select_tab(self, tab_name):
        """
        Activates the chosen subview and toggles styling of navigation buttons.
        """
        # Pack-forget all views
        for view in self.views.values():
            view.pack_forget()

        # Update button highlights
        for name, btn in self.nav_buttons.items():
            if name == tab_name:
                btn.configure(fg_color="#121320", text_color="#00f0ff")
            else:
                btn.configure(fg_color="transparent", text_color="#edf2f4")

        # Instantiate view if not loaded
        if tab_name not in self.views:
            if tab_name == "dashboard":
                from src.ui.dashboard_view import DashboardView
                self.views["dashboard"] = DashboardView(parent=self.content_frame, controller=self)
            elif tab_name == "soundboard":
                from src.ui.soundboard_view import SoundboardView
                self.views["soundboard"] = SoundboardView(parent=self.content_frame, controller=self)
            elif tab_name == "macros":
                from src.ui.macros_view import MacrosView
                self.views["macros"] = MacrosView(parent=self.content_frame, controller=self)
            elif tab_name == "auth":
                from src.ui.auth_view import AuthView
                self.views["auth"] = AuthView(parent=self.content_frame, controller=self)
            elif tab_name == "settings":
                from src.ui.settings_view import SettingsView
                self.views["settings"] = SettingsView(parent=self.content_frame, controller=self)

        # Pack selected view
        selected_view = self.views[tab_name]
        selected_view.pack(fill="both", expand=True)
        
        # Trigger dynamic view refreshes
        if hasattr(selected_view, "update_view"):
            selected_view.update_view()
        if tab_name == "settings" and hasattr(selected_view, "load_logs_content"):
            selected_view.load_logs_content()

    def on_auth_state_changed(self):
        """
        Refreshes labels and view details based on the current sign-in state and Streamer Mode.
        """
        streamer_active = config_manager.get("streamer_mode", False)
        # Update Auth tab title text
        if auth_manager.is_logged_in():
            if streamer_active:
                display_name = "Streamer"
            else:
                email_alias = auth_manager.get_user_email().split("@")[0]
                if len(email_alias) > 12:
                    email_alias = email_alias[:10] + ".."
                display_name = email_alias
            self.nav_buttons["auth"].configure(text=f"Profile ({display_name})")
        else:
            self.nav_buttons["auth"].configure(text="Authentication")

        # Propagate auth updates to active views
        if "dashboard" in self.views:
            self.views["dashboard"].update_view()
        if "settings" in self.views:
            self.views["settings"].update_view()


    def check_connections(self):
        """
        Runs connection health checks in a background worker thread.
        """
        def worker():
            # 1. Check local SQLite Connection
            sqlite_ok = False
            try:
                with get_db_connection() as conn:
                    # Execute a basic ping
                    conn.execute("SELECT 1")
                sqlite_ok = True
            except Exception as e:
                logger.error(f"Local SQLite connection check failed: {e}")

            # 2. Check Supabase connection status
            supabase_ok = False
            supabase_setup = False
            
            url = config_manager.get("supabase_url")
            key = config_manager.get("supabase_key")
            
            if url and key and url != "" and key != "":
                supabase_setup = True
                supabase_ok = test_supabase_connection()

            # Safely schedule label configuration updates on the Tkinter main thread
            self.after(0, self.update_status_labels, sqlite_ok, supabase_setup, supabase_ok)

        threading.Thread(target=worker, daemon=True).start()

    def update_status_labels(self, sqlite_ok, supabase_setup, supabase_ok):
        # Update SQLite Label
        if sqlite_ok:
            self.sqlite_status.configure(text="● SQLite: Ready", text_color="#03dac6")
        else:
            self.sqlite_status.configure(text="● SQLite: Error", text_color="#cf6679")

        # Update Supabase Label
        if not supabase_setup:
            self.supabase_status.configure(text="● Cloud: Setup Required", text_color="#8e9aaf")
        elif supabase_ok:
            self.supabase_status.configure(text="● Cloud: Connected", text_color="#03dac6")
        else:
            self.supabase_status.configure(text="● Cloud: Offline", text_color="#ffb703")

    def panic_stop(self):
        from src.audio.audio_engine import audio_engine
        audio_engine.stop_all()
        try:
            from src.macro_manager import macro_manager
            macro_manager.cancel_all()
        except Exception as e:
            logger.debug(f"Failed to cancel macros on panic stop: {e}")

    def startup_sequence(self):
        """
        Verifies environment, tests connections, and attempts to restore cached login session.
        """
        # Run health checks
        self.check_connections()

        # Start background sync loop
        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.settings_applied_callback = self.apply_loaded_settings
            sync_manager.status_listeners.append(self.update_sync_status_ui)
            sync_manager.start()
        except Exception as e:
            logger.error(f"Failed to start sync manager: {e}")

        # Start API server for Mobile Remote
        try:
            from src.api_server import APIServerManager
            APIServerManager.get_instance().start()
        except Exception as e:
            logger.error(f"Failed to start local API server: {e}")

        # Load registered keyboard hotkeys globally
        self.load_registered_hotkeys()

        # Attempt to recover cached login session in a background thread
        def session_restorer():
            success = auth_manager.restore_session()
            if success:
                self.after(0, self.on_auth_state_changed)
                # Wake up sync manager to restore missing soundboards/sounds
                try:
                    from src.sync.sync_manager import sync_manager
                    sync_manager.trigger_sync()
                except Exception as e:
                    logger.debug(f"Sync trigger failed: {e}")
            else:
                logger.debug("No active session recovered during startup sequence.")
        
        threading.Thread(target=session_restorer, daemon=True).start()

    def on_closing(self):
        """
        Shuts down background services cleanly on window close.
        """
        logger.info("Application is shutting down. Stopping background tasks...")
        try:
            from src.api_server import APIServerManager
            APIServerManager.get_instance().stop()
        except Exception as e:
            logger.debug(f"Failed to stop local server: {e}")
        try:
            from src.audio.hotkeys import hotkey_manager
            hotkey_manager.stop()
        except Exception as e:
            logger.debug(f"Failed to stop hotkey manager: {e}")
        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.stop()
        except Exception as e:
            logger.debug(f"Failed to stop sync manager: {e}")
        try:
            from src.audio.audio_engine import audio_engine
            audio_engine.stop_all()
        except Exception as e:
            logger.debug(f"Failed to stop audio: {e}")
        self.destroy()

    def load_registered_hotkeys(self):
        """
        Queries all sounds that have hotkeys and registers them with the Hotkey manager on boot.
        """
        def worker():
            logger.info("Startup task: Loading user keybindings.")
            from src.audio.hotkeys import hotkey_manager
            from src.database.sqlite_db import get_db_connection
            
            hotkey_manager.clear()
            try:
                query = "SELECT id, name, file_path, volume, hotkey FROM sounds WHERE hotkey IS NOT NULL AND hotkey != ''"
                with get_db_connection() as conn:
                    rows = conn.execute(query).fetchall()
                    
                for r in rows:
                    hotkey_manager.register(
                        sound_id=r["id"],
                        file_path=r["file_path"],
                        volume=r["volume"],
                        hotkey_str=r["hotkey"],
                        sound_name=r["name"]
                    )
                hotkey_manager.start()
            except Exception as e:
                logger.error(f"Failed to load keybindings on startup: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def apply_loaded_settings(self):
        """
        Applies theme and volume changes received from cloud settings restoration.
        """
        logger.info("Applying cloud-restored settings locally.")
        theme = config_manager.get("theme", "Dark")
        ctk.set_appearance_mode(theme)
        
        # Update dropdown if settings view is open
        if "settings" in self.views and hasattr(self.views["settings"], "theme_dropdown"):
            self.views["settings"].theme_dropdown.set(theme)
            
        # Update master volume in engine
        from src.audio.audio_engine import audio_engine
        master_vol = config_manager.get("master_volume", 1.0)
        audio_engine.set_master_volume(master_vol)
        
        # Update master volume label/slider if settings view is open
        if "settings" in self.views and hasattr(self.views["settings"], "master_vol_label"):
            self.views["settings"].master_vol_label.configure(text=f"Master Volume: {int(master_vol * 100)}%")

    def update_sync_status_ui(self, status, last_sync_time):
        """
        Observer callback invoked by SyncManager thread when sync status transitions.
        Schedules UI elements update thread-safely on Tkinter main thread.
        """
        import time
        def update_labels():
            if not auth_manager.is_logged_in():
                self.sync_status_lbl.configure(text="● Sync: Offline (Guest)", text_color="#8e9aaf")
                return

            if status == "syncing":
                self.sync_status_lbl.configure(text="● Sync: Syncing...", text_color="#bb86fc")
            elif status == "offline":
                self.sync_status_lbl.configure(text="● Sync: Offline", text_color="#ffb703")
            elif status == "error":
                self.sync_status_lbl.configure(text="● Sync: Retry Queue", text_color="#cf6679")
            else: # status == "idle"
                # Display relative time or simple time
                if last_sync_time > 0:
                    local_t = time.localtime(last_sync_time)
                    time_str = time.strftime("%H:%M:%S", local_t)
                    self.sync_status_lbl.configure(text=f"● Sync: Synced ({time_str})", text_color="#03dac6")
                else:
                    self.sync_status_lbl.configure(text="● Sync: Ready", text_color="#03dac6")
        
        self.after(0, update_labels)

