"""Submit one authorized instruction to an explicitly identified macOS editor.

The ordinary TCP bridge retains its confirmation policy. This separate channel
uses kernel Unix peer identity in both directions; discovery is not authority.
Run with Apple's /usr/bin/python3 from the authorized Codex desktop process tree.
"""

import argparse
import ctypes
import json
import os
import socket
import stat
import struct
import sys
import time
import uuid
from pathlib import Path


class InstructionClientError(Exception):
    pass


class _BsdInfo(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
        ("xstatus", ctypes.c_uint32),
        ("pid", ctypes.c_uint32),
        ("ppid", ctypes.c_uint32),
        ("uid", ctypes.c_uint32),
        ("gid", ctypes.c_uint32),
        ("ruid", ctypes.c_uint32),
        ("rgid", ctypes.c_uint32),
        ("svuid", ctypes.c_uint32),
        ("svgid", ctypes.c_uint32),
        ("rfu", ctypes.c_uint32),
        ("comm", ctypes.c_char * 16),
        ("name", ctypes.c_char * 32),
        ("nfiles", ctypes.c_uint32),
        ("pgid", ctypes.c_uint32),
        ("pjobc", ctypes.c_uint32),
        ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32),
        ("nice", ctypes.c_int32),
        ("start_sec", ctypes.c_uint64),
        ("start_usec", ctypes.c_uint64),
    ]


def _server_birth(pid):
    if sys.platform != "darwin":
        raise InstructionClientError("trusted_instruction_unsupported")
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    library.proc_pidinfo.restype = ctypes.c_int
    value = _BsdInfo()
    count = library.proc_pidinfo(pid, 3, 0, ctypes.byref(value), ctypes.sizeof(value))
    if count != ctypes.sizeof(value) or value.pid != pid or value.uid != os.getuid() or not value.start_sec:
        raise InstructionClientError("engine_identity_unavailable")
    return value.start_sec, value.start_usec


def _peer_pid(connection):
    # sys/un.h: SOL_LOCAL=0, LOCAL_PEERPID=0x002. No JSON field supplies identity.
    return struct.unpack("=i", connection.getsockopt(0, 0x002, struct.calcsize("=i")))[0]


