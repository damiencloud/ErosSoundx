from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import uvicorn
import socket
import string
import random
import ipaddress
import threading
import asyncio
from src.logger import logger
from src.soundboard_manager import soundboard_manager
from src.audio.audio_engine import audio_engine

# ---------------- LOCAL IP RANGE CHECKS ----------------
PRIVATE_SUBNETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local Address
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local Address
    ipaddress.ip_network("::1/128")     # IPv6 Loopback
]

def is_local_ip(ip_str: str) -> bool:
    """
    Checks if a client host IP address lies within private network ranges.
    """
    try:
        # Strip ports or IPv6 brackets
        if ":" in ip_str and not ip_str.startswith("["):
            if ip_str.count(":") == 1:
                ip_str = ip_str.split(":")[0]
        ip = ipaddress.ip_address(ip_str)
        return any(ip in subnet for subnet in PRIVATE_SUBNETS)
    except Exception as e:
        logger.debug(f"IP checking failed for '{ip_str}': {e}")
        return False

# ---------------- FASTAPI APPLICATION ----------------
app = FastAPI(title="ErosSoundX Remote Server")

# Resolve static directory
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(root_dir, "src", "web")

# Middleware: Restrict HTTP traffic to Local Network Only
@app.middleware("http")
async def local_network_only_middleware(request: Request, call_next):
    client_host = request.client.host if request.client else "127.0.0.1"
    if not is_local_ip(client_host):
        logger.warning(f"Access Denied: Blocked HTTP request from non-local client IP: {client_host}")
        return Response("Access Denied: Local Network Only", status_code=403)
    return await call_next(request)

@app.get("/")
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        return Response("Static assets index.html not found. Please place files in src/web/", status_code=404)
    return FileResponse(index_path)

# Serve CSS and JS assets
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    manager = APIServerManager.get_instance()
    
    # 1. Verify Client Local network range
    client_host = websocket.client.host if websocket.client else "127.0.0.1"
    if not is_local_ip(client_host):
        logger.warning(f"WebSocket connection blocked: Client IP '{client_host}' is not local.")
        await websocket.close(code=4003)
        return

    # 2. Verify Session Pairing Token
    if token != manager.token:
        logger.warning(f"WebSocket connection unauthorized: provided token '{token}' does not match '{manager.token}'")
        await websocket.close(code=4001)
        return

    await websocket.accept()
    manager.active_connections.add(websocket)
    # Cache the active server loop context thread-safely
    if not manager.loop:
        manager.loop = asyncio.get_event_loop()

    logger.info(f"WebSocket client connected from {client_host}")

    try:
        # Pushes initial Soundboard metadata grid state
        initial_payload = {
            "type": "init",
            "data": manager.get_state_payload()
        }
        await websocket.send_json(initial_payload)

        # Main message loop
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "play":
                sound_id = data.get("sound_id")
                from src.database.sqlite_db import get_sound_by_id
                sound = get_sound_by_id(sound_id)
                if sound:
                    # Trigger low latency pygame audio mixer play command
                    audio_engine.play_sound(
                        sound_id=sound["id"],
                        file_path=sound["file_path"],
                        volume=sound.get("volume", 1.0)
                    )
                else:
                    logger.warning(f"Remote trigger play failed: sound_id '{sound_id}' not found.")
            
            elif action == "stop":
                sound_id = data.get("sound_id")
                audio_engine.stop_sound(sound_id)
            
            elif action == "stop_all":
                audio_engine.stop_all()

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_host}")
    except Exception as e:
        logger.error(f"WebSocket processing error: {e}")
    finally:
        manager.active_connections.discard(websocket)

# ---------------- PROGRAMMATIC SERVER MANAGER ----------------
class APIServerManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.server_thread = None
        self.server = None
        self.port = 8000
        self.token = self.generate_token()
        self.is_running = False
        self.active_connections = set()
        self.loop = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @staticmethod
    def generate_token():
        """
        Generates a secure 6-character alphanumeric session token for verification.
        """
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    def get_local_ip(self) -> str:
        """
        Detects the current active local IP address of the machine on the network.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Connecting to a public DNS server determines the primary interface IP
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_state_payload(self) -> dict:
        """
        Compiles all soundboards and sounds metadata currently stored in local cache.
        """
        boards = soundboard_manager.get_boards()
        state = {
            "soundboards": boards,
            "sounds": {}
        }
        # Add Favorites sounds
        state["sounds"]["favorites"] = soundboard_manager.get_favorites()
        
        # Add boards soundboards lists
        for b in boards:
            state["sounds"][b["id"]] = soundboard_manager.get_board_sounds(b["id"])
        return state

    def broadcast_state(self):
        """
        Thread-safe method that triggers an active loop broadcast to all WebSockets clients.
        Called on database mutation callbacks.
        """
        if not self.active_connections:
            return
            
        payload = {
            "type": "update",
            "data": self.get_state_payload()
        }

        async def run_broadcast():
            # Iterate over copy to prevent concurrent update exceptions
            for conn in list(self.active_connections):
                try:
                    await conn.send_json(payload)
                except Exception as e:
                    logger.debug(f"Failed to broadcast update payload: {e}")

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(run_broadcast(), self.loop)

    def start(self):
        """
        Locates a free port (between 8000 and 8050) and starts the Uvicorn server in a background daemon thread.
        """
        if self.is_running:
            return

        # Find first open port in the configured range
        port = 8000
        port_found = False
        while port <= 8050:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    self.port = port
                    port_found = True
                    break
            port += 1

        if not port_found:
            logger.error("Failed to start Remote API server: all ports in range 8000-8050 are occupied.")
            return

        # Configure Uvicorn server instance
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=self.port,
            log_level="warning",
            loop="asyncio"
        )
        self.server = uvicorn.Server(config)

        # Run within a daemon background thread so it shuts down cleanly when Tkinter thread terminates
        self.server_thread = threading.Thread(target=self.server.run, name="RemoteServerThread", daemon=True)
        self.server_thread.start()
        self.is_running = True

        # Hook updates callbacks
        soundboard_manager.register_change_callback(self.broadcast_state)
        logger.info(f"Local network remote server started successfully at http://{self.get_local_ip()}:{self.port} with token {self.token}")

    def stop(self):
        """
        Shuts down the server and resets local handles.
        """
        if not self.is_running or not self.server:
            return
        
        logger.info("Stopping local network remote server...")
        self.server.should_exit = True
        self.is_running = False
        self.loop = None
        self.active_connections.clear()
        logger.info("Local network remote server stopped.")
