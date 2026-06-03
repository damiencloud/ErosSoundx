import unittest
import socket
from src.api_server import is_local_ip, APIServerManager

class TestQRPairingAndLocalAPI(unittest.TestCase):
    def test_is_local_ip(self):
        # Test loopback and private subnets (IPv4)
        self.assertTrue(is_local_ip("127.0.0.1"))
        self.assertTrue(is_local_ip("192.168.1.50"))
        self.assertTrue(is_local_ip("10.0.0.1"))
        self.assertTrue(is_local_ip("172.16.42.1"))
        
        # Test link-local
        self.assertTrue(is_local_ip("169.254.10.12"))

        # Test public IPs (should return False)
        self.assertFalse(is_local_ip("8.8.8.8"))
        self.assertFalse(is_local_ip("204.79.197.200"))
        
        # Test IPv6 loopback and private ranges
        self.assertTrue(is_local_ip("::1"))
        self.assertTrue(is_local_ip("fe80::1"))

    def test_token_generation(self):
        # Generate token and verify length and characters
        token = APIServerManager.generate_token()
        self.assertEqual(len(token), 6)
        self.assertTrue(token.isalnum())
        self.assertTrue(token.isupper())

    def test_local_ip_detection(self):
        manager = APIServerManager.get_instance()
        ip = manager.get_local_ip()
        self.assertIsNotNone(ip)
        
        # Detected IP should be valid local IP
        self.assertTrue(is_local_ip(ip))

if __name__ == "__main__":
    unittest.main()
