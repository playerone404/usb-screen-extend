"""
Unit tests for the H.264 Annex-B Access Unit Parser (AUParser).
"""

import os
import sys
import unittest

# Add windows_screen_extend/core to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, "windows_screen_extend", "core"))

from server import AUParser


class TestAUParser(unittest.TestCase):
    def setUp(self):
        self.parser = AUParser()

    def test_single_nal_unit(self):
        """Feeding IDR frame followed by next frame emits the complete IDR access unit."""
        # Frame 1: IDR frame (type 5)
        nal_idr = b"\x00\x00\x00\x01\x25\x88\x11\x22\x33"
        # Frame 2: P frame (type 1)
        nal_p = b"\x00\x00\x00\x01\x21\x88\x44\x55\x66"
        # Frame 3: start code of subsequent frame to close Frame 2
        nal_next = b"\x00\x00\x00\x01\x21\x88\x77"

        aus = []
        self.parser.feed(nal_idr + nal_p + nal_next, aus)
        self.assertGreaterEqual(len(aus), 1)
        self.assertTrue(aus[0].startswith(b"\x00\x00\x00\x01\x25"))

    def test_sps_pps_idr_aggregation(self):
        """SPS (type 7) and PPS (type 8) must be packed together with IDR (type 5)."""
        sps = b"\x00\x00\x00\x01\x67\x42\x00\x1f"
        pps = b"\x00\x00\x00\x01\x68\xce\x3c\x80"
        idr = b"\x00\x00\x00\x01\x65\x88\xaa\xbb"
        next_p = b"\x00\x00\x00\x01\x41\x88\xcc"
        next_p2 = b"\x00\x00\x00\x01\x41\x88\xdd"

        aus = []
        self.parser.feed(sps + pps + idr + next_p + next_p2, aus)
        self.assertGreaterEqual(len(aus), 1)

        # The access unit should contain SPS, PPS, and IDR together
        au = aus[0]
        self.assertIn(b"\x67\x42", au)
        self.assertIn(b"\x68\xce", au)
        self.assertIn(b"\x65\x88", au)

    def test_fragmented_delivery(self):
        """AUParser must handle NAL units arriving in tiny 1-byte or 2-byte fragments."""
        data = (
            b"\x00\x00\x00\x01\x25\x88\xaa\xbb"
            b"\x00\x00\x00\x01\x21\x88\xcc\xdd"
            b"\x00\x00\x00\x01\x21\x88\xee"
        )
        aus = []
        for byte in data:
            self.parser.feed(bytes([byte]), aus)

        self.assertGreaterEqual(len(aus), 1)
        self.assertTrue(aus[0].startswith(b"\x00\x00\x00\x01\x25"))

    def test_buffer_cleanup_no_start_codes(self):
        """Garbage data without H.264 start codes must not cause unbounded memory growth."""
        garbage = b"A" * 100000
        aus = []
        self.parser.feed(garbage, aus)
        self.assertEqual(len(aus), 0)
        # Buffer should be trimmed to at most 3 bytes to detect next start code
        self.assertLessEqual(len(self.parser.buf), 3)

    def test_flush(self):
        """Calling flush() emits any remaining VCL frame in progress."""
        data = b"\x00\x00\x00\x01\x25\x88\xaa\xbb"
        aus = []
        self.parser.feed(data, aus)
        self.parser.flush(aus)
        self.assertEqual(len(aus), 1)
        self.assertIn(b"\x25\x88\xaa\xbb", aus[0])


if __name__ == "__main__":
    unittest.main()
