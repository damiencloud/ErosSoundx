import sys
import os
import traceback
import threading
import time
import platform
from src.logger import logger
from src.config import config_manager

CRASH_REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "crash_reports"
)

# Ensure the crash reports directory exists
os.makedirs(CRASH_REPORTS_DIR, exist_ok=True)

class BugTracker:
    _root = None

    @classmethod
    def initialize(cls, root):
        """
        Registers global exception hooks for sys, threads, and Tkinter.
        """
        cls._root = root
        
        # 1. Sys excepthook (standard unhandled exceptions)
        sys.excepthook = cls.handle_exception

        # 2. Threading excepthook (unhandled exceptions in background threads)
        # threading.excepthook was added in Python 3.8
        threading.excepthook = cls.handle_thread_exception

        # 3. Tkinter excepthook
        if root:
            root.report_callback_exception = cls.handle_tkinter_exception
            
        logger.info("Exception hook interceptors successfully registered.")

    @classmethod
    def handle_exception(cls, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical("Unhandled exception intercepted!", exc_info=(exc_type, exc_value, exc_traceback))
        report_path = cls.write_crash_report(exc_type, exc_value, exc_traceback)
        cls.show_crash_dialog(exc_value, report_path)

    @classmethod
    def handle_thread_exception(cls, args):
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback

        logger.critical("Unhandled thread exception intercepted!", exc_info=(exc_type, exc_value, exc_traceback))
        report_path = cls.write_crash_report(exc_type, exc_value, exc_traceback)
        cls.show_crash_dialog(exc_value, report_path)

    @classmethod
    def handle_tkinter_exception(cls, exc_type, exc_value, exc_traceback):
        logger.critical("Tkinter callback exception intercepted!", exc_info=(exc_type, exc_value, exc_traceback))
        report_path = cls.write_crash_report(exc_type, exc_value, exc_traceback)
        cls.show_crash_dialog(exc_value, report_path)

    @classmethod
    def write_crash_report(cls, exc_type, exc_value, exc_traceback) -> str:
        timestamp = int(time.time())
        report_filename = f"crash_{timestamp}.txt"
        report_path = os.path.join(CRASH_REPORTS_DIR, report_filename)

        try:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            tb_str = "".join(tb_lines)

            # System environment diagnostics (excluding secrets)
            diagnostics = {
                "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
                "OS": platform.system(),
                "OS Release": platform.release(),
                "Python Version": sys.version,
                "Streamer Mode": config_manager.get("streamer_mode", False),
                "App Theme": config_manager.get("theme", "Dark"),
                "Master Volume": config_manager.get("master_volume", 1.0),
            }

            with open(report_path, "w", encoding="utf-8") as f:
                f.write("=========================================\n")
                f.write("            EROSSOUNDX CRASH REPORT      \n")
                f.write("=========================================\n\n")
                
                f.write("--- Environment Diagnostics ---\n")
                for k, v in diagnostics.items():
                    f.write(f"{k}: {v}\n")
                f.write("\n")

                f.write("--- Stack Trace ---\n")
                f.write(tb_str)
                f.write("\n=========================================\n")
            
            logger.info(f"Crash report written to: {report_path}")
            return report_path
        except Exception as e:
            logger.error(f"Failed to write crash report file: {e}")
            return "Unknown"

    @classmethod
    def show_crash_dialog(cls, exc_value, report_path):
        """
        Displays a cyberpunk-styled warning message box.
        Handles execution on main thread safely.
        """
        def display():
            import customtkinter as ctk
            from tkinter import messagebox
            
            msg = (
                "An unexpected application crash has occurred.\n\n"
                f"Error Details: {exc_value}\n\n"
                f"A crash diagnostic report has been saved to:\n{report_path}\n\n"
                "Please share this report with the development team."
            )
            
            if cls._root:
                # Custom Tkinter themed Toplevel error dialog
                dialog = ctk.CTkToplevel(cls._root)
                dialog.title("System Error Intercepted")
                dialog.geometry("450x220")
                dialog.resizable(False, False)
                dialog.transient(cls._root)
                dialog.grab_set()
                dialog.configure(fg_color="#0c0f12")

                # Center on root
                try:
                    px = cls._root.winfo_x()
                    py = cls._root.winfo_y()
                    pw = cls._root.winfo_width()
                    ph = cls._root.winfo_height()
                    x = px + (pw // 2) - 225
                    y = py + (ph // 2) - 110
                    dialog.geometry(f"+{x}+{y}")
                except Exception:
                    pass

                title_lbl = ctk.CTkLabel(
                    dialog,
                    text="CRITICAL ERROR DETECTED",
                    font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                    text_color="#ff0055"
                )
                title_lbl.pack(pady=(15, 10))

                content_box = ctk.CTkTextbox(
                    dialog,
                    width=410,
                    height=100,
                    font=ctk.CTkFont(family="Consolas", size=11),
                    fg_color="#000000",
                    text_color="#ff0055",
                    border_width=1,
                    border_color="#ff0055"
                )
                content_box.pack(padx=20, pady=5)
                content_box.insert("1.0", msg)
                content_box.configure(state="disabled")

                close_btn = ctk.CTkButton(
                    dialog,
                    text="Close",
                    width=100,
                    height=28,
                    fg_color="#ff0055",
                    text_color="#0b0c10",
                    hover_color="#cc0044",
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    command=dialog.destroy
                )
                close_btn.pack(pady=10)
            else:
                # Fallback to standard messagebox if UI is not fully loaded
                messagebox.showerror("ErosSoundX Critical Error", msg)

        if cls._root:
            cls._root.after(0, display)
        else:
            display()
