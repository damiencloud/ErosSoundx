import customtkinter as ctk
from src.auth import auth_manager
from src.config import config_manager

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Title block
        title_label = ctk.CTkLabel(
            self, 
            text="ErosSoundX Dashboard", 
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color="#00f0ff"
        )
        title_label.pack(pady=(30, 5), padx=30, anchor="w")

        subtitle_label = ctk.CTkLabel(
            self, 
            text="Your command center for premium audio control", 
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#8e9aaf"
        )
        subtitle_label.pack(pady=(0, 15), padx=30, anchor="w")

        # Stats summary row (3 cards)
        self.stats_row = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_row.pack(fill="x", padx=30, pady=(0, 10))
        self.stats_row.grid_columnconfigure((0, 1, 2), weight=1, uniform="equal")
        self.stats_row.grid_rowconfigure(0, weight=1)

        # Card 1: Speaker Output
        self.stat_card_1 = ctk.CTkFrame(self.stats_row, fg_color="#111222", corner_radius=10, border_color="#1a1b35", border_width=1, height=75)
        self.stat_card_1.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        self.stat_card_1.grid_propagate(False)
        self.stat_lbl_1 = ctk.CTkLabel(self.stat_card_1, text="🔊 Primary Output", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8e9aaf")
        self.stat_lbl_1.pack(pady=(12, 2), padx=15, anchor="w")
        self.stat_val_1 = ctk.CTkLabel(self.stat_card_1, text="Default", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#00f0ff")
        self.stat_val_1.pack(pady=0, padx=15, anchor="w")

        # Card 2: Mic Routing
        self.stat_card_2 = ctk.CTkFrame(self.stats_row, fg_color="#111222", corner_radius=10, border_color="#1a1b35", border_width=1, height=75)
        self.stat_card_2.grid(row=0, column=1, padx=5, sticky="nsew")
        self.stat_card_2.grid_propagate(False)
        self.stat_lbl_2 = ctk.CTkLabel(self.stat_card_2, text="🎙️ Virtual Mic Routing", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8e9aaf")
        self.stat_lbl_2.pack(pady=(12, 2), padx=15, anchor="w")
        self.stat_val_2 = ctk.CTkLabel(self.stat_card_2, text="Inactive", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#ffb703")
        self.stat_val_2.pack(pady=0, padx=15, anchor="w")

        # Card 3: Remote Server
        self.stat_card_3 = ctk.CTkFrame(self.stats_row, fg_color="#111222", corner_radius=10, border_color="#1a1b35", border_width=1, height=75)
        self.stat_card_3.grid(row=0, column=2, padx=(10, 0), sticky="nsew")
        self.stat_card_3.grid_propagate(False)
        self.stat_lbl_3 = ctk.CTkLabel(self.stat_card_3, text="📱 Remote API Server", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8e9aaf")
        self.stat_lbl_3.pack(pady=(12, 2), padx=15, anchor="w")
        self.stat_val_3 = ctk.CTkLabel(self.stat_card_3, text="Offline", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#ff0055")
        self.stat_val_3.pack(pady=0, padx=15, anchor="w")

        # Welcome card (Cyberpunk themed)
        self.welcome_card = ctk.CTkFrame(self, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        self.welcome_card.pack(fill="x", padx=30, pady=10)

        self.welcome_title = ctk.CTkLabel(
            self.welcome_card, 
            text="Welcome to ErosSoundX!", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#bc00dd"
        )
        self.welcome_title.pack(pady=(15, 5), padx=20, anchor="w")

        self.welcome_desc = ctk.CTkLabel(
            self.welcome_card, 
            text="Real-time multi-channel audio mixer, low-latency hotkeys, and secure offline-first databases are active.\nOpen the 'Soundboards' tab to configure your soundboard panels and load audio files.", 
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#edf2f4",
            justify="left"
        )
        self.welcome_desc.pack(pady=(0, 15), padx=20, anchor="w")

        # Bottom row grid container to display Profile Card & Mobile Remote Card side-by-side
        self.bottom_row = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_row.pack(fill="both", expand=True, padx=30, pady=(10, 20))
        self.bottom_row.grid_columnconfigure((0, 1), weight=1, uniform="equal")
        self.bottom_row.grid_rowconfigure(0, weight=1)

        # Column 0: User Session Profile display
        self.profile_card = ctk.CTkFrame(self.bottom_row, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        self.profile_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        self.profile_title = ctk.CTkLabel(
            self.profile_card, 
            text="👤 User Session Profile", 
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#00f0ff"
        )
        self.profile_title.pack(pady=(15, 10), padx=20, anchor="w")

        self.profile_details = ctk.CTkLabel(
            self.profile_card, 
            text="Status:    Checking authentication...", 
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#ffb703",
            justify="left"
        )
        self.profile_details.pack(pady=10, padx=20, anchor="w")

        # Column 1: Mobile Remote details
        self.remote_card = ctk.CTkFrame(self.bottom_row, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        self.remote_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        self.remote_title = ctk.CTkLabel(
            self.remote_card, 
            text="📱 Mobile Remote Control", 
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#00f0ff"
        )
        self.remote_title.pack(pady=(15, 10), padx=20, anchor="w")

        self.remote_details = ctk.CTkLabel(
            self.remote_card, 
            text="Status:    Checking connection server...", 
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#ffb703",
            justify="left"
        )
        self.remote_details.pack(pady=10, padx=20, anchor="w")

        # Bind hover micro-animations
        for card in [self.stat_card_1, self.stat_card_2, self.stat_card_3, self.welcome_card]:
            card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#bc00dd"))
            card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))
            
        self.profile_card.bind("<Enter>", lambda e: self.profile_card.configure(border_color="#00f0ff"))
        self.profile_card.bind("<Leave>", lambda e: self.profile_card.configure(border_color="#1a1b35"))
        self.remote_card.bind("<Enter>", lambda e: self.remote_card.configure(border_color="#00f0ff"))
        self.remote_card.bind("<Leave>", lambda e: self.remote_card.configure(border_color="#1a1b35"))

    def update_view(self):
        """
        Updates the dashboard content based on auth state, streamer mode, and local server.
        """
        streamer_active = config_manager.get("streamer_mode", False)

        # Update Primary Output Stat Card
        output_dev = config_manager.get("primary_audio_device", "Default")
        if len(output_dev) > 28:
            output_dev = output_dev[:25] + "..."
        self.stat_val_1.configure(text=output_dev)

        # Update Virtual Mic Status Card
        vmic_enabled = config_manager.get("virtual_mic_enabled", False)
        if vmic_enabled:
            from src.audio.audio_engine import audio_engine
            if audio_engine.subprocess_handle and audio_engine.subprocess_handle.poll() is None:
                self.stat_val_2.configure(text="ACTIVE", text_color="#03dac6")
            else:
                self.stat_val_2.configure(text="ROUTING ERROR", text_color="#ff0055")
        else:
            self.stat_val_2.configure(text="DISABLED", text_color="#8e9aaf")

        # 1. Update Auth profile card details
        if auth_manager.is_logged_in():
            email = auth_manager.get_user_email()
            uid = auth_manager.get_user_id()
            username = email.split('@')[0]

            if streamer_active:
                display_email = "[HIDDEN (STREAMER MODE)]"
                display_uid = "[HIDDEN (STREAMER MODE)]"
                display_username = "Streamer"
            else:
                display_email = email
                display_uid = uid
                display_username = username

            profile_text = f"Status:    ACTIVE SESSION (ONLINE)\nEmail:     {display_email}\nUser ID:   {display_uid}\nProvider:  Supabase Auth"
            self.profile_details.configure(text=profile_text, text_color="#03dac6")
            self.welcome_title.configure(text=f"Welcome back, {display_username}!")
        else:
            profile_text = "Status:    NO SESSION (OFFLINE/GUEST MODE)\n\nPlease log in or sign up in the 'Profile' tab to access cloud sync."
            self.profile_details.configure(text=profile_text, text_color="#ffb703")
            self.welcome_title.configure(text="Welcome to ErosSoundX!")

        # 2. Update local mobile remote status details
        try:
            from src.api_server import APIServerManager
            manager = APIServerManager.get_instance()
            if manager.is_running:
                ip = manager.get_local_ip()
                port = manager.port
                token = manager.token
                
                display_token = "[HIDDEN]" if streamer_active else token
                url = f"http://{ip}:{port}/?token={display_token}"
                
                remote_text = (
                    f"Server:    ACTIVE (RUNNING)\n"
                    f"Local IP:  {ip}\n"
                    f"Port:      {port}\n"
                    f"Token:     {display_token}\n\n"
                    f"Open connection link in mobile browser:\n"
                    f"{url}"
                )
                self.remote_details.configure(text=remote_text, text_color="#03dac6")
                self.stat_val_3.configure(text=f"{ip}:{port}", text_color="#03dac6")
            else:
                remote_text = "Server:    STOPPED / OFFLINE\n\nEnsure local ports are available and restart the application."
                self.remote_details.configure(text=remote_text, text_color="#ff0055")
                self.stat_val_3.configure(text="OFFLINE", text_color="#ff0055")
        except Exception as e:
            self.remote_details.configure(text=f"Error checking API Server:\n{e}", text_color="#ff0055")
            self.stat_val_3.configure(text="ERROR", text_color="#ff0055")
