"""Provider-neutral image validation, process setup and durable immutable jobs."""

import json
import os
import re
import sqlite3
import struct
import subprocess
import time
import zlib
from contextlib import contextmanager

from extensions import canonical, require

MAX_BYTES = 128 * 1024 * 1024
WORKER_LEASE = 180


def _environment():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return env


def _creationflags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def validate_jpeg(data):
    """Validate bounded 8-bit sequential/progressive JPEG container structure.

    This checks frame/quantization/Huffman/scan dependencies, entropy-byte
    framing and complete EOI. It does not reconstruct pixels or claim to detect
    every invalid entropy code; the real image decoder still owns that step.
    """
    require(isinstance(data, bytes) and 4 < len(data) <= MAX_BYTES and data[:2] == b"\xff\xd8", "cli_output_invalid")
    offset, frame, scans, restart = 2, None, 0, 0
    quant, huffman, observed = set(), set(), set()
    segments = 0
    while offset < len(data):
        segments += 1
        require(segments <= 65536 and data[offset] == 255, "cli_output_invalid")
        while offset < len(data) and data[offset] == 255:
            offset += 1
        require(offset < len(data), "cli_output_invalid")
        marker = data[offset]
        offset += 1
        if marker == 0xD9:
            require(
                frame is not None and scans > 0 and observed == set(frame[3]) and offset == len(data),
                "cli_output_invalid",
            )
            return dict(width=frame[0], height=frame[1])
        require(
            marker not in (0, 1, 0xD8) and not 0xD0 <= marker <= 0xD7 and offset + 2 <= len(data), "cli_output_invalid"
        )
        size = struct.unpack_from(">H", data, offset)[0]
        require(size >= 2 and offset + size <= len(data), "cli_output_invalid")
        body = data[offset + 2 : offset + size]
        offset += size
        if marker in (0xC0, 0xC1, 0xC2):
            require(frame is None and len(body) >= 6, "cli_output_invalid")
            precision, height, width, count = struct.unpack_from(">BHHB", body)
            require(
                precision == 8
                and count in (1, 3, 4)
                and len(body) == 6 + 3 * count
                and 0 < width <= 8192
                and 0 < height <= 8192
                and width * height * count <= MAX_BYTES,
                "cli_output_invalid",
            )
            components = {}
            for index in range(count):
                name, sampling, table = body[6 + 3 * index : 9 + 3 * index]
                require(
                    name not in components and 1 <= sampling >> 4 <= 4 and 1 <= sampling & 15 <= 4 and table <= 3,
                    "cli_output_invalid",
                )
                components[name] = table
            frame = (width, height, marker, components)
        elif marker == 0xDB:
            index = 0
            require(bool(body), "cli_output_invalid")
            while index < len(body):
                kind = body[index]
                width = 2 if kind >> 4 == 1 else 1
                require(
                    kind >> 4 in (0, 1) and kind & 15 <= 3 and index + 1 + 64 * width <= len(body), "cli_output_invalid"
                )
                values = struct.unpack_from(">64H" if width == 2 else ">64B", body, index + 1)
                require(all(values), "cli_output_invalid")
                quant.add(kind & 15)
                index += 1 + 64 * width
        elif marker == 0xC4:
            index = 0
            require(bool(body), "cli_output_invalid")
            while index < len(body):
                require(index + 17 <= len(body), "cli_output_invalid")
                kind, counts = body[index], body[index + 1 : index + 17]
                count = sum(counts)
                require(
                    kind >> 4 in (0, 1) and kind & 15 <= 3 and 0 < count <= 256 and index + 17 + count <= len(body),
                    "cli_output_invalid",
                )
                space = 1
                for value in counts:
                    space = space * 2 - value
                    require(space >= 0, "cli_output_invalid")
                symbols = body[index + 17 : index + 17 + count]
                require(len(set(symbols)) == count and (kind >> 4 != 0 or max(symbols) <= 11), "cli_output_invalid")
                huffman.add((kind >> 4, kind & 15))
                index += 17 + count
        elif marker == 0xDD:
            require(len(body) == 2, "cli_output_invalid")
            restart = struct.unpack(">H", body)[0]
        elif marker == 0xDA:
            require(frame is not None and len(body) >= 6, "cli_output_invalid")
            count = body[0]
            require(1 <= count <= len(frame[3]) and len(body) == 4 + 2 * count, "cli_output_invalid")
            start, end, approx = body[-3:]
            high, low = approx >> 4, approx & 15
            require(high <= 13 and low <= 13 and (high == 0 or high == low + 1), "cli_output_invalid")
            require(
                (start == 0 and end == 63 and approx == 0)
                if frame[2] != 0xC2
                else (0 <= start <= end <= 63 and (end == 0 if start == 0 else count == 1)),
                "cli_output_invalid",
            )
            selected = set()
            for index in range(count):
                name, tables = body[1 + index * 2 : 3 + index * 2]
                require(
                    name in frame[3]
                    and name not in selected
                    and tables >> 4 <= 3
                    and tables & 15 <= 3
                    and frame[3][name] in quant,
                    "cli_output_invalid",
                )
                if start == 0 and high == 0:
                    require((0, tables >> 4) in huffman, "cli_output_invalid")
                if end > 0:
                    require((1, tables & 15) in huffman, "cli_output_invalid")
                selected.add(name)
            if start == 0:
                observed.update(selected)
            scans += 1
            require(scans <= 1024, "cli_output_invalid")
            entropy_bytes, expected_restart = 0, 0
            while offset < len(data):
                if data[offset] != 255:
                    entropy_bytes += 1
                    offset += 1
                    continue
                marker_start = offset
                while offset < len(data) and data[offset] == 255:
                    offset += 1
                require(offset < len(data), "cli_output_invalid")
                value = data[offset]
                if value == 0:
                    require(offset == marker_start + 1, "cli_output_invalid")
                    entropy_bytes += 1
                    offset += 1
                elif 0xD0 <= value <= 0xD7:
                    require(restart > 0 and value == 0xD0 + expected_restart, "cli_output_invalid")
                    expected_restart = (expected_restart + 1) % 8
                    offset += 1
                else:
                    offset = marker_start
                    break
            require(entropy_bytes > 0, "cli_output_invalid")
        else:
            require(0xE0 <= marker <= 0xEF or marker == 0xFE, "cli_output_invalid")
    raise ValueError("cli_output_invalid")