class EditorInstructionClient:
    def __init__(self, project, instance):
        if sys.platform != "darwin":
            raise InstructionClientError("trusted_instruction_unsupported")
        if type(instance) is not int or instance <= 1:
            raise InstructionClientError("explicit_observed_engine_pid_required")
        self.project = Path(project).resolve(strict=True)
        self.instance = instance
        descriptor = self.project / ".godot/editor/ai_control" / (str(instance) + ".json")
        if descriptor.stat().st_size > 8192:
            raise InstructionClientError("invalid_editor_discovery")
        info = json.loads(descriptor.read_text(encoding="utf-8"))
        if (
            info.get("protocol_version") != 1
            or info.get("pid") != instance
            or Path(info.get("project", "")).resolve() != self.project
            or not isinstance(info.get("instruction_socket"), str)
        ):
            raise InstructionClientError("trusted_instruction_channel_unavailable")
        self.path = Path(info["instruction_socket"])
        if (
            not self.path.is_absolute()
            or len(os.fsencode(self.path)) >= 104
            or self.path.resolve(strict=True) != self.path
        ):
            raise InstructionClientError("invalid_instruction_socket")
        directory = self.path.parent.lstat()
        endpoint = self.path.lstat()
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != os.getuid()
            or directory.st_mode & 0o077
            or not stat.S_ISSOCK(endpoint.st_mode)
            or endpoint.st_uid != os.getuid()
            or endpoint.st_mode & 0o077
        ):
            raise InstructionClientError("invalid_instruction_socket")
        # Capture the real, explicitly selected process now, not a PID from JSON.
        self.birth = _server_birth(instance)

    def request(self, message):
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(payload) > 32768:
            raise InstructionClientError("instruction_message_too_large")
        if _server_birth(self.instance) != self.birth:
            raise InstructionClientError("engine_identity_changed")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(7)
            connection.connect(str(self.path))
            if _peer_pid(connection) != self.instance or _server_birth(self.instance) != self.birth:
                raise InstructionClientError("instruction_server_identity_mismatch")
            connection.sendall(payload)
            chunks = bytearray()
            while b"\n" not in chunks:
                part = connection.recv(4096)
                if not part:
                    raise InstructionClientError("instruction_result_unknown")
                chunks.extend(part)
                if len(chunks) > 512 * 1024:
                    raise InstructionClientError("invalid_instruction_reply")
            if chunks.count(b"\n") != 1 or not chunks.endswith(b"\n"):
                raise InstructionClientError("invalid_instruction_reply")
            reply = json.loads(chunks.decode("utf-8"))
            if _server_birth(self.instance) != self.birth:
                raise InstructionClientError("instruction_result_unknown")
            if (
                not isinstance(reply, dict)
                or reply.get("protocol_version") != 1
                or reply.get("engine_pid") != self.instance
            ):
                raise InstructionClientError("invalid_instruction_reply")
            return reply

    def context(self):
        return self.request({"protocol_version": 1, "kind": "context"})

    def submit(self, text, expected, request_id, *, consultation_only=False):
        message = {
            "protocol_version": 1,
            "kind": "submit",
            "request_id": request_id,
            "text": text,
            "expected": expected,
        }
        if consultation_only:
            message["consultation_only"] = True
        return self.request(message)

    def status(self, request_id):
        return self.request({"protocol_version": 1, "kind": "status", "request_id": request_id})

    def retry_delivery(self, expected, request_id):
        return self.request({
            "protocol_version": 1,
            "kind": "retry-delivery",
            "request_id": request_id,
            "expected": expected,
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--instance", required=True, type=int, help="Actual engine PID already observed by the caller")
    commands = parser.add_subparsers(dest="command", required=True)
    context = commands.add_parser(
        "context", help="Read owner, generation and draft/queue hashes without text or credentials"
    )
    context.add_argument(
        "--wait", type=float, default=0, help="Wait up to 60 seconds for instruction_available; read-only polling"
    )
    context.add_argument(
        "--consultation-only", action="store_true", help="Wait for the per-message read-only text route"
    )
    submit = commands.add_parser("submit", help="Atomically submit ordinary text through the normal editor workflow")
    submit.add_argument("--text-file", required=True, help="UTF-8 file or - for stdin, at most 8192 bytes")
    submit.add_argument("--expected", required=True, type=Path, help="Previously read context JSON file")
    submit.add_argument("--request-id", default=None)
    submit.add_argument(
        "--consultation-only",
        action="store_true",
        help="Restrict this message to consultation without changing the selected mode or tool permissions",
    )
    retry = commands.add_parser(
        "retry-delivery", help="Retry only the original verified pending activation; never submit new acceptance"
    )
    retry.add_argument("--expected", required=True, type=Path, help="Fresh context from this running parent")
    retry.add_argument("--request-id", default=None)
    status = commands.add_parser("status", help="Recover a receipt without repeating submission")
    status.add_argument("request_id")
    args = parser.parse_args()
    try:
        client = EditorInstructionClient(args.project, args.instance)
        if args.command == "context":
            if not 0 <= args.wait <= 60:
                raise InstructionClientError("invalid_instruction_wait")
            result = client.context()
            deadline = time.monotonic() + args.wait
            while (
                args.wait
                and result.get("ok")
                and not result.get("context", {}).get(
                    "consultation_instruction_available" if args.consultation_only else "instruction_available"
                )
                and time.monotonic() < deadline
            ):
                time.sleep(min(0.2, max(0, deadline - time.monotonic())))
                result = client.context()
        elif args.command == "status":
            result = client.status(args.request_id)
        elif args.command == "retry-delivery":
            if args.expected.stat().st_size > 16384:
                raise InstructionClientError("invalid_expected_context")
            expected = json.loads(args.expected.read_text(encoding="utf-8"))
            if isinstance(expected, dict) and "context" in expected:
                expected = expected["context"]
            result = client.retry_delivery(expected, args.request_id or uuid.uuid4().hex)
        else:
            if args.text_file == "-":
                data = sys.stdin.buffer.read(8193)
            else:
                with Path(args.text_file).open("rb") as source:
                    data = source.read(8193)
            if len(data) > 8192:
                raise InstructionClientError("instruction_text_too_large")
            if args.expected.stat().st_size > 16384:
                raise InstructionClientError("invalid_expected_context")
            expected = json.loads(args.expected.read_text(encoding="utf-8"))
            if isinstance(expected, dict) and "context" in expected:
                expected = expected["context"]
            result = client.submit(
                data.decode("utf-8"),
                expected,
                args.request_id or uuid.uuid4().hex,
                consultation_only=args.consultation_only,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    except InstructionClientError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    except (OSError, ValueError, TypeError, KeyError):
        # Paths, message text and discovery credentials never enter diagnostics.
        print(json.dumps({"ok": False, "error": "instruction_client_failed"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
