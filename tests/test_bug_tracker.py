import unittest
import os
import shutil
import tempfile
from src.bug_tracker import BugTracker, CRASH_REPORTS_DIR

class TestBugTracker(unittest.TestCase):
    def setUp(self):
        # Create a mock exception
        try:
            raise ValueError("Test debug crash exception trigger")
        except Exception as e:
            self.test_exc = e
            self.test_tb = e.__traceback__

    def test_write_crash_report(self):
        # 1. Write the crash report
        report_path = BugTracker.write_crash_report(
            type(self.test_exc),
            self.test_exc,
            self.test_tb
        )
        
        # Verify path exists
        self.assertTrue(os.path.exists(report_path))
        self.assertTrue(report_path.startswith(CRASH_REPORTS_DIR))

        # 2. Inspect report contents
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check diagnostics headers are formatted correctly
        self.assertIn("EROSSOUNDX CRASH REPORT", content)
        self.assertIn("ValueError: Test debug crash exception trigger", content)
        self.assertIn("Environment Diagnostics", content)
        self.assertIn("Stack Trace", content)
        self.assertIn("OS:", content)

        # Cleanup generated crash report
        try:
            os.remove(report_path)
        except OSError:
            pass

if __name__ == "__main__":
    unittest.main()