def validate_png(data):
    """Decode PNG chunks, CRCs, zlib stream and scanline filters (bounded)."""
    require(8 < len(data) <= MAX_BYTES and data[:8] == b"\x89PNG\r\n\x1a\n", "cli_output_invalid")
    offset, header, packed, ended = 8, None, bytearray(), False
    while offset < len(data):
        require(offset + 12 <= len(data), "cli_output_invalid")
        size, kind = struct.unpack_from(">I4s", data, offset)
        end = offset + 12 + size
        require(end <= len(data) and size <= MAX_BYTES, "cli_output_invalid")
        body = data[offset + 8 : offset + 8 + size]
        require(
            zlib.crc32(kind + body) & 0xFFFFFFFF == struct.unpack_from(">I", data, offset + 8 + size)[0],
            "cli_output_invalid",
        )
        if kind == b"IHDR":
            require(header is None and offset == 8 and size == 13, "cli_output_invalid")
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            require(header is not None, "cli_output_invalid")
            packed.extend(body)
        elif kind == b"IEND":
            require(size == 0 and end == len(data), "cli_output_invalid")
            ended = True
            break
        elif kind[:1].isupper() and kind != b"PLTE":
            raise ValueError("cli_output_invalid")
        offset = end
    require(header and ended and packed, "cli_output_invalid")
    width, height, depth, color, compression, filtering, interlace = header
    # ImageGen produces non-interlaced 8-bit RGB/RGBA. Other legal PNG formats
    # fail explicitly rather than passing a signature-only content check.
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color)
    require(
        channels
        and depth == 8
        and compression == filtering == interlace == 0
        and 0 < width <= 8192
        and 0 < height <= 8192,
        "cli_output_invalid",
    )
    stride = width * channels
    expected = (stride + 1) * height
    require(expected <= MAX_BYTES, "cli_output_invalid")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(packed), expected + 1)
    require(
        len(raw) == expected and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
        "cli_output_invalid",
    )
    previous = bytearray(stride)
    for row in range(height):
        start = row * (stride + 1)
        mode = raw[start]
        require(mode <= 4, "cli_output_invalid")
        current = bytearray(raw[start + 1 : start + 1 + stride])
        if mode:
            for index in range(stride):
                a = current[index - channels] if index >= channels else 0
                b = previous[index]
                c = previous[index - channels] if index >= channels else 0
                if mode == 1:
                    value = a
                elif mode == 2:
                    value = b
                elif mode == 3:
                    value = (a + b) // 2
                else:
                    p = a + b - c
                    distances = (abs(p - a), abs(p - b), abs(p - c))
                    value = (a, b, c)[distances.index(min(distances))]
                current[index] = (current[index] + value) & 255
        previous = current
    return dict(width=width, height=height)


class DurableProvider:
    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=20)
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def read(self, key):
        require(isinstance(key, str) and re.fullmatch(r"[a-f0-9]{64}", key), "invalid job key")
        with self.db() as db:
            row = db.execute("SELECT body FROM jobs WHERE key=?", (key,)).fetchone()
        require(row is not None, "unknown local job")
        return json.loads(row[0])

    def write(self, key, **fields):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = json.loads(db.execute("SELECT body FROM jobs WHERE key=?", (key,)).fetchone()[0])
            if "terminal" not in current:
                current.update(fields)
                db.execute("UPDATE jobs SET body=? WHERE key=?", (canonical(current), key))
            return current

    @staticmethod
    def snapshot(key, state, outputs=None, error=None):
        return dict(job_id=key, state=state, outputs=outputs or {}, error=error)

    def lookup(self, key):
        return self.poll(key)

    def poll(self, key):
        record = self.read(key)
        if "terminal" in record:
            return record["terminal"]
        if time.time() - record["heartbeat"] > WORKER_LEASE:
            return self.finish(key, "failed", "cli_result_unknown")
        return self.snapshot(key, "queued" if record["stage"] in ("intent", "queued") else "running")

    def cancel(self, key):
        # Durable cancellation is observed by the owned worker even after the
        # editor/provider is reopened. No process lookup/kill by persisted PID.
        return self.finish(key, "cancelled")

    def result_manifest(self, key):
        record = self.read(key)
        require(record.get("terminal", {}).get("state") == "succeeded", "result not available")
        return record["result"]

    def _active(self, key, stage=None):
        values = dict(heartbeat=time.time())
        if stage:
            values["stage"] = stage
        return "terminal" not in self.write(key, **values)
