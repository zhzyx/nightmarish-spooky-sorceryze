"""Fixed-role authenticated local service. The operating system supplies the process identity."""

import argparse
import csv
import hashlib
import io
import ipaddress
import json
import os
import re
import select
import socket
import sqlite3
import ssl
import struct
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROLES = {"planner", "producer", "reviewer"}
HEX = re.compile(r"[0-9a-f]{64}")
MAX_REQUEST = 128 * 1024
MAX_RESULT = 900000


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def config(path, digest):
    file = Path(path)
    need(file.is_absolute() and file.is_file() and not file.is_symlink(), "Absolute installed configuration required")
    raw = file.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == digest, "Role configuration changed")
    return json.loads(raw)


def tree_sha256():
    root = Path(__file__).resolve().parents[4]
    directories = (
        "customizations/components/tianxuan/duobao",
        "customizations/components/tianxuan/sinan-workorders",
        "customizations/platforms/ai-access/host-http/runtime",
        "tools/codex_cli",
    )
    files = {root / "tools/ainative/owned_process.py", root / "tools/editor_provenance_process.py"}
    for directory in directories:
        for folder, children, names in os.walk(root / directory):
            children[:] = [name for name in children if name != "__pycache__"]
            need(all(not (Path(folder) / name).is_symlink() for name in children), "Linked role source directory")
            files.update(Path(folder) / name for name in names)
    entries = {}
    for path in files:
        need(path.is_file() and path.resolve() == path, "Installed role source required")
        entries[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(canonical(entries)).hexdigest()


def identity():
    if os.name != "nt":
        return "uid:" + str(os.geteuid())
    whoami = Path(os.environ["SystemRoot"]) / "System32/whoami.exe"
    value = subprocess.check_output(
        [str(whoami), "/user", "/fo", "csv", "/nh"], creationflags=subprocess.CREATE_NO_WINDOW
    )
    # The account name can be localized. Only the ASCII SID is used.
    row = next(csv.reader(io.StringIO(value.decode("mbcs"))))
    need(len(row) == 2 and re.fullmatch(r"S-1-[0-9-]+", row[1]), "Current role SID unavailable")
    return row[1]


def read_exact(conn, n):
    data = bytearray()
    while len(data) < n:
        chunk = conn.recv(min(n - len(data), 65536))
        if not chunk:
            raise EOFError("Incomplete role response")
        data.extend(chunk)
    return bytes(data)


def receive(conn, maximum):
    length = struct.unpack("!I", read_exact(conn, 4))[0]
    need(0 < length <= maximum, "Role packet exceeds bounds")
    return json.loads(read_exact(conn, length))


def send(conn, value, maximum):
    raw = canonical(value)
    need(len(raw) <= maximum, "Role packet exceeds bounds")
    conn.sendall(struct.pack("!I", len(raw)) + raw)


def endpoint(settings, server):
    address = ipaddress.ip_address(settings["address"])
    need(
        address.is_loopback or address.is_private and not address.is_unspecified and not address.is_multicast,
        "Role endpoint requires a fixed private address",
    )
    need(type(settings["port"]) is int and 0 < settings["port"] < 65536, "Invalid role service port")
    need(settings["role"] in ROLES and HEX.fullmatch(settings["peer_sha256"]), "Role peer must be pinned")
    ctx = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH if server else ssl.Purpose.SERVER_AUTH, cafile=settings["ca_file"]
    )
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain(settings["certificate_file"], settings["private_key_file"])
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx, (str(address), settings["port"])


def peer(conn, digest):
    need(hashlib.sha256(conn.getpeercert(binary_form=True)).hexdigest() == digest, "Wrong role peer certificate")


