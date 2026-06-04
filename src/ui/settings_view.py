import os
import customtkinter as ctk
import threading
from src.config import config_manager
from src.database.supabase_db import test_supabase_connection, reset_supabase_client
from src.database.sqlite_db import clear_local_sessions
from src.logger import logger

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Title block
        title_label = ctk.CTkLabel(
            self, 
            text="Settings", 
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color="#ffffff"
        )
        title_label.pack(pady=(30, 5), padx=30, anchor="w")

        subtitle_label = ctk.CTkLabel(
            self, 
            text="Configure application preferences and cloud sync settings", 
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#8e9aaf"
        )
        subtitle_label.pack(pady=(0, 20), padx=30, anchor="w")

        # Scrollable panel to group settings beautifully
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        self.draw_appearance_settings()
        self.draw_audio_settings()
        self.draw_hotkey_settings()
        self.draw_qr_pairing_settings()
        self.draw_supabase_settings()
        self.draw_system_settings()
        self.draw_log_viewer()
        self.draw_about_settings()

        # Register settings status listener with background sync worker
        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.status_listeners.append(self.update_sync_status)
        except Exception as e:
            logger.debug(f"Failed to register sync manager observer in settings: {e}")

        # Register level listener with audio engine
        try:
            from src.audio.audio_engine import audio_engine
            audio_engine.register_level_listener(self.on_levels_received)
        except Exception as e:
            logger.debug(f"Failed to register level listener: {e}")


    def draw_appearance_settings(self):
        # Appearance Card
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#bc00dd"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        label = ctk.CTkLabel(card, text="Appearance & Visuals", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(pady=(12, 8), padx=20, anchor="w")

        theme_frame = ctk.CTkFrame(card, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=(0, 10))

        theme_label = ctk.CTkLabel(theme_frame, text="Theme Mode:", font=ctk.CTkFont(family="Segoe UI", size=13), text_color="#edf2f4")
        theme_label.pack(side="left", padx=(0, 20))

        current_theme = config_manager.get("theme", "Dark")
        self.theme_dropdown = ctk.CTkOptionMenu(
            theme_frame,
            values=["Dark", "Light", "System"],
            command=self.change_theme,
            fg_color="#04050a",
            button_color="#bc00dd",
            button_hover_color="#8c00aa",
            dropdown_fg_color="#111222",
            dropdown_hover_color="#bc00dd",
            dropdown_text_color="#ffffff",
            text_color="#ffffff"
        )
        self.theme_dropdown.set(current_theme)
        self.theme_dropdown.pack(side="left")

        # Streamer Mode Toggle Switch
        streamer_frame = ctk.CTkFrame(card, fg_color="transparent")
        streamer_frame.pack(fill="x", padx=20, pady=(5, 15))

        self.streamer_var = ctk.BooleanVar(value=config_manager.get("streamer_mode", False))
        self.streamer_switch = ctk.CTkSwitch(
            streamer_frame,
            text="Streamer Mode (Mask sensitive accounts and credentials in UI)",
            variable=self.streamer_var,
            command=self.toggle_streamer_mode,
            progress_color="#00f0ff",
            button_color="#bc00dd",
            button_hover_color="#8c00aa",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#edf2f4"
        )
        self.streamer_switch.pack(side="left")

    def change_theme(self, new_theme):
        config_manager.set("theme", new_theme)
        ctk.set_appearance_mode(new_theme)
        logger.info(f"Appearance theme switched to: {new_theme}")
        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.trigger_sync()
        except Exception as e:
            logger.debug(f"Failed to trigger sync: {e}")

    def toggle_streamer_mode(self):
        val = self.streamer_var.get()
        config_manager.set("streamer_mode", val)
        logger.info(f"Streamer mode set to: {val}")

        # Update input displays if supabase settings inputs are drawn
        if hasattr(self, "url_entry") and hasattr(self, "key_entry"):
            self.url_entry.delete(0, "end")
            self.key_entry.delete(0, "end")
            if val:
                self.url_entry.insert(0, "[HIDDEN (STREAMER MODE)]")
                self.key_entry.insert(0, "[HIDDEN (STREAMER MODE)]")
            else:
                self.url_entry.insert(0, config_manager.get("supabase_url", ""))
                self.key_entry.insert(0, config_manager.get("supabase_key", ""))

        # Broadcast state changes to main shell views
        self.controller.on_auth_state_changed()


    def draw_audio_settings(self):
        # Audio Playback Master Volume Card
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#00f0ff"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        label = ctk.CTkLabel(card, text="Audio Devices & Routing Mixer", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(pady=(12, 5), padx=20, anchor="w")

        desc_label = ctk.CTkLabel(card, text="Select physical microphone/speakers, route soundboard, and monitor live levels.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        desc_label.pack(pady=(0, 15), padx=20, anchor="w")

        from src.audio.audio_engine import audio_engine
        devices = audio_engine.get_available_devices()
        mics = audio_engine.get_available_microphones()
        
        # 1. Master Volume Section (Monitoring output)
        vol_frame = ctk.CTkFrame(card, fg_color="transparent")
        vol_frame.pack(fill="x", padx=20, pady=(0, 15))

        current_vol = audio_engine.master_volume
        self.master_vol_label = ctk.CTkLabel(vol_frame, text=f"Master Volume (Local Speakers): {int(current_vol * 100)}%", font=ctk.CTkFont(family="Segoe UI", size=13))
        self.master_vol_label.pack(anchor="w", pady=(0, 4))

        vol_slider = ctk.CTkSlider(
            vol_frame, 
            from_=0.0, 
            to=1.0, 
            number_of_steps=20,
            button_color="#00f0ff",
            progress_color="#bc00dd",
            button_hover_color="#00b8cc",
            command=self.change_master_volume
        )
        vol_slider.set(current_vol)
        vol_slider.pack(fill="x")

        # Divider
        divider = ctk.CTkFrame(card, height=1, fg_color="#1a1b35")
        divider.pack(fill="x", padx=20, pady=10)

        # 2. Output Device Selection Grid
        grid_frame = ctk.CTkFrame(card, fg_color="transparent")
        grid_frame.pack(fill="x", padx=20, pady=(0, 10))
        grid_frame.columnconfigure(1, weight=1)

        # Primary Output Dropdown
        primary_label = ctk.CTkLabel(grid_frame, text="Primary Output (What you hear):", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        primary_label.grid(row=0, column=0, sticky="w", pady=5, padx=(0, 20))

        primary_options = ["Default"] + devices
        current_primary = config_manager.get("primary_audio_device", "Default")
        if current_primary not in primary_options:
            primary_options.append(current_primary)

        self.primary_device_dropdown = ctk.CTkOptionMenu(
            grid_frame,
            values=primary_options,
            command=self.change_primary_device,
            fg_color="#04050a",
            button_color="#bc00dd",
            button_hover_color="#8c00aa",
            dropdown_fg_color="#111222",
            dropdown_hover_color="#bc00dd",
            dropdown_text_color="#ffffff",
            text_color="#ffffff",
            width=280
        )
        self.primary_device_dropdown.set(current_primary)
        self.primary_device_dropdown.grid(row=0, column=1, sticky="w", pady=5)

        # Physical Microphone Dropdown
        mic_label = ctk.CTkLabel(grid_frame, text="Physical Microphone (Your Voice):", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        mic_label.grid(row=1, column=0, sticky="w", pady=5, padx=(0, 20))

        mic_options = ["Default"] + mics
        current_mic = config_manager.get("mic_device", "Default")
        if current_mic not in mic_options:
            mic_options.append(current_mic)

        self.mic_device_dropdown = ctk.CTkOptionMenu(
            grid_frame,
            values=mic_options,
            command=self.change_mic_device,
            fg_color="#04050a",
            button_color="#bc00dd",
            button_hover_color="#8c00aa",
            dropdown_fg_color="#111222",
            dropdown_hover_color="#bc00dd",
            dropdown_text_color="#ffffff",
            text_color="#ffffff",
            width=280
        )
        self.mic_device_dropdown.set(current_mic)
        self.mic_device_dropdown.grid(row=1, column=1, sticky="w", pady=5)

        # Virtual Mic Output Device Dropdown
        vmic_label = ctk.CTkLabel(grid_frame, text="Virtual Mic Device (VB-CABLE Input):", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        vmic_label.grid(row=2, column=0, sticky="w", pady=5, padx=(0, 20))

        current_vmic = config_manager.get("virtual_mic_device", "")
        # Auto detect default virtual mic if empty
        if not current_vmic:
            for dev in devices:
                if "cable" in dev.lower():
                    current_vmic = dev
                    break

        vmic_options = devices.copy()
        if current_vmic and current_vmic not in vmic_options:
            vmic_options.append(current_vmic)
        if not vmic_options:
            vmic_options = ["None Detected"]

        self.vmic_device_dropdown = ctk.CTkOptionMenu(
            grid_frame,
            values=vmic_options,
            command=self.change_virtual_mic_device,
            fg_color="#04050a",
            button_color="#bc00dd",
            button_hover_color="#8c00aa",
            dropdown_fg_color="#111222",
            dropdown_hover_color="#bc00dd",
            dropdown_text_color="#ffffff",
            text_color="#ffffff",
            width=280
        )
        if current_vmic:
            self.vmic_device_dropdown.set(current_vmic)
            config_manager.set("virtual_mic_device", current_vmic)
        else:
            self.vmic_device_dropdown.set(vmic_options[0])
        self.vmic_device_dropdown.grid(row=2, column=1, sticky="w", pady=5)

        # Virtual Mic Switch / Toggle
        route_label = ctk.CTkLabel(grid_frame, text="Virtual Mic Routing Status:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        route_label.grid(row=3, column=0, sticky="w", pady=10, padx=(0, 20))

        self.route_var = ctk.BooleanVar(value=config_manager.get("virtual_mic_enabled", False))
        self.route_switch = ctk.CTkSwitch(
            grid_frame,
            text="Enable Voice & Soundboard Multiplexing",
            variable=self.route_var,
            command=self.toggle_virtual_mic,
            progress_color="#00f0ff",
            button_color="#bc00dd",
            button_hover_color="#8c00aa",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#edf2f4"
        )
        self.route_switch.grid(row=3, column=1, sticky="w", pady=10)

        # Divider
        divider2 = ctk.CTkFrame(card, height=1, fg_color="#1a1b35")
        divider2.pack(fill="x", padx=20, pady=10)

        # 3. Independent Routing Volume & Mute Controls
        mix_frame = ctk.CTkFrame(card, fg_color="transparent")
        mix_frame.pack(fill="x", padx=20, pady=(0, 10))
        mix_frame.columnconfigure(1, weight=1)

        # Microphone routing volume
        mic_vol_label = ctk.CTkLabel(mix_frame, text="Microphone Volume:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        mic_vol_label.grid(row=0, column=0, sticky="w", pady=5, padx=(0, 20))

        mic_slider_frame = ctk.CTkFrame(mix_frame, fg_color="transparent")
        mic_slider_frame.grid(row=0, column=1, sticky="ew", pady=5)
        mic_slider_frame.columnconfigure(0, weight=1)

        self.mic_vol_slider = ctk.CTkSlider(
            mic_slider_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=20,
            button_color="#00f0ff",
            progress_color="#bc00dd",
            command=self.change_mic_volume
        )
        self.mic_vol_slider.set(config_manager.get("mic_volume", 1.0))
        self.mic_vol_slider.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.mic_mute_var = ctk.BooleanVar(value=config_manager.get("mic_muted", False))
        self.mic_mute_switch = ctk.CTkSwitch(
            mic_slider_frame,
            text="Mute Mic",
            variable=self.mic_mute_var,
            command=self.toggle_mic_mute,
            progress_color="#ff0055",
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.mic_mute_switch.grid(row=0, column=1, sticky="w")

        # Soundboard routing volume
        sbd_vol_label = ctk.CTkLabel(mix_frame, text="Soundboard Route Vol:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        sbd_vol_label.grid(row=1, column=0, sticky="w", pady=5, padx=(0, 20))

        sbd_slider_frame = ctk.CTkFrame(mix_frame, fg_color="transparent")
        sbd_slider_frame.grid(row=1, column=1, sticky="ew", pady=5)
        sbd_slider_frame.columnconfigure(0, weight=1)

        self.sbd_vol_slider = ctk.CTkSlider(
            sbd_slider_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=20,
            button_color="#00f0ff",
            progress_color="#bc00dd",
            command=self.change_sbd_volume
        )
        self.sbd_vol_slider.set(config_manager.get("soundboard_playback_volume", 1.0))
        self.sbd_vol_slider.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.sbd_mute_var = ctk.BooleanVar(value=config_manager.get("soundboard_muted", False))
        self.sbd_mute_switch = ctk.CTkSwitch(
            sbd_slider_frame,
            text="Mute Soundboard",
            variable=self.sbd_mute_var,
            command=self.toggle_sbd_mute,
            progress_color="#ff0055",
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.sbd_mute_switch.grid(row=0, column=1, sticky="w")

        # Divider
        divider3 = ctk.CTkFrame(card, height=1, fg_color="#1a1b35")
        divider3.pack(fill="x", padx=20, pady=10)

        # 4. Live Audio Level Meters
        meters_frame = ctk.CTkFrame(card, fg_color="transparent")
        meters_frame.pack(fill="x", padx=20, pady=(0, 10))
        meters_frame.columnconfigure(0, weight=1)
        meters_frame.columnconfigure(1, weight=1)

        # Mic Level Meter
        mic_meter_frame = ctk.CTkFrame(meters_frame, fg_color="transparent")
        mic_meter_frame.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        mic_meter_lbl = ctk.CTkLabel(mic_meter_frame, text="Microphone Live Level:", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        mic_meter_lbl.pack(anchor="w")
        
        self.mic_level_bar = ctk.CTkProgressBar(mic_meter_frame, height=8, progress_color="#00f0ff", fg_color="#04050a")
        self.mic_level_bar.set(0.0)
        self.mic_level_bar.pack(fill="x", pady=2)

        # Soundboard Level Meter
        sbd_meter_frame = ctk.CTkFrame(meters_frame, fg_color="transparent")
        sbd_meter_frame.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        
        sbd_meter_lbl = ctk.CTkLabel(sbd_meter_frame, text="Soundboard Live Level:", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        sbd_meter_lbl.pack(anchor="w")
        
        self.sbd_level_bar = ctk.CTkProgressBar(sbd_meter_frame, height=8, progress_color="#bc00dd", fg_color="#04050a")
        self.sbd_level_bar.set(0.0)
        self.sbd_level_bar.pack(fill="x", pady=2)

        # Status and Test Buttons
        status_frame = ctk.CTkFrame(card, fg_color="transparent")
        status_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.vmic_status_lbl = ctk.CTkLabel(
            status_frame,
            text="● Virtual Mic: Checking...",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        self.vmic_status_lbl.pack(side="left", padx=(0, 20))

        self.latency_lbl = ctk.CTkLabel(
            status_frame,
            text="Buffer Latency: -- ms",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#8e9aaf"
        )
        self.latency_lbl.pack(side="left", padx=(0, 20))

        test_btn = ctk.CTkButton(
            status_frame,
            text="🔊 Test Audio Routing",
            fg_color="#bc00dd",
            text_color="#ffffff",
            hover_color="#8c00aa",
            width=160,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.test_audio_devices
        )
        test_btn.pack(side="left")

        # 5. Warnings and Setup Instructions
        self.diagnostics_box = ctk.CTkFrame(card, fg_color="#04050a", corner_radius=8, border_color="#ffb703", border_width=1)
        self.diagnostics_box.pack(fill="x", padx=20, pady=(0, 15))

        cable_detected = any("cable" in d.lower() for d in devices)
        
        self.diag_lbl = ctk.CTkLabel(
            self.diagnostics_box,
            text="⚠️ VB-CABLE Virtual Audio Device not detected on your system.",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#ffb703"
        )
        self.diag_lbl.pack(padx=15, pady=8, anchor="w")

        self.instruction_lbl = ctk.CTkLabel(
            self.diagnostics_box,
            text=(
                "How to Setup Virtual Microphone Routing:\n"
                "1. Download and install VB-CABLE driver from https://vb-audio.com/Cable/ (restart your PC).\n"
                "2. In ErosSoundX Settings (above), select 'CABLE Input' as your Virtual Mic Device and enable Routing.\n"
                "3. Open Discord, TeamSpeak, or Valorant settings, and set your Input Device (Microphone) to 'CABLE Output'.\n"
                "4. Keep your Output Device (Speakers/Headphones) set normally so you can hear your friends."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#edf2f4",
            justify="left",
            anchor="w"
        )
        self.instruction_lbl.pack(padx=15, pady=(0, 10), anchor="w")

        if cable_detected:
            self.diagnostics_box.configure(border_color="#03dac6")
            self.diag_lbl.configure(text="✔ VB-CABLE Virtual Device Detected successfully.", text_color="#03dac6")

        self.update_vmic_status_label()

    def change_master_volume(self, val):
        from src.audio.audio_engine import audio_engine
        audio_engine.set_master_volume(val)
        self.master_vol_label.configure(text=f"Master Volume (Local Speakers): {int(float(val) * 100)}%")
        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.trigger_sync()
        except Exception as e:
            logger.debug(f"Failed to trigger sync: {e}")

    def change_primary_device(self, device):
        from src.audio.audio_engine import audio_engine
        logger.info(f"Primary output device changed to: {device}")
        audio_engine.change_primary_device(device)
        self.update_vmic_status_label()

    def change_mic_device(self, device):
        config_manager.set("mic_device", device)
        logger.info(f"Physical Mic device changed to: {device}")
        from src.audio.audio_engine import audio_engine
        audio_engine.reload_virtual_mic()
        self.update_vmic_status_label()

    def toggle_virtual_mic(self):
        val = self.route_var.get()
        config_manager.set("virtual_mic_enabled", val)
        logger.info(f"Virtual Mic Routing toggled to: {val}")
        
        from src.audio.audio_engine import audio_engine
        audio_engine.reload_virtual_mic()
        self.update_vmic_status_label()

    def change_virtual_mic_device(self, device):
        config_manager.set("virtual_mic_device", device)
        logger.info(f"Virtual Mic device changed to: {device}")
        
        from src.audio.audio_engine import audio_engine
        audio_engine.reload_virtual_mic()
        self.update_vmic_status_label()

    def change_mic_volume(self, val):
        from src.audio.audio_engine import audio_engine
        audio_engine.set_mic_volume(val)

    def toggle_mic_mute(self):
        val = self.mic_mute_var.get()
        from src.audio.audio_engine import audio_engine
        audio_engine.set_mic_mute(val)

    def change_sbd_volume(self, val):
        from src.audio.audio_engine import audio_engine
        audio_engine.set_virtual_mic_sbd_volume(val)

    def toggle_sbd_mute(self):
        val = self.sbd_mute_var.get()
        from src.audio.audio_engine import audio_engine
        audio_engine.set_virtual_mic_sbd_mute(val)

    def test_audio_devices(self):
        from src.audio.audio_engine import audio_engine
        logger.info("Triggering audio device routing verification test.")
        audio_engine.test_device_routing()

    def on_levels_received(self, mic_level, sbd_level, latency_ms):
        def update_ui():
            if not hasattr(self, "mic_level_bar") or not self.mic_level_bar.winfo_exists():
                return
            # Square root scaling maps RMS level values (0.0 to 1.0) to a more visible range
            self.mic_level_bar.set(min(1.0, mic_level ** 0.5))
            self.sbd_level_bar.set(min(1.0, sbd_level ** 0.5))
            self.latency_lbl.configure(text=f"Buffer Latency: {latency_ms:.1f} ms")
            
        if self.winfo_exists():
            self.after(0, update_ui)

    def update_vmic_status_label(self):
        from src.audio.audio_engine import audio_engine
        enabled = config_manager.get("virtual_mic_enabled", False)
        device = config_manager.get("virtual_mic_device", "")
        devices = audio_engine.get_available_devices()
        cable_installed = any("cable" in d.lower() for d in devices)

        if not hasattr(self, "vmic_status_lbl") or not self.vmic_status_lbl.winfo_exists():
            return

        if not cable_installed:
            self.vmic_status_lbl.configure(text="● Virtual Mic: Cable Not Installed", text_color="#cf6679")
        elif not enabled:
            self.vmic_status_lbl.configure(text="● Virtual Mic: Routing Inactive (Disabled)", text_color="#8e9aaf")
        elif not device:
            self.vmic_status_lbl.configure(text="● Virtual Mic: Device Not Selected", text_color="#ffb703")
        elif audio_engine.subprocess_handle and audio_engine.subprocess_handle.poll() is None:
            self.vmic_status_lbl.configure(text="● Virtual Mic: Active & Routing", text_color="#03dac6")
        else:
            self.vmic_status_lbl.configure(text="● Virtual Mic: Routing Error (Off)", text_color="#cf6679")

    def draw_supabase_settings(self):
        # Supabase Connection Card (Cyberpunk styled)
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#bc00dd"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        label = ctk.CTkLabel(card, text="Supabase Integration", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(pady=(12, 5), padx=20, anchor="w")

        desc_label = ctk.CTkLabel(card, text="Required for authentication, storage, and cross-device sharing.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        desc_label.pack(pady=(0, 10), padx=20, anchor="w")

        # URL Input
        url_label = ctk.CTkLabel(card, text="Supabase URL:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        url_label.pack(padx=20, anchor="w")
        
        self.url_entry = ctk.CTkEntry(card, placeholder_text="https://your-project.supabase.co", width=450, height=35, corner_radius=6, fg_color="#04050a", border_color="#1a1b35")
        self.url_entry.pack(pady=(2, 10), padx=20, anchor="w")
        
        # Mask if streamer mode is active
        streamer_active = config_manager.get("streamer_mode", False)
        if streamer_active:
            self.url_entry.insert(0, "[HIDDEN (STREAMER MODE)]")
        else:
            self.url_entry.insert(0, config_manager.get("supabase_url", ""))

        # Anon Key Input
        key_label = ctk.CTkLabel(card, text="Supabase Anon Key:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#edf2f4")
        key_label.pack(padx=20, anchor="w")
        
        self.key_entry = ctk.CTkEntry(card, placeholder_text="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", show="*", width=450, height=35, corner_radius=6, fg_color="#04050a", border_color="#1a1b35")
        self.key_entry.pack(pady=(2, 12), padx=20, anchor="w")
        
        if streamer_active:
            self.key_entry.insert(0, "[HIDDEN (STREAMER MODE)]")
        else:
            self.key_entry.insert(0, config_manager.get("supabase_key", ""))

        # Real-time Sync Status Row
        self.sync_info_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.sync_info_frame.pack(fill="x", padx=20, pady=(0, 10), anchor="w")

        self.sync_status_display = ctk.CTkLabel(
            self.sync_info_frame,
            text="Sync Status: Idle",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#8e9aaf"
        )
        self.sync_status_display.pack(side="left", padx=(0, 20))

        self.last_sync_display = ctk.CTkLabel(
            self.sync_info_frame,
            text="Last Sync: Never",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#8e9aaf"
        )
        self.last_sync_display.pack(side="left")

        # Feedback and Action panel
        action_frame = ctk.CTkFrame(card, fg_color="transparent")
        action_frame.pack(fill="x", padx=20, pady=(0, 15))

        save_btn = ctk.CTkButton(
            action_frame,
            text="Save Settings",
            fg_color="#00f0ff",
            text_color="#04050a",
            hover_color="#00b8cc",
            width=110,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.save_supabase_credentials
        )
        save_btn.pack(side="left", padx=(0, 10))

        self.test_btn = ctk.CTkButton(
            action_frame,
            text="Test Connection",
            fg_color="#bc00dd",
            text_color="#ffffff",
            hover_color="#8c00aa",
            width=120,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self.run_connection_test
        )
        self.test_btn.pack(side="left", padx=10)


        self.sync_btn = ctk.CTkButton(
            action_frame,
            text="Sync Now",
            fg_color="#bc00dd",
            text_color="#ffffff",
            hover_color="#8c00aa",
            width=100,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self.manual_sync
        )
        self.sync_btn.pack(side="left", padx=10)

        self.conn_status_label = ctk.CTkLabel(
            action_frame, 
            text="", 
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.conn_status_label.pack(side="left", padx=15)

    def save_supabase_credentials(self):
        url = self.url_entry.get().strip()
        key = self.key_entry.get().strip()

        # Only save if not masked by Streamer Mode placeholder
        if url != "[HIDDEN (STREAMER MODE)]":
            config_manager.set("supabase_url", url)
        if key != "[HIDDEN (STREAMER MODE)]":
            config_manager.set("supabase_key", key)

        
        # Reset the client so next call picks up the new credentials
        reset_supabase_client()
        logger.info("Supabase credentials updated and saved.")

        self.conn_status_label.configure(text="Settings saved!", text_color="#03dac6")
        self.after(3000, lambda: self.conn_status_label.configure(text=""))
        
        # Notify controller that connection needs checking
        self.controller.check_connections()

        # Trigger sync wakeup
        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.trigger_sync()
        except Exception as e:
            logger.debug(f"Failed to trigger sync: {e}")

    def run_connection_test(self):
        self.test_btn.configure(state="disabled", text="Testing...")
        self.conn_status_label.configure(text="Connecting to API...", text_color="#bb86fc")
        
        # Run test in background thread
        def worker():
            success = test_supabase_connection()
            self.after(0, self.on_test_complete, success)
            
        threading.Thread(target=worker, daemon=True).start()

    def on_test_complete(self, success):
        self.test_btn.configure(state="normal", text="Test Connection")
        if success:
            self.conn_status_label.configure(text="Connection Successful!", text_color="#03dac6")
        else:
            self.conn_status_label.configure(text="Connection Failed (Invalid keys or offline).", text_color="#cf6679")
        
        # Update connections dashboard status
        self.controller.check_connections()

    def draw_system_settings(self):
        # Database reset Card
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#ff0055"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        label = ctk.CTkLabel(card, text="Cache Maintenance", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(pady=(12, 5), padx=20, anchor="w")

        desc_label = ctk.CTkLabel(card, text="Clear local cached sessions and configurations. Does not affect Supabase cloud database.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        desc_label.pack(pady=(0, 10), padx=20, anchor="w")

        reset_btn = ctk.CTkButton(
            card,
            text="🗑️ Clear Session Cache",
            fg_color="transparent",
            text_color="#ff0055",
            hover_color="#330011",
            border_color="#ff0055",
            border_width=1,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.clear_cache
        )
        reset_btn.pack(pady=(5, 15), padx=20, anchor="w")

    def clear_cache(self):
        clear_local_sessions()
        config_manager.set("last_session", {})
        logger.info("Cleared local session cache.")
        # If logged in, logout
        from src.auth import auth_manager
        if auth_manager.is_logged_in():
            auth_manager.sign_out()
            self.controller.on_auth_state_changed()
            
        self.controller.select_tab("auth")
        logger.info("Database cache wiped by user.")

    def draw_log_viewer(self):
        # Log viewer Card
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#bc00dd"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        title_frame = ctk.CTkFrame(card, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(12, 8))

        label = ctk.CTkLabel(title_frame, text="Application Logs", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(side="left")

        refresh_btn = ctk.CTkButton(
            title_frame,
            text="🔄 Refresh",
            width=90,
            height=24,
            fg_color="transparent",
            hover_color="#bc00dd",
            text_color="#00f0ff",
            border_color="#00f0ff",
            border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.load_logs_content
        )
        refresh_btn.pack(side="right")

        # Scrollable text widget for logs styled like a hacker terminal
        self.logs_textbox = ctk.CTkTextbox(
            card,
            width=500,
            height=180,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#04050a",
            text_color="#00f0ff",
            border_width=1,
            border_color="#1a1b35"
        )
        self.logs_textbox.pack(fill="x", padx=20, pady=(0, 15))
        self.load_logs_content()

    def load_logs_content(self):
        self.logs_textbox.configure(state="normal")
        self.logs_textbox.delete("1.0", "end")
        
        # Read app.log
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_file = os.path.join(root_dir, "logs", "app.log")
        
        if os.path.exists(log_file):
            try:
                # Read last 100 lines for efficiency
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                last_lines = lines[-100:]
                self.logs_textbox.insert("end", "".join(last_lines))
            except Exception as e:
                self.logs_textbox.insert("end", f"Failed to read logs: {e}")
        else:
            self.logs_textbox.insert("end", "Log file not created yet.")
            
        self.logs_textbox.configure(state="disabled")
        # Scroll to the end of the text box
        self.logs_textbox.see("end")

    def draw_hotkey_settings(self):
        # Global Hotkey Settings Card
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#00f0ff"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        label = ctk.CTkLabel(card, text="Global Hotkeys", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(pady=(12, 5), padx=20, anchor="w")

        desc_label = ctk.CTkLabel(card, text="Configure global keyboard bindings and panic mute actions.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        desc_label.pack(pady=(0, 10), padx=20, anchor="w")

        # Panic Mute Hotkey Row
        panic_frame = ctk.CTkFrame(card, fg_color="transparent")
        panic_frame.pack(fill="x", padx=20, pady=5)

        panic_lbl = ctk.CTkLabel(panic_frame, text="Panic Mute Hotkey (Stops all sounds):", font=ctk.CTkFont(family="Segoe UI", size=13))
        panic_lbl.pack(side="left", padx=(0, 10))

        current_panic = config_manager.get("panic_hotkey", "Escape")
        self.panic_entry = ctk.CTkEntry(panic_frame, width=150, height=30, fg_color="#04050a", border_color="#1a1b35")
        self.panic_entry.insert(0, current_panic)
        self.panic_entry.pack(side="left", padx=5)

        save_panic_btn = ctk.CTkButton(
            panic_frame,
            text="Save Key",
            width=80,
            height=30,
            fg_color="#00f0ff",
            text_color="#04050a",
            hover_color="#00b8cc",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.save_panic_hotkey
        )
        save_panic_btn.pack(side="left", padx=10)

        self.panic_feedback_lbl = ctk.CTkLabel(panic_frame, text="", font=ctk.CTkFont(family="Segoe UI", size=12))
        self.panic_feedback_lbl.pack(side="left", padx=5)

        # Active bindings list
        binds_label = ctk.CTkLabel(card, text="Active Keybindings List:", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#00f0ff")
        binds_label.pack(pady=(15, 5), padx=20, anchor="w")

        # Scrollable panel or text box to display registered keys
        self.active_binds_frame = ctk.CTkFrame(card, fg_color="#04050a", corner_radius=8, border_color="#1a1b35", border_width=1)
        self.active_binds_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.populate_active_binds()

    def populate_active_binds(self):
        # Clear existing bindings list children
        for widget in self.active_binds_frame.winfo_children():
            widget.destroy()

        from src.audio.hotkeys import hotkey_manager
        from tkinter import messagebox
        
        # Add headers
        header_frame = ctk.CTkFrame(self.active_binds_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=5)
        
        key_header = ctk.CTkLabel(header_frame, text="Hotkey Combo", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#bc00dd", width=180, anchor="w")
        key_header.pack(side="left")
        
        sound_header = ctk.CTkLabel(header_frame, text="Assigned Sound Name", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#bc00dd", anchor="w")
        sound_header.pack(side="left", fill="x", expand=True)

        # Divider
        divider = ctk.CTkFrame(self.active_binds_frame, height=1, fg_color="#1a1b35")
        divider.pack(fill="x", padx=5, pady=2)

        # List all bindings
        bindings = hotkey_manager.bindings
        if not bindings:
            no_binds_lbl = ctk.CTkLabel(self.active_binds_frame, text="No sounds currently have hotkey bindings assigned.", font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"), text_color="#8e9aaf")
            no_binds_lbl.pack(pady=10)
            return

        for norm_key, data in bindings.items():
            row_frame = ctk.CTkFrame(self.active_binds_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=10, pady=4)

            # Format raw hotkey beautifully
            raw_key = hotkey_manager.raw_hotkeys.get(data["sound_id"], norm_key)

            key_lbl = ctk.CTkLabel(row_frame, text=f"[ {raw_key} ]", font=ctk.CTkFont(family="Consolas", size=11), text_color="#00f0ff", width=180, anchor="w")
            key_lbl.pack(side="left")

            sound_lbl = ctk.CTkLabel(row_frame, text=data["sound_name"], font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#ffffff", anchor="w")
            sound_lbl.pack(side="left", fill="x", expand=True)

    def save_panic_hotkey(self):
        from tkinter import messagebox
        val = self.panic_entry.get().strip()
        if not val:
            messagebox.showwarning("Warning", "Panic hotkey cannot be empty.", parent=self.winfo_toplevel())
            return

        from src.audio.hotkeys import hotkey_manager, is_os_reserved, validate_hotkey_format
        
        # Validate format
        if not validate_hotkey_format(val):
            messagebox.showwarning(
                "Invalid Hotkey Format",
                f"The hotkey '{val}' is invalid.\nFormat example: 'Ctrl+Alt+A' or 'Escape'. Modifiers must be joined by '+' with no trailing plus.",
                parent=self.winfo_toplevel()
            )
            return

        # Check if OS reserved
        if is_os_reserved(val):
            messagebox.showwarning(
                "Reserved Hotkey",
                f"The hotkey '{val}' is reserved by the Operating System. Please choose a different shortcut.",
                parent=self.winfo_toplevel()
            )
            return

        # Check duplicate conflict with existing sounds
        conflict_id = hotkey_manager.check_conflict(val)
        conflict_name = ""
        if conflict_id and conflict_id != "panic":
            for d in hotkey_manager.bindings.values():
                if d["sound_id"] == conflict_id:
                    conflict_name = d["sound_name"]
                    break

        if conflict_id and conflict_id != "panic":
            messagebox.showwarning(
                "Hotkey Conflict",
                f"The hotkey '{val}' is already assigned to the sound '{conflict_name}'. Please assign a different hotkey to avoid conflicts.",
                parent=self.winfo_toplevel()
            )
            return

        # Save to config
        config_manager.set("panic_hotkey", val)
        logger.info(f"Saved global panic hotkey: {val}")

        # Reload hotkeys listener to apply changes
        hotkey_manager.reload()

        self.panic_feedback_lbl.configure(text="Saved!", text_color="#03dac6")
        self.after(3000, lambda: self.panic_feedback_lbl.configure(text=""))

    def update_view(self):
        """
        Refreshes settings states and updates the active keybindings list.
        """
        if hasattr(self, "active_binds_frame"):
            self.populate_active_binds()
        
        # Refresh virtual mic status label if present
        self.update_vmic_status_label()
        
        # Initialize sync status labels
        try:
            from src.sync.sync_manager import sync_manager
            self.update_sync_status(sync_manager.status, sync_manager.last_sync_time)
        except Exception:
            pass

    def manual_sync(self):
        from src.auth import auth_manager
        from tkinter import messagebox
        if not auth_manager.is_logged_in():
            messagebox.showwarning("Authentication Required", "Please log in to synchronize settings and soundboards.", parent=self.winfo_toplevel())
            return
            
        # Waking up sync manager background thread safely
        from src.sync.sync_manager import sync_manager
        sync_manager.trigger_sync()

    def update_sync_status(self, status, last_sync_time):
        """
        Observer callback triggered by SyncManager. Updates local labels thread-safely.
        """
        import time
        def update_ui():
            if not hasattr(self, "sync_status_display"):
                return
                
            if status == "syncing":
                self.sync_status_display.configure(text="Sync Status: Syncing...", text_color="#bb86fc")
                self.sync_btn.configure(state="disabled", text="Syncing...")
            elif status == "offline":
                self.sync_status_display.configure(text="Sync Status: Offline", text_color="#ffb703")
                self.sync_btn.configure(state="normal", text="Sync Now")
            elif status == "error":
                self.sync_status_display.configure(text="Sync Status: Error / Retrying", text_color="#cf6679")
                self.sync_btn.configure(state="normal", text="Sync Now")
            else: # status == "idle"
                self.sync_status_display.configure(text="Sync Status: Idle", text_color="#03dac6")
                self.sync_btn.configure(state="normal", text="Sync Now")
                self.populate_active_binds() # refresh the hotkeys list when sync completes
                
            if last_sync_time > 0:
                local_t = time.localtime(last_sync_time)
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_t)
                self.last_sync_display.configure(text=f"Last Sync: {time_str}")
            else:
                self.last_sync_display.configure(text="Last Sync: Never")

        self.after(0, update_ui)

    def draw_qr_pairing_settings(self):
        # QR Pairing & Remote Card
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#bc00dd"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        label = ctk.CTkLabel(card, text="Mobile Remote Control (QR Pairing)", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(pady=(12, 5), padx=20, anchor="w")

        desc_label = ctk.CTkLabel(card, text="Control your soundboard from a mobile browser on your local network.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        desc_label.pack(pady=(0, 15), padx=20, anchor="w")

        # Main horizontal layout: Left is QR and Right is Diagnostics
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.pack(fill="x", padx=20, pady=(0, 15))

        # QR Code display area (Left)
        self.qr_container = ctk.CTkFrame(content_frame, fg_color="#04050a", width=180, height=180, corner_radius=8, border_color="#1a1b35", border_width=1)
        self.qr_container.pack(side="left", padx=(0, 20))
        self.qr_container.pack_propagate(False)

        # Label inside container
        self.qr_label = ctk.CTkLabel(self.qr_container, text="Loading QR...")
        self.qr_label.pack(fill="both", expand=True)

        # Diagnostics frame (Right)
        diag_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        diag_frame.pack(side="left", fill="both", expand=True)

        self.remote_status_lbl = ctk.CTkLabel(diag_frame, text="Server Status: Stopped", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#ff0055", anchor="w")
        self.remote_status_lbl.pack(pady=2, anchor="w")

        self.remote_ip_lbl = ctk.CTkLabel(diag_frame, text="Local IP Address: --", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#edf2f4", anchor="w")
        self.remote_ip_lbl.pack(pady=2, anchor="w")

        self.remote_port_lbl = ctk.CTkLabel(diag_frame, text="Listening Port: --", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#edf2f4", anchor="w")
        self.remote_port_lbl.pack(pady=2, anchor="w")

        self.remote_token_lbl = ctk.CTkLabel(diag_frame, text="Security Token: [HIDDEN]", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#edf2f4", anchor="w")
        self.remote_token_lbl.pack(pady=2, anchor="w")

        self.remote_clients_lbl = ctk.CTkLabel(diag_frame, text="Connected Clients: 0", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#edf2f4", anchor="w")
        self.remote_clients_lbl.pack(pady=2, anchor="w")

        self.remote_fw_lbl = ctk.CTkLabel(diag_frame, text="Firewall Status: --", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#edf2f4", anchor="w")
        self.remote_fw_lbl.pack(pady=2, anchor="w")

        # Control buttons
        btn_frame = ctk.CTkFrame(diag_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0), anchor="w")

        self.toggle_server_btn = ctk.CTkButton(
            btn_frame,
            text="Start Remote Server",
            fg_color="#bc00dd",
            text_color="#ffffff",
            hover_color="#8c00aa",
            width=140,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self.toggle_remote_server
        )
        self.toggle_server_btn.pack(side="left", padx=(0, 10))

        self.reveal_qr_btn = ctk.CTkButton(
            btn_frame,
            text="Reveal QR Code",
            fg_color="transparent",
            text_color="#00f0ff",
            hover_color="#bc00dd",
            border_color="#00f0ff",
            border_width=1,
            width=120,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self.reveal_qr_code
        )
        self.qr_revealed = False

        self.refresh_remote_diagnostics()
        self.schedule_diagnostics_refresh()

    def toggle_remote_server(self):
        from src.api_server import APIServerManager
        manager = APIServerManager.get_instance()
        if manager.is_running:
            manager.stop()
        else:
            manager.start()
        self.qr_revealed = False
        self.refresh_remote_diagnostics()

    def reveal_qr_code(self):
        self.qr_revealed = True
        self.refresh_remote_diagnostics()

    def hide_qr_code(self):
        self.qr_revealed = False
        self.reveal_qr_btn.configure(text="Reveal QR Code", command=self.reveal_qr_code)
        self.refresh_remote_diagnostics()

    def display_qr_image(self, ip, port, token):
        try:
            import qrcode
            from PIL import Image
            pairing_url = f"http://{ip}:{port}/?token={token}"

            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=1)
            qr.add_data(pairing_url)
            qr.make(fit=True)

            # Cyberpunk styling: neon cyan modules, dark back
            img = qr.make_image(fill_color="#00f0ff", back_color="#04050a").convert("RGB")
            img = img.resize((150, 150), Image.Resampling.LANCZOS)

            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 150))
            self.qr_label.configure(image=ctk_img, text="")
            self.qr_label._qr_image = ctk_img
        except Exception as e:
            logger.error(f"Failed to render QR Code: {e}")
            self.qr_label.configure(image="", text="QR Error")

    def refresh_remote_diagnostics(self):
        from src.api_server import APIServerManager
        manager = APIServerManager.get_instance()

        is_running = manager.is_running
        ip = manager.get_local_ip()
        port = manager.port
        token = manager.token
        client_count = len(manager.active_connections)
        streamer_active = config_manager.get("streamer_mode", False)

        if is_running:
            self.remote_status_lbl.configure(text="Server Status: Active (Running)", text_color="#03dac6")
            self.toggle_server_btn.configure(text="Stop Remote Server", fg_color="#ff0055", hover_color="#cc0044")
            self.remote_ip_lbl.configure(text=f"Local IP Address: {ip}")
            self.remote_port_lbl.configure(text=f"Listening Port: {port}")
            self.remote_clients_lbl.configure(text=f"Connected Clients: {client_count}")
            self.remote_fw_lbl.configure(text="Firewall Status: Port Bound (0.0.0.0)", text_color="#03dac6")

            if streamer_active and not self.qr_revealed:
                self.remote_token_lbl.configure(text="Security Token: [HIDDEN (STREAMER MODE)]")
                self.reveal_qr_btn.pack(side="left")
                self.reveal_qr_btn.configure(text="Reveal QR Code", command=self.reveal_qr_code)
                self.qr_label.configure(image="", text="[STREAMER MODE]\nClick 'Reveal QR'\nto view")
            else:
                self.remote_token_lbl.configure(text=f"Security Token: {token}")
                if streamer_active:
                    self.reveal_qr_btn.pack(side="left")
                    self.reveal_qr_btn.configure(text="Hide QR Code", command=self.hide_qr_code)
                else:
                    self.reveal_qr_btn.pack_forget()

                self.display_qr_image(ip, port, token)
        else:
            self.remote_status_lbl.configure(text="Server Status: Stopped", text_color="#ff0055")
            self.toggle_server_btn.configure(text="Start Remote Server", fg_color="#bc00dd", hover_color="#8c00aa")
            self.remote_ip_lbl.configure(text="Local IP Address: --")
            self.remote_port_lbl.configure(text="Listening Port: --")
            self.remote_token_lbl.configure(text="Security Token: --")
            self.remote_clients_lbl.configure(text="Connected Clients: --")
            self.remote_fw_lbl.configure(text="Firewall Status: Server Offline", text_color="#edf2f4")
            self.reveal_qr_btn.pack_forget()
            self.qr_label.configure(image="", text="Server Offline")

    def schedule_diagnostics_refresh(self):
        if self.winfo_exists():
            self.refresh_remote_diagnostics()
            self.after(2000, self.schedule_diagnostics_refresh)

    def draw_about_settings(self):
        # About Card
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#111222", corner_radius=12, border_color="#1a1b35", border_width=1)
        card.pack(fill="x", pady=10)

        # Bind hover border animation
        card.bind("<Enter>", lambda e, c=card: c.configure(border_color="#00f0ff"))
        card.bind("<Leave>", lambda e, c=card: c.configure(border_color="#1a1b35"))

        label = ctk.CTkLabel(card, text="About ErosSoundX", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        label.pack(pady=(12, 5), padx=20, anchor="w")

        desc_label = ctk.CTkLabel(card, text="Premium cyberpunk soundboard application with offline-first synchronization and mobile remote capabilities.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf")
        desc_label.pack(pady=(0, 15), padx=20, anchor="w")

        # Details Layout
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=(0, 15))

        version_lbl = ctk.CTkLabel(info_frame, text="App Version: 1.0.0 (Release Build)", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#ffffff", anchor="w")
        version_lbl.pack(pady=1, anchor="w")

        license_lbl = ctk.CTkLabel(info_frame, text="License: MIT License", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf", anchor="w")
        license_lbl.pack(pady=1, anchor="w")

        credits_lbl = ctk.CTkLabel(info_frame, text="Built by: Google DeepMind team and paired with Antigravity AI", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8e9aaf", anchor="w")
        credits_lbl.pack(pady=1, anchor="w")

        from src.database.sqlite_db import DB_PATH
        db_path_lbl = ctk.CTkLabel(info_frame, text=f"Local DB Path: {DB_PATH}", font=ctk.CTkFont(family="Consolas", size=10), text_color="#00f0ff", anchor="w")
        db_path_lbl.pack(pady=(10, 0), anchor="w")

