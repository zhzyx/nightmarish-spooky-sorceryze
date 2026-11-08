"""Portable JPEG fixtures: one constant DCT block, no imaging dependency."""

import hashlib
import struct
import unittest

from codex_provider import validate_jpeg


def segment(marker, body):
    return bytes((255, marker)) + struct.pack(">H", len(body) + 2) + body


def jpeg(progressive=False, components=1):
    # DC category zero and AC end-of-block each have the one-bit code 0.
    quant = segment(0xDB, bytes((0,)) + bytes((1,)) * 64)
    frame = segment(
        0xC2 if progressive else 0xC0,
        struct.pack(">BHHB", 8, 8, 8, components) + b"".join(bytes((i + 1, 0x11, 0)) for i in range(components)),
    )
    tables = segment(0xC4, bytes((0, 1)) + bytes(15) + bytes((0, 0x10, 1)) + bytes(15) + bytes((0,)))
    if progressive:
        scan = segment(0xDA, bytes((1, 1, 0, 0, 0, 0))) + b"\x7f"
        scan += segment(0xDA, bytes((1, 1, 0, 1, 63, 0))) + b"\x7f"
    else:
        bits = components * 2
        entropy = bytes(((1 << (8 - bits)) - 1,))
        scan = (
            segment(
                0xDA, bytes((components,)) + b"".join(bytes((i + 1, 0)) for i in range(components)) + bytes((0, 63, 0))
            )
            + entropy
        )
    return b"\xff\xd8" + quant + frame + tables + scan + b"\xff\xd9"


class JpegValidationTests(unittest.TestCase):
    def test_sequential_gray_rgb_cmyk_and_progressive_preserve_exact_input(self):
        for value in (jpeg(), jpeg(components=3), jpeg(components=4), jpeg(progressive=True)):
            before = hashlib.sha256(value).digest()
            self.assertEqual(validate_jpeg(value), {"width": 8, "height": 8})
            self.assertEqual(hashlib.sha256(value).digest(), before)

    def test_signature_only_truncated_and_trailing_bytes_are_rejected(self):
        good = jpeg()
        for value in (b"\xff\xd8\xff\xd9", good[:-1], good + b"trailing", good[:-2], good[:10]):
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                validate_jpeg(value)

    def test_missing_tables_frame_scan_and_entropy_are_rejected(self):
        good = jpeg()
        offsets = [good.index(bytes((255, marker))) for marker in (0xDB, 0xC0, 0xC4, 0xDA)]
        for start in offsets:
            size = struct.unpack_from(">H", good, start + 2)[0]
            value = good[:start] + good[start + 2 + size :]
            with self.subTest(marker=good[start + 1]), self.assertRaises(ValueError):
                validate_jpeg(value)
        with self.assertRaises(ValueError):
            validate_jpeg(good[:-3] + good[-2:])

    def test_bounds_bad_component_scan_and_huffman_tables_are_rejected(self):
        good = jpeg()
        frame, scan, table = (good.index(bytes((255, marker))) for marker in (0xC0, 0xDA, 0xC4))
        alterations = (
            (frame + 5, 255),
            (frame + 7, 255),
            (frame + 12, 4),
            (scan + 5, 2),
            (scan + 8, 64),
            (table + 5, 3),
        )
        for index, byte in alterations:
            value = bytearray(good)
            value[index] = byte
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_jpeg(bytes(value))

    def test_restart_markers_require_interval_and_sequence(self):
        good = jpeg()
        value = good[:-2] + b"\xff\xd0\x3f" + good[-2:]
        with self.assertRaises(ValueError):
            validate_jpeg(value)
        frame = value.index(b"\xff\xc0")
        value = value[:frame] + segment(0xDD, b"\x00\x01") + value[frame:]
        changed = bytearray(value)
        changed[value.index(b"\xff\xc0") + 8] = 16
        value = bytes(changed)
        self.assertEqual(validate_jpeg(value), {"width": 16, "height": 8})
        with self.assertRaises(ValueError):
            validate_jpeg(value.replace(b"\xff\xd0", b"\xff\xd3"))


if __name__ == "__main__":
    unittest.main()
