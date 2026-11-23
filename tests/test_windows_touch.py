"""
Unit tests for the Windows Touch and Mouse Injector.
"""

import os
import sys
import unittest

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, "windows_screen_extend", "core"))

from server import WindowsTouchInjector, TOUCH_DOWN, TOUCH_MOVE, TOUCH_UP


class MockUser32:
    def __init__(self):
        self.cursor_pos = None
        self.mouse_events = []

    def SetCursorPos(self, x, y):
        self.cursor_pos = (x, y)
        return True

    def mouse_event(self, flags, dx, dy, data, extra):
        self.mouse_events.append(flags)
        return True


class TestWindowsTouchInjector(unittest.TestCase):
    def setUp(self):
        self.monitor = {
            "left": 100,
            "top": 200,
            "width": 1920,
            "height": 1080,
        }
        self.injector = WindowsTouchInjector(self.monitor)
        # Patch user32 with mock
        self.mock_user32 = MockUser32()
        import server
        server.user32 = self.mock_user32

    def test_coordinate_mapping_corners(self):
        """0 maps to left/top; 65535 maps to right/bottom bound."""
        # Top-left corner (0, 0)
        self.injector.handle(TOUCH_MOVE, 0, 0)
        self.assertEqual(self.mock_user32.cursor_pos, (100, 200))

        # Bottom-right corner (65535, 65535)
        self.injector.handle(TOUCH_MOVE, 65535, 65535)
        # 100 + 1920 = 2020 clamped to 2019
        self.assertEqual(self.mock_user32.cursor_pos, (2019, 1279))

        # Center (32767, 32767)
        self.injector.handle(TOUCH_MOVE, 32767, 32767)
        px, py = self.mock_user32.cursor_pos
        self.assertAlmostEqual(px, 100 + 1920 // 2, delta=2)
        self.assertAlmostEqual(py, 200 + 1080 // 2, delta=2)

    def test_touch_down_and_up_lifecycle(self):
        """Touch down sends MOUSEEVENTF_LEFTDOWN; touch up sends MOUSEEVENTF_LEFTUP."""
        self.assertFalse(self.injector.is_down)

        self.injector.handle(TOUCH_DOWN, 1000, 1000)
        self.assertTrue(self.injector.is_down)
        self.assertIn(0x0002, self.mock_user32.mouse_events)  # MOUSEEVENTF_LEFTDOWN

        self.injector.handle(TOUCH_UP, 1000, 1000)
        self.assertFalse(self.injector.is_down)
        self.assertIn(0x0004, self.mock_user32.mouse_events)  # MOUSEEVENTF_LEFTUP

    def test_release_all_failsafe(self):
        """release_all() ensures mouse button is never left held down when phone disconnects."""
        self.injector.handle(TOUCH_DOWN, 500, 500)
        self.assertTrue(self.injector.is_down)

        self.injector.release_all()
        self.assertFalse(self.injector.is_down)
        self.assertEqual(self.mock_user32.mouse_events[-1], 0x0004)  # MOUSEEVENTF_LEFTUP


if __name__ == "__main__":
    unittest.main()
