"""
Unit tests for external tool (ADB, FFmpeg) discovery and encoder selection.
"""

import os
import shutil
import sys
import unittest
from unittest.mock import patch, MagicMock

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, "windows_screen_extend", "core"))

import server


class TestToolsDiscovery(unittest.TestCase):
    def test_find_ffmpeg_when_binary_present(self):
        """find_ffmpeg finds the bundled bin/ffmpeg.exe if present."""
        ffmpeg_bin = os.path.join(base_dir, "windows_screen_extend", "bin", "ffmpeg.exe")
        if os.path.exists(ffmpeg_bin):
            found = server.find_ffmpeg()
            self.assertIsNotNone(found)
            self.assertTrue(os.path.exists(found))

    def test_find_adb_when_binary_present(self):
        """find_adb finds the bundled bin/adb.exe or system adb."""
        found = server.find_adb()
        self.assertIsNotNone(found)
        self.assertTrue(found.lower().endswith("adb.exe") or found == "adb")

    def test_detect_best_encoder_prioritizes_hardware(self):
        """detect_best_encoder picks NVENC/QSV/AMF before falling back to libx264."""
        # Mock FFmpeg -encoders output with nvenc
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(return_value=0, stdout="V....D h264_nvenc NVIDIA NVENC H.264")
            enc = server.detect_best_encoder("mock_ffmpeg")
            self.assertEqual(enc, "h264_nvenc")

            # Mock FFmpeg -encoders output with QSV
            mock_run.return_value = MagicMock(return_value=0, stdout="V..... h264_qsv Intel QuickSync H.264")
            enc = server.detect_best_encoder("mock_ffmpeg")
            self.assertEqual(enc, "h264_qsv")

            # Mock FFmpeg -encoders output with CPU only
            mock_run.return_value = MagicMock(return_value=0, stdout="V....D libx264 H.264 / AVC")
            enc = server.detect_best_encoder("mock_ffmpeg")
            self.assertEqual(enc, "libx264")


if __name__ == "__main__":
    unittest.main()
