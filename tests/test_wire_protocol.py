"""
Unit tests for the wire protocol shared between PC servers and Android client.
"""

import struct
import unittest

MSG = struct.Struct(">BBBBHH")
MSG_HELLO, MSG_TOUCH = 0, 1
TOUCH_DOWN, TOUCH_MOVE, TOUCH_UP = 0, 1, 2


class TestWireProtocol(unittest.TestCase):
    def test_msg_struct_size(self):
        """Protocol packet size must be exactly 8 bytes."""
        self.assertEqual(MSG.size, 8)

    def test_hello_packet_pack_unpack(self):
        """Hello packet transmits screen dimensions (width x height) in big-endian."""
        width = 1080
        height = 2400
        packet = MSG.pack(MSG_HELLO, 0, 0, 0, width, height)
        self.assertEqual(len(packet), 8)

        mtype, action, slot, pad, w, h = MSG.unpack(packet)
        self.assertEqual(mtype, MSG_HELLO)
        self.assertEqual(action, 0)
        self.assertEqual(slot, 0)
        self.assertEqual(pad, 0)
        self.assertEqual(w, 1080)
        self.assertEqual(h, 2400)

    def test_touch_down_packet(self):
        """Touch DOWN packet encodes action, slot index, and normalized coordinates (0..65535)."""
        x_norm = 32767  # center
        y_norm = 65535  # bottom
        slot = 1
        packet = MSG.pack(MSG_TOUCH, TOUCH_DOWN, slot, 0, x_norm, y_norm)

        mtype, action, slot_out, _, x, y = MSG.unpack(packet)
        self.assertEqual(mtype, MSG_TOUCH)
        self.assertEqual(action, TOUCH_DOWN)
        self.assertEqual(slot_out, 1)
        self.assertEqual(x, 32767)
        self.assertEqual(y, 65535)

    def test_touch_actions(self):
        """Tests DOWN (0), MOVE (1), and UP (2) actions."""
        for act in (TOUCH_DOWN, TOUCH_MOVE, TOUCH_UP):
            packet = MSG.pack(MSG_TOUCH, act, 0, 0, 100, 200)
            _, action_out, _, _, _, _ = MSG.unpack(packet)
            self.assertEqual(action_out, act)

    def test_stream_resolution_handshake(self):
        """Server responds to hello with 4-byte [width u16][height u16]."""
        stream_w, stream_h = 1920, 1080
        resp = struct.pack(">HH", stream_w, stream_h)
        self.assertEqual(len(resp), 4)
        w, h = struct.unpack(">HH", resp)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)

    def test_frame_header(self):
        """Each video access unit is prefixed by a 4-byte big-endian length."""
        frame_len = 45000
        header = struct.pack(">I", frame_len)
        self.assertEqual(len(header), 4)
        self.assertEqual(struct.unpack(">I", header)[0], 45000)


if __name__ == "__main__":
    unittest.main()
