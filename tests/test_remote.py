import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api_server import app, is_local_ip, APIServerManager

class TestRemoteControl(unittest.TestCase):
    def setUp(self):
        self.manager = APIServerManager.get_instance()
        # Ensure server state is reset for testing
        self.manager.active_connections.clear()
        self.manager.loop = None
        self.client = TestClient(app)

    def test_is_local_ip_validation(self):
        # Local subnets (RFC 1918 & Loopback) should pass
        self.assertTrue(is_local_ip("127.0.0.1"))
        self.assertTrue(is_local_ip("192.168.1.50"))
        self.assertTrue(is_local_ip("10.0.12.3"))
        self.assertTrue(is_local_ip("172.16.55.99"))
        self.assertTrue(is_local_ip("169.254.10.20"))
        self.assertTrue(is_local_ip("::1"))
        self.assertTrue(is_local_ip("fe80::1"))

        # Public IPs should fail
        self.assertFalse(is_local_ip("8.8.8.8"))
        self.assertFalse(is_local_ip("104.244.42.1"))
        self.assertFalse(is_local_ip("200.10.20.30"))

        # Malformed IPs should fail gracefully
        self.assertFalse(is_local_ip("invalid-ip-string"))
        self.assertFalse(is_local_ip(""))

    @patch("src.api_server.is_local_ip")
    def test_http_ip_middleware_blocks_external(self, mock_is_local):
        # Simulate request coming from an external non-local IP address
        mock_is_local.return_value = False
        
        # Test request to root endpoint
        response = self.client.get("/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Access Denied", response.text)

    @patch("src.api_server.is_local_ip")
    def test_http_ip_middleware_allows_local(self, mock_is_local):
        # Simulate request coming from local IP address
        mock_is_local.return_value = True
        
        # Patch FileResponse to return dummy html if static files don't exist
        with patch("os.path.exists", return_value=True), \
             patch("src.api_server.FileResponse", return_value="dummy_html"):
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)

    @patch("src.api_server.is_local_ip")
    def test_websocket_token_validation(self, mock_is_local):
        # Ensure client is marked as local IP
        mock_is_local.return_value = True
        
        # 1. Invalid Token should close WS connection with code 4001 (Unauthorized)
        with self.assertRaises(Exception):
            with self.client.websocket_connect("/ws?token=WRONGTOKEN"):
                pass

        # 2. Valid Token should connect successfully
        valid_token = self.manager.token
        with self.client.websocket_connect(f"/ws?token={valid_token}") as websocket:
            # Check that initial state payload is received
            initial_data = websocket.receive_json()
            self.assertEqual(initial_data["type"], "init")
            self.assertIn("soundboards", initial_data["data"])
            self.assertIn("sounds", initial_data["data"])

    @patch("src.api_server.is_local_ip")
    @patch("src.api_server.audio_engine")
    @patch("src.database.sqlite_db.get_sound_by_id")
    def test_websocket_audio_commands(self, mock_get_sound, mock_audio_engine, mock_is_local):
        mock_is_local.return_value = True
        
        # Set up mock sound return
        mock_get_sound.return_value = {
            "id": "sound-abc",
            "name": "Airhorn",
            "file_path": "cache/sound-abc.wav",
            "volume": 0.8
        }
        
        valid_token = self.manager.token
        with self.client.websocket_connect(f"/ws?token={valid_token}") as websocket:
            # Drain the initial state dump
            websocket.receive_json()
            
            # Send play command payload
            websocket.send_json({
                "action": "play",
                "sound_id": "sound-abc"
            })
            
            # Allow time for messages to process inside client loops
            import time
            time.sleep(0.05)
            mock_audio_engine.play_sound.assert_called_with(
                sound_id="sound-abc",
                file_path="cache/sound-abc.wav",
                volume=0.8
            )

            # Send stop command payload
            websocket.send_json({
                "action": "stop",
                "sound_id": "sound-abc"
            })
            time.sleep(0.05)
            mock_audio_engine.stop_sound.assert_called_with("sound-abc")

            # Send stop_all command payload
            websocket.send_json({
                "action": "stop_all"
            })
            time.sleep(0.05)
            mock_audio_engine.stop_all.assert_called()

    @patch("src.api_server.is_local_ip")
    def test_soundboard_manager_change_callbacks(self, mock_is_local):
        mock_is_local.return_value = True
        
        # Register a mock broadcast callback or verify manager registration
        mock_broadcast = MagicMock()
        from src.soundboard_manager import soundboard_manager
        soundboard_manager.register_change_callback(mock_broadcast)
        
        # Trigger change event in soundboard manager manually
        soundboard_manager.notify_change()
        
        # Assert callback was fired successfully
        mock_broadcast.assert_called_once()

if __name__ == "__main__":
    unittest.main()
