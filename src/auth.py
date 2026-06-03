import time
from src.logger import logger
from src.config import config_manager
from src.database.sqlite_db import save_local_session, get_last_local_session, clear_local_sessions
from src.database.supabase_db import get_supabase_client

class AuthManager:
    """
    Manages user authentication, including sign up, login, logout, and session restoration.
    """
    def __init__(self):
        self.current_user = None  # Holds Supabase user object if logged in

    def get_client(self):
        return get_supabase_client()

    def is_logged_in(self) -> bool:
        return self.current_user is not None

    def get_user_email(self) -> str:
        return self.current_user.email if self.current_user else ""

    def get_user_id(self) -> str:
        return self.current_user.id if self.current_user else ""

    def sign_up(self, email, password):
        """
        Signs up a new user with Supabase.
        """
        client = self.get_client()
        if not client:
            return {"success": False, "error": "Supabase client is not configured or offline."}

        try:
            logger.info(f"Attempting sign up for email: {email}")
            # Supabase Python client Auth v2 uses dict parameter or kwargs
            response = client.auth.sign_up({"email": email, "password": password})
            user = response.user
            if user:
                return {"success": True, "user": user, "message": "Sign up successful! Please check your email for confirmation."}
            else:
                return {"success": False, "error": "Sign up succeeded but returned no user info."}
        except Exception as e:
            logger.error(f"Sign up failed: {e}")
            return {"success": False, "error": str(e)}

    def sign_in(self, email, password, remember_me=True):
        """
        Signs in an existing user with Supabase and caches session info locally if checked.
        """
        client = self.get_client()
        if not client:
            return {"success": False, "error": "Supabase client is not configured or offline."}

        try:
            logger.info(f"Attempting login for email: {email}")
            response = client.auth.sign_in_with_password({"email": email, "password": password})
            session = response.session
            user = response.user

            if session and user:
                self.current_user = user
                
                # Check expiration attributes
                expires_at = getattr(session, 'expires_at', None)
                if expires_at is None:
                    expires_in = getattr(session, 'expires_in', 3600)
                    expires_at = int(time.time()) + expires_in

                if remember_me:
                    save_local_session(
                        user_id=user.id,
                        email=user.email,
                        access_token=session.access_token,
                        refresh_token=session.refresh_token,
                        expires_at=expires_at
                    )
                    config_manager.set("remember_me", True)
                    config_manager.set("last_session", {
                        "user_id": user.id,
                        "email": user.email
                    })
                else:
                    clear_local_sessions()
                    config_manager.set("remember_me", False)
                    config_manager.set("last_session", {})

                logger.info(f"User signed in successfully: {email}")
                return {"success": True, "user": user}
            else:
                return {"success": False, "error": "Sign in failed: invalid credentials or session details."}
        except Exception as e:
            logger.error(f"Sign in failed: {e}")
            return {"success": False, "error": str(e)}

    def sign_out(self):
        """
        Signs out the current user and clears local session cache.
        """
        client = self.get_client()
        if client:
            try:
                client.auth.sign_out()
            except Exception as e:
                logger.error(f"Supabase remote sign out error: {e}")

        self.current_user = None
        clear_local_sessions()
        config_manager.set("last_session", {})
        logger.info("User signed out and local session cleared.")
        return {"success": True}

    def restore_session(self) -> bool:
        """
        Attempts to restore a cached session from SQLite.
        """
        client = self.get_client()
        if not client:
            logger.debug("Cannot restore session: Supabase client not initialized.")
            return False

        if not config_manager.get("remember_me", True):
            logger.debug("Cannot restore session: 'remember_me' preference is disabled.")
            return False

        local_session = get_last_local_session()
        if not local_session:
            logger.debug("No local session cached in SQLite database.")
            return False

        try:
            logger.info(f"Attempting to restore session for cached user: {local_session['email']}")
            response = client.auth.set_session(local_session["access_token"], local_session["refresh_token"])
            user = response.user
            session = response.session

            if user and session:
                self.current_user = user
                
                # Update tokens (could have rotated)
                expires_at = getattr(session, 'expires_at', None)
                if expires_at is None:
                    expires_in = getattr(session, 'expires_in', 3600)
                    expires_at = int(time.time()) + expires_in
                    
                save_local_session(
                    user_id=user.id,
                    email=user.email,
                    access_token=session.access_token,
                    refresh_token=session.refresh_token,
                    expires_at=expires_at
                )
                logger.info(f"Session successfully restored for user: {user.email}")
                return True
            else:
                logger.warning("Cached session restoration failed (invalid response). Clearing local cache.")
                clear_local_sessions()
                return False
        except Exception as e:
            logger.warning(f"Failed to restore cached session: {e}. Clearing local cache.")
            clear_local_sessions()
            return False

    def send_password_reset(self, email):
        """
        Sends a password reset email via Supabase.
        """
        client = self.get_client()
        if not client:
            return {"success": False, "error": "Supabase client is not configured or offline."}

        try:
            client.auth.reset_password_for_email(email)
            logger.info(f"Password reset instructions email requested for: {email}")
            return {"success": True, "message": "Password reset instructions sent. Please check your email."}
        except Exception as e:
            logger.error(f"Password reset request failed: {e}")
            return {"success": False, "error": str(e)}

# Global authentication manager instance
auth_manager = AuthManager()
