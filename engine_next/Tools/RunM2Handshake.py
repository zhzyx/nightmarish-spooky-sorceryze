"""Run reconnect, packet loss, interpolation recovery and drain over real UDP."""

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


def parse_lines(lines, pattern):
    expression = re.compile(pattern)
    return [match.groupdict() for line in lines if (match := expression.fullmatch(line))]


def run_handshake(server, client, report_path, duration_ms=8000, drain_after_ms=3000):
    started = time.monotonic()
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        keep = {"SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATH"}
        env = {name: os.environ[name] for name in keep if name in os.environ}
    else:
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(report_path.parent / "Home"),
            "TMPDIR": str(report_path.parent / "Temp"),
        }
        (report_path.parent / "Home").mkdir(exist_ok=True)
        (report_path.parent / "Temp").mkdir(exist_ok=True)
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
                str(duration_ms),
                "--drain-after-ms",
                str(drain_after_ms),
                "--drain-timeout-ms",
                "1000",
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
                str(duration_ms),
                "--seed",
                "101" if client_id == "A" else "202",
                "--client-id",
                client_id,
                "--m2-reconnect",
                "--trace-output",
                report_path.parent / f"client-{client_id}.jsonl",
            ]
            if client_id == "A":
                command.extend([
                    "--drop-first-input",
                    "--impairment-delay-ms",
                    "8",
                    "--impairment-jitter-ms",
                    "3",
                    "--impairment-queue-capacity",
                    "16",
                ])
            clients.append((client_id, popen(command, report_path.parent, env)))

        client_results = []
        for client_id, process in clients:
            stdout, stderr = process.communicate(timeout=max(10, duration_ms // 1000 + 15))
            client_results.append({
                "client_id": client_id,
                "returncode": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
            })
        server_stdout, server_stderr = server_process.communicate(timeout=max(10, duration_ms // 1000 + 15))
        lines.extend(server_stdout.splitlines())
        errors.extend(server_stderr.splitlines())
        result["server_returncode"] = server_process.returncode
        result["server_stdout"] = lines
        result["server_stderr"] = errors
        result["clients"] = client_results
        client_lines = {item["client_id"]: item["stdout"].splitlines() for item in client_results}
        welcomes = []
        for client_result in client_results:
            for match in parse_lines(
                client_result["stdout"].splitlines(),
                r"ENGINE_NEXT_CLIENT_WELCOME client_id=(?P<client_id>\S+) session_id=(?P<session_id>\d+) entity_id=(?P<entity_id>\d+) resumed=(?P<resumed>[01])",
            ):
                match["session_id"] = int(match["session_id"])
                match["entity_id"] = int(match["entity_id"])
                match["resumed"] = int(match["resumed"])
                welcomes.append(match)
        sessions = parse_lines(
            lines,
            r"ENGINE_NEXT_SESSION peer_id=(?P<peer_id>\d+) session_id=(?P<session_id>\d+) entity_id=(?P<entity_id>\d+)",
        )
        resumes = parse_lines(
            lines,
            r"ENGINE_NEXT_RESUME peer_id=(?P<peer_id>\d+) session_id=(?P<session_id>\d+) entity_id=(?P<entity_id>\d+) confirmed=(?P<confirmed>\d+)",
        )
        for collection in (sessions, resumes):
            for item in collection:
                for name, value in item.items():
                    item[name] = int(value)
        predictions = parse_lines(
            client_lines["A"],
            r"ENGINE_NEXT_CLIENT_PREDICTION client_id=A confirmed=(?P<confirmed>\d+) position_x=(?P<position_x>[\d.eE+-]+) history=(?P<history>\d+) corrections=(?P<corrections>\d+) retransmissions=(?P<retransmissions>\d+)",
        )
        remotes = parse_lines(
            client_lines["B"],
            r"ENGINE_NEXT_CLIENT_REMOTE client_id=B entity_id=(?P<entity_id>\d+) position_x=(?P<position_x>[\d.eE+-]+) status=(?P<status>\w+) samples=(?P<samples>\d+) server_time=(?P<server_time>\d+)",
        )
        client_resumes = parse_lines(
            client_lines["A"],
            r"ENGINE_NEXT_CLIENT_RESUME client_id=A session_id=(?P<session_id>\d+) entity_id=(?P<entity_id>\d+) confirmed=(?P<confirmed>\d+) error=(?P<error>[\d.eE+-]+)",
        )
        client_drains = []
        for client_result in client_results:
            client_drains.extend(
                parse_lines(
                    client_result["stdout"].splitlines(),
                    r"ENGINE_NEXT_CLIENT_DRAIN client_id=(?P<client_id>\S+) deadline_tick=(?P<deadline_tick>\d+)",
                )
            )
        client_closes = []
        for client_result in client_results:
            client_closes.extend(
                parse_lines(
                    client_result["stdout"].splitlines(),
                    r"ENGINE_NEXT_CLIENT_CLOSE client_id=(?P<client_id>\S+) drain=(?P<drain>[01])",
                )
            )
        drain_begins = parse_lines(
            lines, r"ENGINE_NEXT_DRAIN_BEGIN peers=(?P<peers>\d+) deadline_tick=(?P<deadline_tick>\d+)"
        )
        drain_acks = parse_lines(
            lines, r"ENGINE_NEXT_DRAIN_ACK peer_id=(?P<peer_id>\d+) session_id=(?P<session_id>\d+)"
        )
        drain_completes = parse_lines(
            lines,
            r"ENGINE_NEXT_DRAIN_COMPLETE notified=(?P<notified>\d+) acknowledged=(?P<acknowledged>\d+) forced=(?P<forced>\d+) resumed=(?P<resumed>\d+)",
        )
        impairments = []
        for client_result in client_results:
            impairments.extend(
                parse_lines(
                    client_result["stdout"].splitlines(),
                    r"ENGINE_NEXT_IMPAIRMENT client_id=(?P<client_id>\S+) dropped_input=(?P<dropped_input>\d+) dropped_loss=(?P<dropped_loss>\d+) dropped_overflow=(?P<dropped_overflow>\d+) high_water=(?P<high_water>\d+)",
                )
            )
        server_bounds = parse_lines(
            lines,
            r"ENGINE_NEXT_SERVER_BOUNDS ticks=(?P<ticks>\d+) input_high_water=(?P<input_high_water>\d+) enet_outgoing_high_water=(?P<enet_outgoing_high_water>\d+) poll_event_high_water=(?P<poll_event_high_water>\d+)",
        )
        client_bounds = []
        for client_result in client_results:
            client_bounds.extend(
                parse_lines(
                    client_result["stdout"].splitlines(),
                    r"ENGINE_NEXT_CLIENT_BOUNDS client_id=(?P<client_id>\S+) prediction_history=(?P<prediction_history>\d+) unconfirmed_transport=(?P<unconfirmed_transport>\d+) interpolation=(?P<interpolation>\d+) enet_outgoing_high_water=(?P<enet_outgoing_high_water>\d+) poll_event_high_water=(?P<poll_event_high_water>\d+)",
                )
            )
        for collection, names in (
            (predictions, ("confirmed", "position_x", "history", "corrections", "retransmissions")),
            (remotes, ("entity_id", "position_x", "samples", "server_time")),
            (client_resumes, ("session_id", "entity_id", "confirmed", "error")),
            (client_drains, ("deadline_tick",)),
            (client_closes, ("drain",)),
            (drain_begins, ("peers", "deadline_tick")),
            (drain_acks, ("peer_id", "session_id")),
            (drain_completes, ("notified", "acknowledged", "forced", "resumed")),
            (impairments, ("dropped_input", "dropped_loss", "dropped_overflow", "high_water")),
            (server_bounds, ("ticks", "input_high_water", "enet_outgoing_high_water", "poll_event_high_water")),
            (
                client_bounds,
                (
                    "prediction_history",
                    "unconfirmed_transport",
                    "interpolation",
                    "enet_outgoing_high_water",
                    "poll_event_high_water",
                ),
            ),
        ):
            for item in collection:
                for name in names:
                    item[name] = float(item[name]) if name in {"position_x", "error"} else int(item[name])
        initial_welcomes = [item for item in welcomes if item["resumed"] == 0]
        resumed_welcomes = [item for item in welcomes if item["resumed"] == 1]
        a_initial = next((item for item in initial_welcomes if item["client_id"] == "A"), {})
        impairment_a = next((item for item in impairments if item["client_id"] == "A"), {})
        result.update({
            "welcomes": welcomes,
            "server_sessions": sessions,
            "server_resumes": resumes,
            "client_resumes": client_resumes,
            "predictions": predictions,
            "remotes": remotes,
            "client_drains": client_drains,
            "client_closes": client_closes,
            "drain_begins": drain_begins,
            "drain_acks": drain_acks,
            "drain_completes": drain_completes,
            "impairments": impairments,
            "server_bounds": server_bounds,
            "client_bounds": client_bounds,
        })
        valid = (
            server_process.returncode == 0
            and all(item["returncode"] == 0 and not item["stderr"] for item in client_results)
            and not errors
            and len(initial_welcomes) == 2
            and len(resumed_welcomes) == 1
            and resumed_welcomes[0]["client_id"] == "A"
            and resumed_welcomes[0]["session_id"] == a_initial.get("session_id")
            and resumed_welcomes[0]["entity_id"] == a_initial.get("entity_id")
            and len(sessions) == 2
            and len({item["session_id"] for item in sessions}) == 2
            and len({item["entity_id"] for item in sessions}) == 2
            and len({item["peer_id"] for item in sessions}) == 2
            and {(item["session_id"], item["entity_id"]) for item in initial_welcomes}
            == {(item["session_id"], item["entity_id"]) for item in sessions}
            and len(resumes) == 1
            and resumes[0]["peer_id"] not in {item["peer_id"] for item in sessions}
            and resumes[0]["session_id"] == a_initial.get("session_id")
            and resumes[0]["entity_id"] == a_initial.get("entity_id")
            and 0 <= resumes[0]["confirmed"] <= 12
            and len(client_resumes) == 1
            and client_resumes[0]["session_id"] == resumes[0]["session_id"]
            and client_resumes[0]["entity_id"] == resumes[0]["entity_id"]
            and client_resumes[0]["confirmed"] == resumes[0]["confirmed"]
            and len(predictions) == 1
            and predictions[0]["confirmed"] == 24
            and predictions[0]["history"] == 0
            and abs(predictions[0]["position_x"] - 3.072) < 0.001
            and predictions[0]["corrections"] >= 1
            and predictions[0]["retransmissions"] >= 1
            and len(remotes) == 3
            and remotes[0]["status"] in {"interpolated", "held"}
            and remotes[1]["status"] == "stale_held"
            and remotes[2]["status"] in {"interpolated", "held"}
            and remotes[2]["server_time"] > remotes[1]["server_time"]
            and all(
                item["entity_id"] == a_initial.get("entity_id") and item["position_x"] > 0 and item["samples"] >= 2
                for item in remotes
            )
            and len(client_drains) == 2
            and {item["client_id"] for item in client_drains} == {"A", "B"}
            and len(client_closes) == 2
            and {item["client_id"] for item in client_closes} == {"A", "B"}
            and all(item["drain"] == 1 for item in client_closes)
            and len(drain_begins) == 1
            and drain_begins[0]["peers"] == 2
            and all(item["deadline_tick"] == drain_begins[0]["deadline_tick"] for item in client_drains)
            and len(drain_acks) == 2
            and len({item["session_id"] for item in drain_acks}) == 2
            and len(drain_completes) == 1
            and drain_completes[0]["notified"] == 2
            and drain_completes[0]["acknowledged"] == 2
            and drain_completes[0]["forced"] == 0
            and drain_completes[0]["resumed"] == 1
            and len(server_bounds) == 1
            and server_bounds[0]["ticks"] >= 1
            and server_bounds[0]["input_high_water"] <= 64
            and server_bounds[0]["enet_outgoing_high_water"] > 0
            and server_bounds[0]["poll_event_high_water"] > 0
            and len(client_bounds) == 2
            and all(
                item["prediction_history"] <= 256
                and item["unconfirmed_transport"] <= 256
                and item["interpolation"] <= 32
                and item["enet_outgoing_high_water"] > 0
                and item["poll_event_high_water"] > 0
                for item in client_bounds
            )
            and impairment_a.get("dropped_input") == 1
            and impairment_a.get("dropped_overflow") == 0
            and 0 < impairment_a.get("high_water", 0) <= 16
        )
        result["passed"] = valid
        if not valid:
            raise RuntimeError(
                "Reconnect, loss, interpolation recovery or drain validation failed: " + json.dumps(result)
            )
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
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
        print("ENGINE_NEXT_HANDSHAKE clients=2 resumes=1 stale_recoveries=1 graceful_acks=2 status=ok")
        print(json.dumps({"report": str(args.report), "trace_sha256": result["trace_sha256"]}, indent=2))
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