def client(settings, recover):
    role = settings["role"]
    if role == "producer":
        need(not recover, "Unknown producer may not be replayed")
        work = Path(os.environ["NATIVE_WORKSPACE"])
        need(work.name == "work" and HEX.fullmatch(work.parent.name), "Exact workspace execution required")
        need(work.parent.parent == Path(settings["worker_root"]), "Wrong installed producer workspace")
        payload = {
            "execution": work.parent.name,
            "worker_root": settings["worker_root"],
            "registry": settings["registry"],
        }
    else:
        raw = sys.stdin.buffer.read(100001)
        need(len(raw) <= 100000, "Role input exceeds limit")
        payload = json.loads(raw)
    request = {
        "role": role,
        "broker_sha256": settings["broker_sha256"],
        "service_sha256": settings["service_sha256"],
        "service_identity": settings["service_identity"],
        "tree_sha256": settings["tree_sha256"],
        "recover": recover,
        "payload": payload,
    }
    ctx, address = endpoint(settings, False)
    with (
        socket.create_connection(address, timeout=10) as sock,
        ctx.wrap_socket(sock, server_hostname=settings["server_name"]) as conn,
    ):
        peer(conn, settings["peer_sha256"])
        conn.settimeout(600)
        send(conn, request, MAX_REQUEST)
        result = receive(conn, MAX_RESULT)
    need(
        isinstance(result, dict)
        and set(result) == {"result", "request_sha256", "identity"}
        and result["identity"] == settings["service_identity"]
        and result["request_sha256"] == hashlib.sha256(canonical(request)).hexdigest(),
        "Unknown role outcome",
    )
    sys.stdout.buffer.write(canonical(result["result"]))


def launch(settings, request, conn, settings_path, digest, tls_generation):
    need(tree_sha256() == settings["tree_sha256"], "Role execution tree changed")
    # A regular file cannot contain a cache tree. Always load the verified sources.
    sys.pycache_prefix = __file__
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "duobao"))
    from native_check_runner import _process_helper
    from native_entry_runtime import load_config
    from native_workspace import absolute

    role = settings["role"]
    need(
        set(request)
        == {"role", "broker_sha256", "service_sha256", "service_identity", "tree_sha256", "recover", "payload"}
        and request["tree_sha256"] == settings["tree_sha256"]
        and request["service_sha256"] == digest
        and request["service_identity"] == settings["identity"] == identity()
        and role == request["role"]
        and request["broker_sha256"] == settings["broker_sha256"]
        and type(request["recover"]) is bool,
        "Wrong role or broker binding",
    )
    broker, template = load_config(settings["broker_file"], settings["broker_sha256"])
    payload = request["payload"]
    need(isinstance(payload, dict), "Closed service request required")
    recover = request["recover"]
    producer = role == "producer"
    script = Path(__file__).with_name("native_entry_producer.py" if producer else "native_entry_runtime.py")
    need(hashlib.sha256(script.read_bytes()).hexdigest() == settings["script_sha256"], "Service entrypoint changed")
    args = [
        broker["python"],
        "-E",
        "-S",
        "-X",
        f"pycache_prefix={script}",
        "-B",
        "-X",
        "utf8",
        str(script),
        "--config",
        settings["broker_file"],
        "--sha256",
        settings["broker_sha256"],
    ]
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "SYSTEMROOT") if k in os.environ}
    if producer:
        need(
            set(payload) == {"execution", "worker_root", "registry"}
            and not recover
            and payload["worker_root"] == settings["worker_root"]
            and payload["registry"] == settings["registry"],
            "Producer requires installed execution roots",
        )
        key = payload["execution"]
        need(isinstance(key, str) and HEX.fullmatch(key), "Invalid producer execution")
        folder = absolute(Path(settings["worker_root"]) / key)
        work = absolute(folder / "work")
        env.update(NATIVE_WORKSPACE=str(work), NATIVE_CONTEXT=str(absolute(folder / "context.json")))
        args.extend(["--registry", str(absolute(settings["registry"]))])
        data = b""
    else:
        need(payload.get("role") == ("yanshi" if role == "planner" else "reviewer"), "Incompatible role request")
        need((template["task"]["agent_id"] == "yanshi") == (role == "planner"), "Incompatible installed role")
        key = payload["entry"]
        need(isinstance(key, str) and HEX.fullmatch(key), "Invalid role entry")
        data = canonical(payload)
        need(len(data) <= 100000, "Role input too large")
        if recover:
            args.append("--recover")
    credentials = [Path(settings[k]) for k in ("ca_file", "certificate_file", "private_key_file")] + [
        Path(broker["key_file"])
    ]

    def credential_generation():
        return [hashlib.sha256(path.read_bytes()).hexdigest() for path in credentials]

    generation = credential_generation()
    need(generation[:3] == tls_generation, "Service TLS generation withdrawn")

    def active():
        try:
            config(settings_path, digest)
            config(settings["broker_file"], settings["broker_sha256"])
            return generation == credential_generation() and not select.select([conn], [], [], 0)[0]
        except (OSError, ValueError):
            return False

    journal = Path(settings["journal"])
    need(journal.is_absolute(), "Private absolute role journal required")
    # Bind the original verified client, service identity, roots, command and
    # configuration generation. A new certificate or deployment cannot recover it.
    binding = hashlib.sha256(
        canonical({
            "payload": payload,
            "service": digest,
            "client": settings["peer_sha256"],
            "generation": generation,
            "identity": settings["identity"],
            "role": role,
        })
    ).hexdigest()
    need(active(), "Role authority withdrawn")
    with closing(sqlite3.connect(journal)) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS intents (entry TEXT PRIMARY KEY, binding TEXT NOT NULL, broker TEXT NOT NULL)"
        )
        if recover:
            need(
                db.execute("SELECT binding,broker FROM intents WHERE entry=?", (key,)).fetchone()
                == (binding, settings["broker_sha256"]),
                "No original matching service intent",
            )
        else:
            db.execute("INSERT INTO intents VALUES (?,?,?)", (key, binding, settings["broker_sha256"]))
            db.commit()
    # A peer sends exactly one request. Disconnect or extra data cancels this owned child.
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        source.write(data)
        source.seek(0)
        reasons = []

        need(active(), "Role authority withdrawn")

        code = _process_helper().run_owned(
            args,
            env=env,
            stdin=source,
            stdout=out,
            stderr=err,
            timeout=570,
            limit=MAX_RESULT,
            active=active,
            fail=reasons.append,
        )
        need(code == 0 and not reasons and active(), "Role result unknown; reconcile original intent")
        out.seek(0)
        result = json.load(out)
    return {
        "result": result,
        "request_sha256": hashlib.sha256(canonical(request)).hexdigest(),
        "identity": settings["identity"],
    }


