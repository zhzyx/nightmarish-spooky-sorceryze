"""Run one real next_server and two real next_client processes over UDP."""

import argparse
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def popen(command, cwd, env):
    return subprocess.Popen(
        [str(value) for value in command],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=os.name != "nt",
    )


def run_handshake(server, client, report_path):
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for name in list(env):
        if "GODOT" in name.upper():
            env.pop(name, None)
    lines = []
    errors = []
    output_queue = queue.Queue()
    server_process = None
    clients = []
    result = {"passed": False, "clients": [], "server_sessions": [], "errors": []}
    try:
        server_process = popen(
            [
                server,
                "--bind",
                "127.0.0.1",
                "--port",
                "0",
                "--duration-ms",
                "5000",
                "--seed",
                "41",
                "--trace-output",
                report_path.parent / "server.jsonl",
            ],
            report_path.parent,
            env,
        )

        def read_server_output():
            for line in server_process.stdout:
                lines.append(line.rstrip())
                output_queue.put(line.rstrip())
            output_queue.put(None)

        def read_server_error():
            for line in server_process.stderr:
                errors.append(line.rstrip())

        threading.Thread(target=read_server_output, daemon=True).start()
        threading.Thread(target=read_server_error, daemon=True).start()
        deadline = time.monotonic() + 8
        port = None
        while time.monotonic() < deadline and port is None:
            try:
                line = output_queue.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty as error:
                raise RuntimeError("Server did not report a bound port") from error
            if line is None:
                raise RuntimeError("Server exited before reporting a bound port")
            match = re.fullmatch(r"ENGINE_NEXT_SERVER_READY port=(\d+)", line)
            if match and int(match.group(1)) > 0:
                port = int(match.group(1))
        if port is None:
            raise RuntimeError("Server did not report a valid port")

        for client_id in ("A", "B"):
            command = [
                client,
                "--connect",
                "127.0.0.1",
                "--port",
                str(port),
                "--duration-ms",
                "5000",
                "--seed",
                "101" if client_id == "A" else "202",
                "--client-id",
                client_id,
                "--trace-output",
                report_path.parent / f"client-{client_id}.jsonl",
            ]
            clients.append((client_id, popen(command, report_path.parent, env)))

        client_results = []
        for client_id, process in clients:
            stdout, stderr = process.communicate(timeout=10)
            client_results.append({
                "client_id": client_id,
                "returncode": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
            })
        server_stdout, server_stderr = server_process.communicate(timeout=10)
        lines.extend(server_stdout.splitlines())
        errors.extend(server_stderr.splitlines())
        result["server_returncode"] = server_process.returncode
        result["server_stdout"] = lines
        result["server_stderr"] = errors
        result["clients"] = client_results

        welcomes = []
        for client_result in client_results:
            for line in client_result["stdout"].splitlines():
                match = re.fullmatch(
                    r"ENGINE_NEXT_CLIENT_WELCOME client_id=(\S+) session_id=(\d+) entity_id=(\d+)",
                    line,
                )
                if match:
                    welcomes.append({
                        "client_id": match.group(1),
                        "session_id": int(match.group(2)),
                        "entity_id": int(match.group(3)),
                    })
        sessions = []
        for line in lines:
            match = re.fullmatch(r"ENGINE_NEXT_SESSION peer_id=(\d+) session_id=(\d+) entity_id=(\d+)", line)
            if match:
                sessions.append({
                    "peer_id": int(match.group(1)),
                    "session_id": int(match.group(2)),
                    "entity_id": int(match.group(3)),
                })
        predictions = []
        remotes = []
        for client_result in client_results:
            for line in client_result["stdout"].splitlines():
                match = re.fullmatch(
                    r"ENGINE_NEXT_CLIENT_PREDICTION client_id=A confirmed=(\d+) position_x=([\d.eE+-]+) history=(\d+) corrections=(\d+)",
                    line,
                )
                if match:
                    predictions.append({
                        "confirmed": int(match.group(1)),
                        "position_x": float(match.group(2)),
                        "history": int(match.group(3)),
                        "corrections": int(match.group(4)),
                    })
                match = re.fullmatch(
                    r"ENGINE_NEXT_CLIENT_REMOTE client_id=B entity_id=(\d+) position_x=([\d.eE+-]+) status=(\w+) samples=(\d+)",
                    line,
                )
                if match:
                    remotes.append({
                        "entity_id": int(match.group(1)),
                        "position_x": float(match.group(2)),
                        "status": match.group(3),
                        "samples": int(match.group(4)),
                    })
        result["welcomes"] = welcomes
        result["server_sessions"] = sessions
        result["predictions"] = predictions
        result["remotes"] = remotes
        valid = (
            server_process.returncode == 0
            and all(item["returncode"] == 0 and not item["stderr"] for item in client_results)
            and not errors
            and len(welcomes) == 2
            and len(sessions) == 2
            and len({item["session_id"] for item in welcomes}) == 2
            and len({item["entity_id"] for item in welcomes}) == 2
            and len({item["peer_id"] for item in sessions}) == 2
            and {(item["session_id"], item["entity_id"]) for item in welcomes}
            == {(item["session_id"], item["entity_id"]) for item in sessions}
            and len(predictions) == 1
            and predictions[0]["confirmed"] == 24
            and predictions[0]["history"] == 0
            and abs(predictions[0]["position_x"] - 3.072) < 0.001
            and len(remotes) == 1
            and remotes[0]["entity_id"] in {item["entity_id"] for item in sessions}
            and remotes[0]["position_x"] > 0
            and remotes[0]["status"] in {"interpolated", "held"}
            and remotes[0]["samples"] >= 2
        )
        result["passed"] = valid
        if not valid:
            raise RuntimeError("Two-client handshake validation failed: " + json.dumps(result))
        result["trace_sha256"] = {
            name: digest(report_path.parent / name) for name in ("server.jsonl", "client-A.jsonl", "client-B.jsonl")
        }
        return result
    except Exception as error:
        result["errors"].append(str(error))
        raise
    finally:
        if server_process is not None and server_process.poll() is None:
            server_process.terminate()
            try:
                server_process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.communicate(timeout=3)
        for _, process in clients:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=3)
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_handshake(args.server, args.client, args.report)
        print("ENGINE_NEXT_HANDSHAKE clients=2 distinct_sessions=2 distinct_entities=2 status=ok")
        print(json.dumps({"report": str(args.report), "trace_sha256": result["trace_sha256"]}, indent=2))
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
