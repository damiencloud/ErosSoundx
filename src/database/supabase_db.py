import os
import urllib.request
import urllib.error
from dotenv import load_dotenv
from supabase import create_client, Client
from src.logger import logger
from src.config import config_manager

# Load environmental variables
load_dotenv()

_supabase_client = None

def get_supabase_client() -> Client:
    """
    Instantiates and returns the Supabase client.
    Returns None if credentials are not configured or invalid.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    # Get from environment variable first, fall back to UI local config
    url = os.getenv("SUPABASE_URL") or config_manager.get("supabase_url")
    key = os.getenv("SUPABASE_KEY") or config_manager.get("supabase_key")

    # Clean strings and ignore placeholders
    if url:
        url = url.strip()
    if key:
        key = key.strip()

    if not url or not key or "your-project" in url or "your-supabase" in key or url == "" or key == "":
        logger.warning("Supabase URL and/or Anon Key is not configured. Cloud features are disabled.")
        return None

    try:
        # Instantiate supabase-py client
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized successfully.")
        return _supabase_client
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return None

def reset_supabase_client():
    """
    Forces the Supabase client to re-evaluate configuration.
    Useful when settings are updated in the UI.
    """
    global _supabase_client
    _supabase_client = None
    logger.debug("Supabase client state has been reset.")

def test_supabase_connection() -> bool:
    """
    Checks if the Supabase server is reachable and active.
    Uses built-in urllib to avoid external dependencies for network check.
    """
    url = os.getenv("SUPABASE_URL") or config_manager.get("supabase_url")
    if not url or "your-project" in url or url == "":
        return False
        
    try:
        # Standardize URL
        target_url = url.strip()
        if not target_url.startswith("http"):
            target_url = f"https://{target_url}"
            
        # Send a lightweight request to the Supabase endpoint
        # If reachable, we should get 200, 400, 401, or 404 (all indicate server is online).
        # Network failures will raise urllib.error.URLError.
        req = urllib.request.Request(target_url, method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as response:
            status = response.getcode()
            return status >= 200 and status < 500
    except urllib.error.HTTPError as e:
        # Got an HTTP response from server (e.g. 401 Unauthorized), which means the server is online
        return e.code >= 200 and e.code < 500
    except Exception as e:
        logger.debug(f"Supabase connection test failed: {e}")
        return False
