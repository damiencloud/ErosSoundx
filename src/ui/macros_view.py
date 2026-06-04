import os
import customtkinter as ctk
import uuid
from tkinter import messagebox, simpledialog
from src.logger import logger
from src.auth import auth_manager
from src.database.sqlite_db import (
    get_macros, create_macro, delete_macro, rename_macro,
    get_macro_steps, clear_macro_steps, add_macro_step
)
from src.soundboard_manager import soundboard_manager
from src.macro_manager import macro_manager

class MacrosView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.selected_macro_id = None
        self.local_steps = []  # List of dicts representing the steps currently in the UI editor

        # Main layouts: Grid with left sidebar (macros list) and right content (editor)
        self.grid_columnconfigure(0, weight=1, minsize=240)
        self.grid_columnconfigure(1, weight=2, minsize=450)
        self.grid_rowconfigure(0, weight=1)

        # 1. Left Sidebar: Macros List Panel
        self.left_panel = ctk.CTkFrame(self, fg_color="#111222", border_color="#1a1b35", border_width=1, corner_radius=12)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(30, 10), pady=20)
        
        list_title = ctk.CTkLabel(
            self.left_panel, 
            text="Macros List", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#00f0ff"
        )
        list_title.pack(pady=(15, 10), padx=15, anchor="w")

        # Create Macro Button
        self.create_btn = ctk.CTkButton(
            self.left_panel,
            text="+ New Macro",
            fg_color="#bc00dd",
            text_color="#ffffff",
            hover_color="#8c00aa",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.create_new_macro
        )
        self.create_btn.pack(fill="x", padx=15, pady=(0, 10))

        # Scrollable container for macro list items
        self.macro_list_scroll = ctk.CTkScrollableFrame(self.left_panel, fg_color="transparent")
        self.macro_list_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # 2. Right Panel: Macro Steps Editor
        self.right_panel = ctk.CTkFrame(self, fg_color="#111222", border_color="#1a1b35", border_width=1, corner_radius=12)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 30), pady=20)
        
        self.editor_welcome = ctk.CTkLabel(
            self.right_panel,
            text="Select or create a macro from the list to start editing.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#8e9aaf"
        )
        self.editor_welcome.pack(fill="both", expand=True)

        # Editor UI container (hidden initially)
        self.editor_container = ctk.CTkFrame(self.right_panel, fg_color="transparent")

        # Title / Name row
        self.editor_header = ctk.CTkFrame(self.editor_container, fg_color="transparent")
        self.editor_header.pack(fill="x", padx=20, pady=(15, 10))

        self.macro_name_label = ctk.CTkLabel(
            self.editor_header, 
            text="Edit Macro", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#00f0ff"
        )
        self.macro_name_label.pack(side="left")

        self.rename_btn = ctk.CTkButton(
            self.editor_header,
            text="Rename",
            width=70,
            height=25,
            fg_color="#04050a",
            border_color="#00f0ff",
            border_width=1,
            text_color="#00f0ff",
            hover_color="#bc00dd",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self.rename_current_macro
        )
        self.rename_btn.pack(side="left", padx=10)

        self.delete_btn = ctk.CTkButton(
            self.editor_header,
            text="Delete Macro",
            width=90,
            height=25,
            fg_color="transparent",
            text_color="#ff0055",
            hover_color="#ff0055",
            border_color="#ff0055",
            border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.delete_current_macro
        )
        self.delete_btn.pack(side="right")

        # Action panel (buttons to add steps)
        self.actions_bar = ctk.CTkFrame(self.editor_container, fg_color="transparent")
        self.actions_bar.pack(fill="x", padx=20, pady=(0, 10))

        self.add_play_btn = ctk.CTkButton(
            self.actions_bar,
            text="+ Play Sound Step",
            width=130,
            height=28,
            fg_color="#04050a",
            border_color="#1a1b35",
            border_width=1,
            text_color="#edf2f4",
            hover_color="#bc00dd",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self.add_play_step
        )
        self.add_play_btn.pack(side="left", padx=(0, 10))

        self.add_delay_btn = ctk.CTkButton(
            self.actions_bar,
            text="+ Delay Step",
            width=100,
            height=28,
            fg_color="#04050a",
            border_color="#1a1b35",
            border_width=1,
            text_color="#edf2f4",
            hover_color="#bc00dd",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self.add_delay_step
        )
        self.add_delay_btn.pack(side="left")

        self.test_macro_btn = ctk.CTkButton(
            self.actions_bar,
            text="▶ Play Macro",
            width=110,
            height=28,
            fg_color="#03dac6",
            text_color="#04050a",
            hover_color="#01a896",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.play_current_macro
        )
        self.test_macro_btn.pack(side="right")

        # Scrollable container for the steps
        self.steps_scroll = ctk.CTkScrollableFrame(self.editor_container, fg_color="#04050a", border_color="#1a1b35", border_width=1, corner_radius=8)
        self.steps_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Bottom save/cancel info
        self.save_bar = ctk.CTkFrame(self.editor_container, fg_color="transparent")
        self.save_bar.pack(fill="x", padx=20, pady=(0, 15))

        self.save_info_lbl = ctk.CTkLabel(
            self.save_bar, 
            text="Changes save automatically.", 
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"), 
            text_color="#8e9aaf"
        )
        self.save_info_lbl.pack(side="left")

        # Bind hover effects on panels
        self.left_panel.bind("<Enter>", lambda e: self.left_panel.configure(border_color="#bc00dd"))
        self.left_panel.bind("<Leave>", lambda e: self.left_panel.configure(border_color="#1a1b35"))
        self.right_panel.bind("<Enter>", lambda e: self.right_panel.configure(border_color="#bc00dd"))
        self.right_panel.bind("<Leave>", lambda e: self.right_panel.configure(border_color="#1a1b35"))

    def update_view(self):
        """
        Reloads the macro list from database and refreshes editor if a macro is selected.
        """
        user_id = auth_manager.get_user_id() or "guest_user"
        macros = get_macros(user_id)

        # Clear active macro list display
        for widget in self.macro_list_scroll.winfo_children():
            widget.destroy()

        if not macros:
            no_macros_lbl = ctk.CTkLabel(
                self.macro_list_scroll,
                text="No macros yet.",
                font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
                text_color="#8e9aaf"
            )
            no_macros_lbl.pack(pady=20)
            
            self.editor_welcome.pack(fill="both", expand=True)
            self.editor_container.pack_forget()
            self.selected_macro_id = None
            return

        for m in macros:
            m_id = m["id"]
            m_name = m["name"]
            
            is_active = (m_id == self.selected_macro_id)
            btn = ctk.CTkButton(
                self.macro_list_scroll,
                text=m_name,
                fg_color="#111222" if is_active else "transparent",
                text_color="#00f0ff" if is_active else "#edf2f4",
                hover_color="#111222",
                border_color="#00f0ff" if is_active else "transparent",
                border_width=1 if is_active else 0,
                height=35,
                anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold" if is_active else "normal"),
                command=lambda mid=m_id: self.select_macro(mid)
            )
            btn.pack(fill="x", pady=2, padx=5)

        if self.selected_macro_id:
            exists = any(m["id"] == self.selected_macro_id for m in macros)
            if exists:
                self.load_macro_editor(self.selected_macro_id)
            else:
                self.selected_macro_id = None
                self.editor_welcome.pack(fill="both", expand=True)
                self.editor_container.pack_forget()

    def select_macro(self, macro_id):
        self.selected_macro_id = macro_id
        self.update_view()

    def load_macro_editor(self, macro_id):
        self.editor_welcome.pack_forget()
        self.editor_container.pack(fill="both", expand=True)
        
        from src.database.sqlite_db import get_macro_by_id
        macro = get_macro_by_id(macro_id)
        if not macro:
            return
            
        self.macro_name_label.configure(text=f"Edit Macro: {macro['name']}")
        
        steps = get_macro_steps(macro_id)
        self.local_steps = []
        for s in steps:
            self.local_steps.append({
                "id": s["id"],
                "action_type": s["action_type"],
                "sound_id": s["sound_id"],
                "delay_seconds": s["delay_seconds"]
            })
            
        self.draw_editor_steps()

    def create_new_macro(self):
        user_id = auth_manager.get_user_id() or "guest_user"
        name = simpledialog.askstring("New Macro", "Enter macro name:", parent=self.winfo_toplevel())
        if not name or not name.strip():
            return
            
        macro_id = str(uuid.uuid4())
        success = create_macro(macro_id, user_id, name.strip())
        if success:
            logger.info(f"Created new macro '{name}' successfully.")
            self.selected_macro_id = macro_id
            self.update_view()
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception:
                pass
        else:
            messagebox.showerror("Error", "Failed to create macro in DB.", parent=self.winfo_toplevel())

    def rename_current_macro(self):
        if not self.selected_macro_id:
            return
        name = simpledialog.askstring("Rename Macro", "Enter new name:", parent=self.winfo_toplevel())
        if not name or not name.strip():
            return
            
        success = rename_macro(self.selected_macro_id, name.strip())
        if success:
            logger.info(f"Renamed macro successfully to '{name}'")
            self.update_view()
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception:
                pass
        else:
            messagebox.showerror("Error", "Failed to rename macro.", parent=self.winfo_toplevel())

    def delete_current_macro(self):
        if not self.selected_macro_id:
            return
        confirm = messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this macro?", parent=self.winfo_toplevel())
        if not confirm:
            return
            
        success = delete_macro(self.selected_macro_id)
        if success:
            logger.info(f"Deleted macro {self.selected_macro_id}")
            self.selected_macro_id = None
            self.update_view()
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception:
                pass
        else:
            messagebox.showerror("Error", "Failed to delete macro.", parent=self.winfo_toplevel())

    def draw_editor_steps(self):
        for widget in self.steps_scroll.winfo_children():
            widget.destroy()

        if not self.local_steps:
            no_steps_lbl = ctk.CTkLabel(
                self.steps_scroll,
                text="Macro has no steps. Click below to add play/delay commands.",
                font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
                text_color="#8e9aaf"
            )
            no_steps_lbl.pack(pady=20)
            return

        all_sounds = []
        boards = soundboard_manager.get_boards()
        for b in boards:
            sounds = soundboard_manager.get_board_sounds(b["id"])
            for s in sounds:
                all_sounds.append(s)
                
        sound_options = [f"{s['name']} (ID: {s['id'][:6]})" for s in all_sounds]
        sound_map = {f"{s['name']} (ID: {s['id'][:6]})": s["id"] for s in all_sounds}

        for index, step in enumerate(self.local_steps):
            step_frame = ctk.CTkFrame(self.steps_scroll, fg_color="#161726", border_color="#1a1b35", border_width=1, corner_radius=6)
            step_frame.pack(fill="x", pady=4, padx=5)

            step_frame.bind("<Enter>", lambda e, sf=step_frame: sf.configure(border_color="#00f0ff"))
            step_frame.bind("<Leave>", lambda e, sf=step_frame: sf.configure(border_color="#1a1b35"))

            idx_lbl = ctk.CTkLabel(step_frame, text=f"#{index + 1}", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8e9aaf", width=25)
            idx_lbl.pack(side="left", padx=10)

            action_type = step["action_type"]
            if action_type == "play":
                type_lbl = ctk.CTkLabel(step_frame, text="PLAY SOUND", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#00f0ff", width=90, anchor="w")
                type_lbl.pack(side="left")

                curr_sound_id = step.get("sound_id")
                curr_label = "Select Sound..."
                
                if curr_sound_id:
                    matched_s = next((s for s in all_sounds if s["id"] == curr_sound_id), None)
                    if matched_s:
                        curr_label = f"{matched_s['name']} (ID: {matched_s['id'][:6]})"

                dropdown = ctk.CTkOptionMenu(
                    step_frame,
                    values=sound_options if sound_options else ["No Sounds Found"],
                    width=200,
                    fg_color="#04050a",
                    button_color="#bc00dd",
                    button_hover_color="#8c00aa",
                    dropdown_fg_color="#111222",
                    command=lambda val, idx=index: self.on_step_sound_change(idx, val, sound_map)
                )
                dropdown.set(curr_label)
                dropdown.pack(side="left", padx=10)

            elif action_type == "delay":
                type_lbl = ctk.CTkLabel(step_frame, text="DELAY WAIT", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#ffb703", width=90, anchor="w")
                type_lbl.pack(side="left")

                curr_delay = step.get("delay_seconds", 1.0)
                entry = ctk.CTkEntry(step_frame, width=80, height=28, fg_color="#04050a", border_color="#1a1b35")
                entry.insert(0, str(curr_delay))
                
                entry.bind("<FocusOut>", lambda e, idx=index, ent=entry: self.on_step_delay_change(idx, ent.get()))
                entry.bind("<Return>", lambda e, idx=index, ent=entry: self.on_step_delay_change(idx, ent.get()))
                entry.pack(side="left", padx=10)

                sec_lbl = ctk.CTkLabel(step_frame, text="seconds", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#edf2f4")
                sec_lbl.pack(side="left")

            ctrls = ctk.CTkFrame(step_frame, fg_color="transparent")
            ctrls.pack(side="right", padx=10)

            up_btn = ctk.CTkButton(
                ctrls,
                text="▲",
                width=24,
                height=24,
                fg_color="#04050a",
                text_color="#edf2f4",
                hover_color="#bc00dd",
                state="normal" if index > 0 else "disabled",
                command=lambda idx=index: self.move_step(idx, -1)
            )
            up_btn.pack(side="left", padx=2)

            down_btn = ctk.CTkButton(
                ctrls,
                text="▼",
                width=24,
                height=24,
                fg_color="#04050a",
                text_color="#edf2f4",
                hover_color="#bc00dd",
                state="normal" if index < len(self.local_steps) - 1 else "disabled",
                command=lambda idx=index: self.move_step(idx, 1)
            )
            down_btn.pack(side="left", padx=2)

            del_btn = ctk.CTkButton(
                ctrls,
                text="✖",
                width=24,
                height=24,
                fg_color="transparent",
                text_color="#ff0055",
                hover_color="#ff0055",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda idx=index: self.delete_step(idx)
            )
            del_btn.pack(side="left", padx=(5, 0))

    def add_play_step(self):
        self.local_steps.append({
            "id": str(uuid.uuid4()),
            "action_type": "play",
            "sound_id": None,
            "delay_seconds": None
        })
        self.save_steps_to_db()
        self.draw_editor_steps()

    def add_delay_step(self):
        self.local_steps.append({
            "id": str(uuid.uuid4()),
            "action_type": "delay",
            "sound_id": None,
            "delay_seconds": 1.0
        })
        self.save_steps_to_db()
        self.draw_editor_steps()

    def on_step_sound_change(self, idx, value, sound_map):
        sound_id = sound_map.get(value)
        if sound_id:
            self.local_steps[idx]["sound_id"] = sound_id
            self.save_steps_to_db()

    def on_step_delay_change(self, idx, val_str):
        try:
            val = float(val_str)
            if val < 0:
                val = 0.0
            self.local_steps[idx]["delay_seconds"] = val
            self.save_steps_to_db()
        except ValueError:
            pass

    def move_step(self, idx, direction):
        target = idx + direction
        if 0 <= target < len(self.local_steps):
            self.local_steps[idx], self.local_steps[target] = self.local_steps[target], self.local_steps[idx]
            self.save_steps_to_db()
            self.draw_editor_steps()

    def delete_step(self, idx):
        self.local_steps.pop(idx)
        self.save_steps_to_db()
        self.draw_editor_steps()

    def save_steps_to_db(self):
        if not self.selected_macro_id:
            return
            
        clear_macro_steps(self.selected_macro_id)
        
        for pos, step in enumerate(self.local_steps):
            add_macro_step(
                step_id=step["id"],
                macro_id=self.selected_macro_id,
                position=pos,
                action_type=step["action_type"],
                sound_id=step["sound_id"],
                delay_seconds=step["delay_seconds"]
            )
            
        logger.debug(f"Saved {len(self.local_steps)} steps to DB for macro {self.selected_macro_id}.")
        try:
            from src.sync.sync_manager import sync_manager
            sync_manager.trigger_sync()
        except Exception:
            pass

    def play_current_macro(self):
        if not self.selected_macro_id:
            return
        macro_manager.cancel_all()
        macro_manager.play_macro(self.selected_macro_id)
