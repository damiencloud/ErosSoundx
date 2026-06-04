import os
import customtkinter as ctk
import threading
from tkinter import filedialog, messagebox
from src.soundboard_manager import soundboard_manager
from src.logger import logger

class SoundboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        self.active_board_id = None  # None, "favorites", or UUID of a soundboard
        self.active_board_name = ""
        self.play_indicators = {}    # Maps sound_id to CTkLabel for status indicator

        # --- LAYOUT SPLIT ---
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 1. Top Panel (Soundboard Tabs & Controls)
        self.top_panel = ctk.CTkFrame(self, fg_color="#111222", height=60, corner_radius=10, border_color="#1a1b35", border_width=1)
        self.top_panel.grid(row=0, column=0, sticky="ew", padx=25, pady=(25, 10))
        self.top_panel.grid_propagate(False)

        # Scrollable container for tabs
        self.tabs_scroll = ctk.CTkScrollableFrame(self.top_panel, fg_color="transparent", orientation="horizontal", height=45)
        self.tabs_scroll.pack(side="left", fill="both", expand=True, padx=10, pady=5)

        # Tab management buttons frame
        self.tab_buttons_frame = ctk.CTkFrame(self.tabs_scroll, fg_color="transparent")
        self.tab_buttons_frame.pack(fill="both", expand=True)

        # Board Action Controls (Rename/Delete)
        self.board_actions_frame = ctk.CTkFrame(self.top_panel, fg_color="transparent")
        self.board_actions_frame.pack(side="right", padx=10, pady=10)

        # 2. Main Sound Cards Grid
        self.grid_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.grid_scroll.grid(row=1, column=0, sticky="nsew", padx=25, pady=(0, 25))
        
        # Grid layout parameters
        self.grid_scroll.grid_columnconfigure((0, 1, 2), weight=1, minsize=180)

        # Cache reference lists for tabs and card elements
        self.tab_elements = {}

        self.update_view()
        self.check_active_playbacks()

    def check_active_playbacks(self):
        """
        Periodically polls the active playbacks and updates status dots in real-time.
        """
        if self.winfo_exists():
            from src.audio.audio_engine import audio_engine
            for sound_id, lbl in list(self.play_indicators.items()):
                try:
                    if lbl.winfo_exists():
                        if audio_engine.is_playing(sound_id):
                            lbl.configure(text="● PLAYING", text_color="#03dac6")
                        else:
                            lbl.configure(text="● IDLE", text_color="#8e9aaf")
                except Exception:
                    pass
            self.after(200, self.check_active_playbacks)

    def update_view(self):
        """
        Reloads soundboard list and redraws the tabs.
        """
        logger.debug("Refreshing Soundboard view lists.")
        # Clear existing tabs
        for widget in self.tab_buttons_frame.winfo_children():
            widget.destroy()
        self.tab_elements.clear()

        # Fetch soundboards
        boards = soundboard_manager.get_boards()

        # Render "Favorites" Virtual Tab first
        self.create_tab_button("favorites", "★ Favorites", is_virtual=True)

        # Render User Tabs
        for b in boards:
            self.create_tab_button(
                b["id"],
                b["name"],
                category=b.get("category", "General"),
                is_favorite=b.get("is_favorite", 0) == 1
            )

        # Add Board (+) Tab button
        add_board_btn = ctk.CTkButton(
            self.tab_buttons_frame,
            text="+ Add Board",
            width=90,
            height=30,
            fg_color="transparent",
            text_color="#00f0ff",
            hover=False,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.open_create_board_dialog
        )
        add_board_btn.pack(side="left", padx=5)

        import_board_btn = ctk.CTkButton(
            self.tab_buttons_frame,
            text="📥 Import Board",
            width=100,
            height=30,
            fg_color="transparent",
            text_color="#03dac6",
            hover=False,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.import_soundboard_pack
        )
        import_board_btn.pack(side="left", padx=5)

        # Determine active tab selection
        if not self.active_board_id:
            self.select_tab("favorites")
        else:
            # Check if active board still exists, otherwise default to favorites
            exists = any(b["id"] == self.active_board_id for b in boards) or self.active_board_id == "favorites"
            if exists:
                self.select_tab(self.active_board_id)
            else:
                self.select_tab("favorites")

    def create_tab_button(self, board_id, name, is_virtual=False, category="", is_favorite=False):
        """
        Renders a single tab button in the horizontal tab bar.
        """
        if is_virtual:
            display_text = name
        else:
            star = "★ " if is_favorite else ""
            cat_suffix = f" [{category}]" if category and category != "General" else ""
            display_text = f"{star}{name}{cat_suffix}"

        btn = ctk.CTkButton(
            self.tab_buttons_frame,
            text=display_text,
            width=100,
            height=30,
            corner_radius=6,
            fg_color="transparent",
            text_color="#edf2f4",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self.select_tab(board_id)
        )
        btn.pack(side="left", padx=4)
        self.tab_elements[board_id] = btn

    def select_tab(self, board_id):
        self.active_board_id = board_id

        # Update visual highlight of tab buttons
        for bid, btn in self.tab_elements.items():
            if bid == board_id:
                btn.configure(fg_color="#111222", text_color="#00f0ff", border_color="#00f0ff", border_width=1)
            else:
                btn.configure(fg_color="transparent", text_color="#edf2f4", border_width=0)

        # Set board name metadata
        if board_id == "favorites":
            self.active_board_name = "Favorites"
        else:
            boards = soundboard_manager.get_boards()
            active_board = next((b for b in boards if b["id"] == board_id), None)
            self.active_board_name = active_board["name"] if active_board else "General"

        # Update tab-action controls (hide rename/delete/favorite if in Favorites virtual tab)
        for w in self.board_actions_frame.winfo_children():
            w.destroy()

        if board_id != "favorites":
            boards = soundboard_manager.get_boards()
            active_board = next((b for b in boards if b["id"] == board_id), None)
            current_is_favorite = active_board.get("is_favorite", 0) == 1 if active_board else False

            fav_label = "★ Unfavorite" if current_is_favorite else "☆ Favorite"
            fav_fg    = "#111222"
            fav_hover = "#bc00dd" if current_is_favorite else "#00f0ff"
            fav_tc    = "#ffb703" if current_is_favorite else "#edf2f4"

            fav_btn = ctk.CTkButton(
                self.board_actions_frame,
                text=fav_label,
                width=95,
                height=26,
                fg_color=fav_fg,
                text_color=fav_tc,
                hover_color=fav_hover,
                border_color="#1a1b35",
                border_width=1,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=lambda bid=board_id, fav=current_is_favorite: self.toggle_board_favorite(bid, not fav)
            )
            fav_btn.pack(side="left", padx=4)

            rename_btn = ctk.CTkButton(
                self.board_actions_frame,
                text="Rename",
                width=65,
                height=26,
                fg_color="#111222",
                hover_color="#bc00dd",
                text_color="#edf2f4",
                border_color="#1a1b35",
                border_width=1,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=self.open_rename_board_dialog
            )
            rename_btn.pack(side="left", padx=4)

            delete_btn = ctk.CTkButton(
                self.board_actions_frame,
                text="Delete",
                width=65,
                height=26,
                fg_color="#111222",
                text_color="#ff0055",
                hover_color="#ff0055",
                border_color="#ff0055",
                border_width=1,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=self.open_delete_board_dialog
            )
            delete_btn.pack(side="left", padx=4)

            export_btn = ctk.CTkButton(
                self.board_actions_frame,
                text="Export Pack",
                width=80,
                height=26,
                fg_color="#111222",
                text_color="#03dac6",
                hover_color="#03dac6",
                border_color="#1a1b35",
                border_width=1,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=self.export_soundboard_pack
            )
            export_btn.pack(side="left", padx=4)

        # Redraw sound card grid
        self.load_sound_grid()

    def toggle_board_favorite(self, board_id: str, new_state: bool):
        if not board_id or board_id == "favorites":
            return
        soundboard_manager.toggle_board_favorite(board_id, new_state)
        self.update_view()

    def load_sound_grid(self):
        """Clears and redraws the sound card grid for the active tab."""
        for widget in self.grid_scroll.winfo_children():
            widget.destroy()
        self.play_indicators.clear()

        # Fetch sound data
        if self.active_board_id == "favorites":
            sounds = soundboard_manager.get_favorites()
        else:
            sounds = soundboard_manager.get_board_sounds(self.active_board_id)

        # --- Empty State ---
        if not sounds and self.active_board_id != "favorites":
            empty_frame = ctk.CTkFrame(self.grid_scroll, fg_color="transparent")
            empty_frame.grid(row=0, column=0, columnspan=3, pady=60, sticky="nsew")

            ctk.CTkLabel(
                empty_frame,
                text="🎵",
                font=ctk.CTkFont(size=48),
                text_color="#1a1b35"
            ).pack(pady=(0, 12))
            ctk.CTkLabel(
                empty_frame,
                text="No sounds yet",
                font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                text_color="#8e9aaf"
            ).pack()
            ctk.CTkLabel(
                empty_frame,
                text="Click  + Add Sound  to add your first MP3 or WAV file.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#5c6272"
            ).pack(pady=(4, 20))
            ctk.CTkButton(
                empty_frame,
                text="+ Add Sound",
                width=140,
                height=38,
                fg_color="#00f0ff",
                text_color="#04050a",
                hover_color="#00b8cc",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                command=self.open_add_sound_dialog
            ).pack()
            return

        if not sounds and self.active_board_id == "favorites":
            empty_frame = ctk.CTkFrame(self.grid_scroll, fg_color="transparent")
            empty_frame.grid(row=0, column=0, columnspan=3, pady=60)
            ctk.CTkLabel(
                empty_frame,
                text="No favorite sounds yet",
                font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                text_color="#8e9aaf"
            ).pack()
            ctk.CTkLabel(
                empty_frame,
                text="Star a sound on any board to pin it here.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#5c6272"
            ).pack(pady=(4, 0))
            return

        # Draw sound cards
        row = 0
        col = 0
        for s in sounds:
            card = self.create_sound_card(s)
            card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")
            col += 1
            if col > 2:
                col = 0
                row += 1

        # Add Sound card (bottom-right of grid, non-favorites tabs only)
        if self.active_board_id != "favorites":
            add_card = ctk.CTkFrame(
                self.grid_scroll,
                fg_color="#111222",
                corner_radius=10,
                border_color="#1a1b35",
                border_width=1,
                height=190
            )
            add_card.grid_propagate(False)
            add_card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")
            
            # Hover effect for Add Card border
            add_card.bind("<Enter>", lambda e: add_card.configure(border_color="#bc00dd"))
            add_card.bind("<Leave>", lambda e: add_card.configure(border_color="#1a1b35"))
            
            add_btn = ctk.CTkButton(
                add_card,
                text="+ Add Sound",
                fg_color="transparent",
                hover=False,
                text_color="#00f0ff",
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                command=self.open_add_sound_dialog
            )
            add_btn.place(relx=0.5, rely=0.5, anchor="center")
            
            add_card.bind("<Button-1>", lambda e: self.open_add_sound_dialog())

    def create_sound_card(self, sound) -> ctk.CTkFrame:
        """
        Builds one sound card widget with Play/Stop buttons and a volume slider.
        """
        card = ctk.CTkFrame(
            self.grid_scroll,
            fg_color="#111222",
            corner_radius=10,
            border_color="#1a1b35",
            border_width=1,
            height=190
        )
        card.grid_propagate(False)

        card.bind("<Enter>", lambda e: card.configure(border_color="#00f0ff"))
        card.bind("<Leave>", lambda e: card.configure(border_color="#1a1b35"))

        # --- Sound Name Row ---
        title_frame = ctk.CTkFrame(card, fg_color="transparent")
        title_frame.pack(fill="x", padx=14, pady=(12, 0))

        title = ctk.CTkLabel(
            title_frame,
            text=sound["name"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#ffffff",
            anchor="w",
            wraplength=120
        )
        title.pack(side="left")

        indicator = ctk.CTkLabel(
            title_frame,
            text="● IDLE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#8e9aaf"
        )
        indicator.pack(side="right")
        self.play_indicators[sound["id"]] = indicator

        # --- File type + duration row ---
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=14, pady=(3, 0))

        _, ext = os.path.splitext(sound.get("file_path", ""))
        type_badge = ctk.CTkLabel(
            info_frame,
            text=ext.upper().lstrip(".") if ext else "?",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color="#ffffff",
            fg_color="#bc00dd",
            corner_radius=4,
            width=32,
            height=16
        )
        type_badge.pack(side="left", padx=(0, 6))

        dur = sound.get("duration", 0.0) or 0.0
        if dur > 0:
            mins = int(dur) // 60
            secs = int(dur) % 60
            dur_str = f"{mins}:{secs:02d}"
        else:
            dur_str = "--:--"

        ctk.CTkLabel(
            info_frame,
            text=dur_str,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#8e9aaf"
        ).pack(side="left")

        # --- Volume slider row ---
        volume_frame = ctk.CTkFrame(card, fg_color="transparent")
        volume_frame.pack(fill="x", padx=14, pady=(8, 0))

        vol_val = sound.get("volume", 1.0)
        vol_label = ctk.CTkLabel(
            volume_frame,
            text=f"Vol: {int(vol_val * 100)}%",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#8e9aaf",
            width=48,
            anchor="w"
        )
        vol_label.pack(side="left")

        vol_slider = ctk.CTkSlider(
            volume_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            height=14,
            button_color="#00f0ff",
            progress_color="#bc00dd",
            button_hover_color="#00b8cc",
            command=lambda val, sid=sound["id"], lbl=vol_label: self.on_slider_drag(sid, val, lbl)
        )
        vol_slider.set(vol_val)
        vol_slider.pack(side="left", fill="x", expand=True, padx=(4, 0))
        vol_slider.bind("<ButtonRelease-1>", lambda e, sid=sound["id"], slider=vol_slider: self.on_slider_release(sid, slider.get()))

        # --- Playback and Action buttons ---
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=14, pady=(12, 8))

        # Play button (Cyan Cyber Accent)
        play_btn = ctk.CTkButton(
            btn_frame,
            text="▶",
            width=38,
            height=28,
            fg_color="#00f0ff",
            text_color="#04050a",
            hover_color="#00b8cc",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda s=sound: self.play_sound(s)
        )
        play_btn.pack(side="left", padx=(0, 4))

        # Stop button (Hot Pink Panic Accent)
        stop_btn = ctk.CTkButton(
            btn_frame,
            text="■",
            width=38,
            height=28,
            fg_color="#ff0055",
            text_color="#ffffff",
            hover_color="#cc0044",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda s=sound: self.stop_sound(s)
        )
        stop_btn.pack(side="left", padx=(0, 4))

        # Favorite star
        is_fav = sound.get("is_favorite", 0) == 1
        fav_btn = ctk.CTkButton(
            btn_frame,
            text="★" if is_fav else "☆",
            width=28,
            height=28,
            fg_color="transparent",
            text_color="#ffb703" if is_fav else "#8e9aaf",
            hover=False,
            font=ctk.CTkFont(size=15),
            command=lambda s=sound: self.toggle_sound_favorite(s)
        )
        fav_btn.pack(side="left", padx=(0, 4))

        # Edit button (Move / Delete / Rename)
        edit_btn = ctk.CTkButton(
            btn_frame,
            text="Edit",
            width=48,
            height=28,
            fg_color="#111222",
            text_color="#edf2f4",
            hover_color="#bc00dd",
            border_color="#1a1b35",
            border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda s=sound: self.open_edit_sound_dialog(s)
        )
        edit_btn.pack(side="right")

        return card

    def on_slider_drag(self, sound_id: str, val: float, label: ctk.CTkLabel):
        from src.audio.audio_engine import audio_engine
        audio_engine.set_sound_volume(sound_id, val)
        label.configure(text=f"Vol: {int(val * 100)}%")

    def on_slider_release(self, sound_id: str, val: float):
        import threading
        def update_db():
            soundboard_manager.update_sound_volume(sound_id, val)
        threading.Thread(target=update_db, daemon=True).start()

    def play_sound(self, sound):
        from src.audio.audio_engine import audio_engine
        audio_engine.play_sound(
            sound_id=sound["id"],
            file_path=sound["file_path"],
            volume=sound.get("volume", 1.0)
        )

    def stop_sound(self, sound):
        from src.audio.audio_engine import audio_engine
        audio_engine.stop_sound(sound["id"])

    def toggle_sound_favorite(self, sound):
        new_state = not (sound.get("is_favorite", 0) == 1)
        soundboard_manager.toggle_favorite(sound["id"], new_state)
        self.load_sound_grid()

    # --- MODALS / DIALOGS ---

    def open_create_board_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Create Soundboard")
        dialog.geometry("340x220")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(fg_color="#111222")

        x = self.winfo_toplevel().winfo_x() + 200
        y = self.winfo_toplevel().winfo_y() + 150
        dialog.geometry(f"+{x}+{y}")

        title = ctk.CTkLabel(dialog, text="New Soundboard", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        title.pack(pady=(15, 10))

        name_entry = ctk.CTkEntry(dialog, placeholder_text="Soundboard Name", width=260, height=35, fg_color="#04050a", border_color="#1a1b35")
        name_entry.pack(pady=8)

        cat_entry = ctk.CTkEntry(dialog, placeholder_text="Category (e.g. Gaming, Memes)", width=260, height=35, fg_color="#04050a", border_color="#1a1b35")
        cat_entry.pack(pady=8)

        def save():
            name = name_entry.get().strip()
            cat = cat_entry.get().strip() or "General"
            if name:
                soundboard_manager.create_board(name, cat)
                dialog.destroy()
                self.update_view()
            else:
                messagebox.showwarning("Warning", "Soundboard name cannot be empty.", parent=dialog)

        btn = ctk.CTkButton(dialog, text="Create", fg_color="#00f0ff", text_color="#04050a", hover_color="#00b8cc", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), command=save)
        btn.pack(pady=12)

    def open_rename_board_dialog(self):
        if not self.active_board_id or self.active_board_id == "favorites":
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Rename Soundboard")
        dialog.geometry("340x220")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(fg_color="#111222")

        x = self.winfo_toplevel().winfo_x() + 200
        y = self.winfo_toplevel().winfo_y() + 150
        dialog.geometry(f"+{x}+{y}")

        title = ctk.CTkLabel(dialog, text="Edit Soundboard", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#00f0ff")
        title.pack(pady=(15, 10))

        name_entry = ctk.CTkEntry(dialog, placeholder_text="New Name", width=260, height=35, fg_color="#04050a", border_color="#1a1b35")
        name_entry.pack(pady=8)
        name_entry.insert(0, self.active_board_name)

        boards = soundboard_manager.get_boards()
        active_board = next((b for b in boards if b["id"] == self.active_board_id), None)
        active_cat = active_board["category"] if active_board else "General"

        cat_entry = ctk.CTkEntry(dialog, placeholder_text="New Category", width=260, height=35, fg_color="#04050a", border_color="#1a1b35")
        cat_entry.pack(pady=8)
        cat_entry.insert(0, active_cat)

        def save():
            name = name_entry.get().strip()
            cat = cat_entry.get().strip() or "General"
            if name:
                soundboard_manager.rename_board(self.active_board_id, name)
                soundboard_manager.update_board_category(self.active_board_id, cat)
                dialog.destroy()
                self.update_view()
            else:
                messagebox.showwarning("Warning", "Soundboard name cannot be empty.", parent=dialog)

        btn = ctk.CTkButton(dialog, text="Update", fg_color="#00f0ff", text_color="#04050a", hover_color="#00b8cc", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), command=save)
        btn.pack(pady=12)

    def open_delete_board_dialog(self):
        if not self.active_board_id or self.active_board_id == "favorites":
            return

        confirm = messagebox.askyesno(
            "Confirm Delete", 
            f"Are you sure you want to delete soundboard '{self.active_board_name}'? All sound metadata inside will be deleted.",
            parent=self.winfo_toplevel()
        )
        if confirm:
            soundboard_manager.delete_board(self.active_board_id)
            self.active_board_id = None
            self.update_view()

    def open_add_sound_dialog(self):
        """Dialog to add an MP3 or WAV file to the active soundboard."""
        if not self.active_board_id or self.active_board_id == "favorites":
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Sound")
        dialog.geometry("400x260")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(fg_color="#111222")
        dialog.geometry(f"+{self.winfo_toplevel().winfo_x() + 200}+{self.winfo_toplevel().winfo_y() + 150}")

        ctk.CTkLabel(
            dialog,
            text="Add Sound",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#00f0ff"
        ).pack(pady=(18, 10))

        name_entry = ctk.CTkEntry(dialog, placeholder_text="Sound Name", width=320, height=35, fg_color="#04050a", border_color="#1a1b35")
        name_entry.pack(pady=6)

        file_row = ctk.CTkFrame(dialog, fg_color="transparent")
        file_row.pack(pady=6, fill="x", padx=40)

        path_entry = ctk.CTkEntry(file_row, placeholder_text="No file selected…", width=220, height=35, fg_color="#04050a", border_color="#1a1b35")
        path_entry.pack(side="left", padx=(0, 8))

        def pick_file():
            path = filedialog.askopenfilename(
                title="Select Audio File",
                filetypes=[("Audio Files", "*.mp3 *.wav"), ("MP3", "*.mp3"), ("WAV", "*.wav")]
            )
            if path:
                path_entry.delete(0, "end")
                path_entry.insert(0, path)
                if not name_entry.get().strip():
                     base = os.path.splitext(os.path.basename(path))[0]
                     name_entry.insert(0, base)

        ctk.CTkButton(
            file_row, text="Browse", width=90, height=35,
            fg_color="#bc00dd", hover_color="#8c00aa", text_color="#ffffff",
            command=pick_file
        ).pack(side="left")

        def save():
            name = name_entry.get().strip()
            path = path_entry.get().strip()
            if not name:
                messagebox.showwarning("Warning", "Sound name cannot be empty.", parent=dialog)
                return
            if not path or not os.path.exists(path):
                messagebox.showwarning("Warning", "Please select a valid MP3 or WAV file.", parent=dialog)
                return
            _, ext = os.path.splitext(path)
            if ext.lower() not in (".mp3", ".wav"):
                messagebox.showwarning("Warning", "Only MP3 and WAV files are supported.", parent=dialog)
                return
            soundboard_manager.add_sound_card(self.active_board_id, name, path)
            dialog.destroy()
            self.load_sound_grid()

        ctk.CTkButton(
            dialog, text="Add Sound",
            fg_color="#00f0ff", text_color="#04050a", hover_color="#00b8cc",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=save
        ).pack(pady=14)

    def open_rename_sound_dialog(self, sound):
        """Inline rename dialog — focused, single-purpose."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Rename Sound")
        dialog.geometry("340x170")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(fg_color="#111222")
        dialog.geometry(f"+{self.winfo_toplevel().winfo_x() + 200}+{self.winfo_toplevel().winfo_y() + 180}")

        ctk.CTkLabel(
            dialog,
            text="Rename Sound",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#00f0ff"
        ).pack(pady=(18, 10))

        name_entry = ctk.CTkEntry(dialog, placeholder_text="New name", width=280, height=35, fg_color="#04050a", border_color="#1a1b35")
        name_entry.pack(pady=6)
        name_entry.insert(0, sound["name"])
        name_entry.focus()

        def save():
            new_name = name_entry.get().strip()
            if not new_name:
                messagebox.showwarning("Warning", "Name cannot be empty.", parent=dialog)
                return
            soundboard_manager.rename_sound(sound["id"], new_name)
            dialog.destroy()
            self.load_sound_grid()

        ctk.CTkButton(
            dialog, text="Rename",
            fg_color="#00f0ff", text_color="#04050a", hover_color="#00b8cc",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=save
        ).pack(pady=10)

    def open_edit_sound_dialog(self, sound):
        """
        Edit dialog for a sound card.
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Sound")
        dialog.geometry("360x280")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(fg_color="#111222")
        dialog.geometry(f"+{self.winfo_toplevel().winfo_x() + 200}+{self.winfo_toplevel().winfo_y() + 150}")

        ctk.CTkLabel(
            dialog,
            text=f"Edit: {sound['name']}",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#00f0ff"
        ).pack(pady=(18, 6))

        dur = sound.get("duration", 0.0) or 0.0
        dur_str = f"{int(dur)//60}:{int(dur)%60:02d}" if dur > 0 else "unknown"
        _, ext = os.path.splitext(sound.get("file_path", ""))
        ctk.CTkLabel(
            dialog,
            text=f"{ext.upper().lstrip('.')}  ·  {dur_str}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#8e9aaf"
        ).pack(pady=(0, 14))

        # Move to Board section
        ctk.CTkLabel(
            dialog,
            text="Move to Board",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#edf2f4"
        ).pack(anchor="w", padx=40)

        boards = soundboard_manager.get_boards()
        other_boards = [b for b in boards if b["id"] != sound.get("soundboard_id")]
        board_names  = [b["name"] for b in other_boards]

        board_var = ctk.StringVar(value=board_names[0] if board_names else "(no other boards)")
        board_menu = ctk.CTkOptionMenu(
            dialog,
            values=board_names if board_names else ["(no other boards)"],
            variable=board_var,
            width=280,
            fg_color="#04050a",
            button_color="#bc00dd",
            button_hover_color="#8c00aa",
            dropdown_fg_color="#111222"
        )
        board_menu.pack(pady=6)

        def move():
            selected_name = board_var.get()
            target = next((b for b in other_boards if b["name"] == selected_name), None)
            if not target:
                messagebox.showwarning("Warning", "Please select a valid destination board.", parent=dialog)
                return
            soundboard_manager.move_sound(sound["id"], target["id"])
            dialog.destroy()
            self.load_sound_grid()

        move_btn = ctk.CTkButton(
            dialog, text="Move",
            width=120, height=30,
            fg_color="#bc00dd", hover_color="#8c00aa", text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="normal" if board_names else "disabled",
            command=move
        )
        move_btn.pack(pady=(4, 14))

        # Action buttons row (Rename and Delete)
        action_row = ctk.CTkFrame(dialog, fg_color="transparent")
        action_row.pack(fill="x", padx=40, pady=(0, 12))

        def rename():
            dialog.destroy()
            self.open_rename_sound_dialog(sound)

        rename_btn = ctk.CTkButton(
            action_row, text="Rename...",
            width=135, height=32,
            fg_color="#04050a", hover_color="#bc00dd", text_color="#edf2f4",
            border_color="#1a1b35", border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=rename
        )
        rename_btn.pack(side="left", padx=(0, 10))

        def delete():
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Delete '{sound['name']}'? This cannot be undone.",
                parent=dialog
            )
            if confirm:
                soundboard_manager.remove_sound_card(sound["id"])
                dialog.destroy()
                self.load_sound_grid()

        delete_btn = ctk.CTkButton(
            action_row, text="Delete",
            width=135, height=32,
            fg_color="#04050a", text_color="#ff0055", hover_color="#ff0055",
            border_color="#ff0055", border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=delete
        )
        delete_btn.pack(side="left")

    def export_soundboard_pack(self):
        if not self.active_board_id or self.active_board_id == "favorites":
            return
            
        file_path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title="Export Soundboard Package",
            defaultextension=".sbx",
            filetypes=[("SoundboardX Package", "*.sbx")],
            initialfile=f"{self.active_board_name}.sbx"
        )
        if not file_path:
            return
            
        from src.pack_manager import PackManager
        success = PackManager.export_pack(self.active_board_id, file_path)
        if success:
            messagebox.showinfo("Export Successful", f"Soundboard exported successfully to:\n{file_path}", parent=self.winfo_toplevel())
        else:
            messagebox.showerror("Export Failed", "Failed to export soundboard package.", parent=self.winfo_toplevel())

    def import_soundboard_pack(self):
        file_path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Import Soundboard Package",
            filetypes=[("SoundboardX Package", "*.sbx")]
        )
        if not file_path:
            return

        progress_win = ctk.CTkToplevel(self.winfo_toplevel())
        progress_win.title("Importing...")
        progress_win.geometry("300x120")
        progress_win.resizable(False, False)
        progress_win.transient(self.winfo_toplevel())
        progress_win.grab_set()
        progress_win.configure(fg_color="#111222")
        
        parent_x = self.winfo_toplevel().winfo_x()
        parent_y = self.winfo_toplevel().winfo_y()
        parent_w = self.winfo_toplevel().winfo_width()
        parent_h = self.winfo_toplevel().winfo_height()
        x = parent_x + (parent_w // 2) - 150
        y = parent_y + (parent_h // 2) - 60
        progress_win.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(progress_win, text="Importing package assets...", font=ctk.CTkFont(family="Segoe UI", size=13))
        lbl.pack(pady=(15, 5))
        
        progress_bar = ctk.CTkProgressBar(progress_win, width=220, progress_color="#00f0ff")
        progress_bar.set(0.0)
        progress_bar.pack(pady=10)
        
        def update_progress(pct):
            progress_bar.set(pct / 100.0)
            progress_win.update_idletasks()
            
        def run_import():
            from src.pack_manager import PackManager
            success = PackManager.import_pack(file_path, progress_callback=update_progress)
            
            def on_complete():
                progress_win.destroy()
                if success:
                    messagebox.showinfo("Import Successful", "Soundboard package imported successfully!", parent=self.winfo_toplevel())
                    self.update_view()
                else:
                    messagebox.showerror("Import Failed", "Failed to import package. Verify archive is not corrupt.", parent=self.winfo_toplevel())
            
            self.after(0, on_complete)

        threading.Thread(target=run_import, daemon=True).start()