def serve(settings_path, digest):
    settings = config(settings_path, digest)
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "Start role service with -I -S -B")
    who = identity()
    need(
        settings["identity"] == who and who not in {"uid:0", "S-1-5-18"},
        "Dedicated operating-system role identity required",
    )
    tls_files = [Path(settings[k]) for k in ("ca_file", "certificate_file", "private_key_file")]
    tls_generation = [hashlib.sha256(path.read_bytes()).hexdigest() for path in tls_files]
    ctx, address = endpoint(settings, True)
    with socket.create_server(
        address, family=socket.AF_INET6 if ":" in address[0] else socket.AF_INET, backlog=4
    ) as listener:
        while True:
            sock, _ = listener.accept()
            with sock:
                sock.settimeout(10)
                try:
                    with ctx.wrap_socket(sock, server_side=True) as conn:
                        peer(conn, settings["peer_sha256"])
                        # Configuration withdrawal before a new effect is terminal for that request.
                        config(settings_path, digest)
                        request = receive(conn, MAX_REQUEST)
                        need(
                            [hashlib.sha256(path.read_bytes()).hexdigest() for path in tls_files] == tls_generation,
                            "Restart role service after TLS rotation",
                        )
                        result = launch(settings, request, conn, settings_path, digest, tls_generation)
                        send(conn, result, MAX_RESULT)
                except (ValueError, KeyError, TypeError, EOFError, OSError, sqlite3.Error) as error:
                    print(
                        "Role request ended without confirmed reply:", type(error).__name__, file=sys.stderr, flush=True
                    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["call", "serve"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    if args.operation == "serve":
        need(not args.recover, "Cannot recover a service")
        serve(args.config, args.sha256)
    else:
        client(config(args.config, args.sha256), args.recover)
