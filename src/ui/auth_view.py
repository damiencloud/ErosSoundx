import customtkinter as ctk
import threading
from src.auth import auth_manager
from src.logger import logger
from src.config import config_manager

class AuthView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.mode = "login"  # "login", "register", "reset"

        # Center Container
        self.container = ctk.CTkFrame(self, fg_color="#121320", corner_radius=16, border_color="#1f2833", border_width=1, width=420, height=480)
        self.container.place(relx=0.5, rely=0.5, anchor="center")

        # Loading state flag
        self.is_loading = False

        self.draw_view()

    def set_mode(self, mode):
        if self.is_loading:
            return
        self.mode = mode
        self.draw_view()

    def draw_view(self):
        # Clear container
        for widget in self.container.winfo_children():
            widget.destroy()

        if self.mode == "login":
            self.draw_login()
        elif self.mode == "register":
            self.draw_register()
        elif self.mode == "reset":
            self.draw_reset()

    def show_loading(self, text="Processing..."):
        self.is_loading = True
        self.draw_view()
        
        # Display Loading Indicator
        loading_label = ctk.CTkLabel(
            self.container, 
            text=text, 
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#00f0ff"
        )
        loading_label.pack(pady=40)
        
        spinner = ctk.CTkProgressBar(self.container, mode="indeterminate", width=250, progress_color="#00f0ff")
        spinner.pack(pady=20)
        spinner.start()

    def run_async(self, target_fn, callback_fn, *args):
        """
        Executes an authentication task in a background thread to prevent Tkinter freezing.
        """
        def worker():
            try:
                res = target_fn(*args)
                self.after(0, callback_fn, res)
            except Exception as e:
                logger.error(f"Authentication thread crashed: {e}")
                self.after(0, callback_fn, {"success": False, "error": str(e)})
        
        threading.Thread(target=worker, daemon=True).start()

    # --- LOGIN SCREEN ---
    def draw_login(self):
        # Title (Cyberpunk neon title)
        title = ctk.CTkLabel(self.container, text="Sign In", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color="#00f0ff")
        title.pack(pady=(35, 10))

        subtitle = ctk.CTkLabel(self.container, text="Access your synced soundboard profile", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8e9aaf")
        subtitle.pack(pady=(0, 20))

        # Inputs
        self.email_input = ctk.CTkEntry(self.container, placeholder_text="Email", width=300, height=40, corner_radius=8, fg_color="#0b0c10", border_color="#1f2833")
        self.email_input.pack(pady=8)
        
        # Prepopulate email if remember_me is cached
        last_sess = config_manager.get("last_session")
        if last_sess and "email" in last_sess:
            self.email_input.insert(0, last_sess["email"])

        self.password_input = ctk.CTkEntry(self.container, placeholder_text="Password", show="*", width=300, height=40, corner_radius=8, fg_color="#0b0c10", border_color="#1f2833")
        self.password_input.pack(pady=8)

        # Remember Me Checkbox
        self.remember_var = ctk.BooleanVar(value=config_manager.get("remember_me", True))
        self.remember_cb = ctk.CTkCheckBox(
            self.container, 
            text="Remember me on this device", 
            variable=self.remember_var, 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            checkbox_width=18,
            checkbox_height=18,
            border_width=2,
            fg_color="#bc00dd",
            hover_color="#8c00aa",
            text_color="#edf2f4"
        )
        self.remember_cb.pack(pady=10, padx=60, anchor="w")

        # Feedback Label
        self.feedback_label = ctk.CTkLabel(self.container, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#ff0055")
        self.feedback_label.pack(pady=(2, 5))

        # Login button (Cyan Cyber Accent)
        login_btn = ctk.CTkButton(
            self.container, 
            text="Log In", 
            width=300, 
            height=40, 
            corner_radius=8, 
            fg_color="#00f0ff", 
            text_color="#0b0c10",
            hover_color="#00b8cc",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self.handle_login
        )
        login_btn.pack(pady=10)

        # Navigation toggles
        nav_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        nav_frame.pack(pady=(15, 20))

        reg_link = ctk.CTkButton(
            nav_frame, 
            text="Create Account", 
            fg_color="transparent", 
            hover=False, 
            text_color="#00f0ff", 
            width=100,
            font=ctk.CTkFont(family="Segoe UI", size=11, underline=True),
            command=lambda: self.set_mode("register")
        )
        reg_link.pack(side="left", padx=10)

        reset_link = ctk.CTkButton(
            nav_frame, 
            text="Forgot Password?", 
            fg_color="transparent", 
            hover=False, 
            text_color="#8e9aaf", 
            width=100,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self.set_mode("reset")
        )
        reset_link.pack(side="right", padx=10)

    # --- REGISTRATION SCREEN ---
    def draw_register(self):
        title = ctk.CTkLabel(self.container, text="Sign Up", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color="#00f0ff")
        title.pack(pady=(35, 10))

        subtitle = ctk.CTkLabel(self.container, text="Create a new account for cloud syncing", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8e9aaf")
        subtitle.pack(pady=(0, 20))

        # Inputs
        self.reg_email = ctk.CTkEntry(self.container, placeholder_text="Email Address", width=300, height=40, corner_radius=8, fg_color="#0b0c10", border_color="#1f2833")
        self.reg_email.pack(pady=8)

        self.reg_password = ctk.CTkEntry(self.container, placeholder_text="Password (min 6 characters)", show="*", width=300, height=40, corner_radius=8, fg_color="#0b0c10", border_color="#1f2833")
        self.reg_password.pack(pady=8)

        self.reg_confirm = ctk.CTkEntry(self.container, placeholder_text="Confirm Password", show="*", width=300, height=40, corner_radius=8, fg_color="#0b0c10", border_color="#1f2833")
        self.reg_confirm.pack(pady=8)

        self.feedback_label = ctk.CTkLabel(self.container, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#ff0055")
        self.feedback_label.pack(pady=(2, 5))

        # Register Button (Purple Cyber Accent)
        register_btn = ctk.CTkButton(
            self.container, 
            text="Create Account", 
            width=300, 
            height=40, 
            corner_radius=8, 
            fg_color="#bc00dd", 
            text_color="#ffffff",
            hover_color="#8c00aa",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self.handle_register
        )
        register_btn.pack(pady=10)

        # Back to Login Link
        back_link = ctk.CTkButton(
            self.container, 
            text="Already have an account? Sign In", 
            fg_color="transparent", 
            hover=False, 
            text_color="#00f0ff", 
            font=ctk.CTkFont(family="Segoe UI", size=11, underline=True),
            command=lambda: self.set_mode("login")
        )
        back_link.pack(pady=(15, 20))

    # --- PASSWORD RESET SCREEN ---
    def draw_reset(self):
        title = ctk.CTkLabel(self.container, text="Reset Password", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color="#00f0ff")
        title.pack(pady=(35, 10))

        subtitle = ctk.CTkLabel(self.container, text="Receive a recovery link on your email", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8e9aaf")
        subtitle.pack(pady=(0, 20))

        # Inputs
        self.reset_email = ctk.CTkEntry(self.container, placeholder_text="Enter your email", width=300, height=40, corner_radius=8, fg_color="#0b0c10", border_color="#1f2833")
        self.reset_email.pack(pady=20)

        self.feedback_label = ctk.CTkLabel(self.container, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#ff0055")
        self.feedback_label.pack(pady=(2, 10))

        # Submit button
        submit_btn = ctk.CTkButton(
            self.container, 
            text="Send Reset Link", 
            width=300, 
            height=40, 
            corner_radius=8, 
            fg_color="#ff0055", 
            text_color="#0b0c10",
            hover_color="#d00045",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self.handle_reset
        )
        submit_btn.pack(pady=10)

        # Back link
        back_link = ctk.CTkButton(
            self.container, 
            text="Back to Sign In", 
            fg_color="transparent", 
            hover=False, 
            text_color="#00f0ff", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self.set_mode("login")
        )
        back_link.pack(pady=(15, 20))

    # --- EVENT HANDLERS ---
    def handle_login(self):
        email = self.email_input.get().strip()
        password = self.password_input.get()
        remember = self.remember_var.get()

        if not email or not password:
            self.feedback_label.configure(text="Please fill in all fields.", text_color="#ff0266")
            return

        self.show_loading("Verifying Credentials...")
        self.run_async(auth_manager.sign_in, self.on_login_complete, email, password, remember)

    def on_login_complete(self, result):
        self.is_loading = False
        if result.get("success"):
            logger.info("Sign in successful.")
            # Trigger updates across shell
            self.controller.on_auth_state_changed()
            # Trigger background sync wakeup
            try:
                from src.sync.sync_manager import sync_manager
                sync_manager.trigger_sync()
            except Exception as e:
                logger.error(f"Failed to trigger sync after login: {e}")
            # Redirect to Dashboard view
            self.controller.select_tab("dashboard")
        else:
            self.draw_view()
            err_msg = result.get("error", "Sign in failed.")
            self.feedback_label.configure(text=err_msg, text_color="#ff0266")

    def handle_register(self):
        email = self.reg_email.get().strip()
        password = self.reg_password.get()
        confirm = self.reg_confirm.get()

        if not email or not password or not confirm:
            self.feedback_label.configure(text="Please fill in all fields.", text_color="#ff0266")
            return

        if password != confirm:
            self.feedback_label.configure(text="Passwords do not match.", text_color="#ff0266")
            return

        if len(password) < 6:
            self.feedback_label.configure(text="Password must be at least 6 characters.", text_color="#ff0266")
            return

        self.show_loading("Creating Account...")
        self.run_async(auth_manager.sign_up, self.on_register_complete, email, password)

    def on_register_complete(self, result):
        self.is_loading = False
        self.draw_view()
        if result.get("success"):
            msg = result.get("message", "Registration successful!")
            self.feedback_label.configure(text=msg, text_color="#03dac6")
        else:
            err_msg = result.get("error", "Registration failed.")
            self.feedback_label.configure(text=err_msg, text_color="#ff0266")

    def handle_reset(self):
        email = self.reset_email.get().strip()

        if not email:
            self.feedback_label.configure(text="Please enter your email.", text_color="#ff0266")
            return

        self.show_loading("Sending Recovery Email...")
        self.run_async(auth_manager.send_password_reset, self.on_reset_complete, email)

    def on_reset_complete(self, result):
        self.is_loading = False
        self.draw_view()
        if result.get("success"):
            msg = result.get("message", "Instructions sent!")
            self.feedback_label.configure(text=msg, text_color="#03dac6")
        else:
            err_msg = result.get("error", "Failed to send reset link.")
            self.feedback_label.configure(text=err_msg, text_color="#ff0266")
