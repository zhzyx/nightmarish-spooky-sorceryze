"""Verify real drain timeout and new-connection rejection are not graceful success."""

import argparse
import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from RunM2Handshake import digest, parse_lines, popen


class DrainConnectionGate:
    """Prepare the late client's real UDP handshake before the short drain window."""

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.settimeout(0.05)
        self.port = self.socket.getsockname()[1]
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.server_address = None
        self.client_address = None
        self.pending = None
        self.released = False
        self.forwarded_client_packets = 0
        self.closed_endpoint_notifications = 0
        self.errors = []
        self.thread = threading.Thread(target=self._forward, daemon=True)
        self.thread.start()

    def set_server(self, port):
        with self.lock:
            self.server_address = ("127.0.0.1", port)

    def release(self):
        with self.lock:
            if self.server_address is None or self.pending is None:
                self.errors.append("Late client was not ready at the drain event")
                return
            try:
                self.socket.sendto(self.pending, self.server_address)
            except OSError as error:
                self.errors.append(str(error))
                return
            self.pending = None
            self.released = True
            self.forwarded_client_packets += 1

    def _forward(self):
        while not self.stopping.is_set():
            try:
                data, address = self.socket.recvfrom(65536)
            except TimeoutError:
                continue
            except ConnectionResetError:
                # Windows reports ICMP after a client or server closes its UDP port.
                # Required application rejection and drain events are checked below.
                self.closed_endpoint_notifications += 1
                continue
            except OSError as error:
                if not self.stopping.is_set():
                    self.errors.append(str(error))
                return
            with self.lock:
                try:
                    if address == self.server_address:
                        if self.client_address is not None:
                            self.socket.sendto(data, self.client_address)
                    elif self.client_address is None or address == self.client_address:
                        self.client_address = address
                        if self.released:
                            self.socket.sendto(data, self.server_address)
                            self.forwarded_client_packets += 1
                        else:
                            self.pending = data
                            self.ready.set()
                except OSError as error:
                    self.errors.append(str(error))
                    return

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=1)
        self.socket.close()


def run_drain_faults(server, client, report_path):
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for name in list(env):
        if "GODOT" in name.upper():
            env.pop(name, None)
    lines = []
    errors = []
    events = queue.Queue()
    processes = []
    result = {"passed": False, "expected_failure": True, "clients": [], "errors": []}
    gate = DrainConnectionGate()
    try:
        # C reaches its first ENet packet before the server's drain clock starts.
        late_client = popen(
            [
                client,
                "--connect",
                "127.0.0.1",
                "--port",
                str(gate.port),
                "--duration-ms",
                "8000",
                "--seed",
                "303",
                "--client-id",
                "C",
                "--trace-output",
                report_path.parent / "fault-client-C.jsonl",
            ],
            report_path.parent,
            env,
        )
        processes.append(("C", late_client))
        if not gate.ready.wait(timeout=8):
            raise RuntimeError("Late client did not prepare its initial UDP packet")
        server_process = popen(
            [
                server,
                "--bind",
                "127.0.0.1",
                "--port",
                "0",
                "--duration-ms",
                "8000",
                "--drain-after-ms",
                "2000",
                "--drain-timeout-ms",
                "200",
                "--seed",
                "41",
                "--trace-output",
                report_path.parent / "fault-server.jsonl",
            ],
            report_path.parent,
            env,
        )
        processes.append(("server", server_process))

        def read_output():
            for line in server_process.stdout:
                line = line.rstrip()
                if re.fullmatch(r"ENGINE_NEXT_DRAIN_BEGIN peers=2 deadline_tick=\d+", line):
                    gate.release()
                lines.append(line)
                events.put(line)
            events.put(None)

        def read_error():
            errors.extend(line.rstrip() for line in server_process.stderr)

        output_reader = threading.Thread(target=read_output, daemon=True)
        error_reader = threading.Thread(target=read_error, daemon=True)
        output_reader.start()
        error_reader.start()

        def wait_for(pattern, timeout):
            expression = re.compile(pattern)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    line = events.get(timeout=max(0.01, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if line is None:
                    break
                match = expression.fullmatch(line)
                if match:
                    return match
            raise RuntimeError("Missing server event: " + pattern)

        port_match = wait_for(r"ENGINE_NEXT_SERVER_READY port=(?P<port>\d+)", 8)
        port = int(port_match.group("port"))
        gate.set_server(port)
        for client_id in ("A", "B"):
            command = [
                client,
                "--connect",
                "127.0.0.1",
                "--port",
                str(port),
                "--duration-ms",
                "6000",
                "--seed",
                "101" if client_id == "A" else "202",
                "--client-id",
                client_id,
                "--m2-reconnect",
                "--trace-output",
                report_path.parent / f"fault-client-{client_id}.jsonl",
            ]
            if client_id == "B":
                command.append("--withhold-drain-ack")
            processes.append((client_id, popen(command, report_path.parent, env)))

        wait_for(r"ENGINE_NEXT_DRAIN_BEGIN peers=2 deadline_tick=(?P<deadline>\d+)", 6)
        client_results = []
        for client_id, process in processes:
            if client_id == "server":
                continue
            stdout, stderr = process.communicate(timeout=10)
            client_results.append({
                "client_id": client_id,
                "returncode": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
            })
        server_process.wait(timeout=10)
        output_reader.join(timeout=3)
        error_reader.join(timeout=3)
        if output_reader.is_alive() or error_reader.is_alive():
            raise RuntimeError("Server output readers did not finish")
        if gate.errors or not gate.released or gate.forwarded_client_packets == 0:
            raise RuntimeError("Late client gate failed: " + repr(gate.errors))
        result["late_client_gate"] = {
            "prepared_before_server_start": gate.ready.is_set(),
            "released_on_drain_begin": gate.released,
            "forwarded_client_packets": gate.forwarded_client_packets,
            "closed_endpoint_notifications": gate.closed_endpoint_notifications,
        }
        result.update({
            "server_returncode": server_process.returncode,
            "server_stdout": lines,
            "server_stderr": errors,
            "clients": client_results,
        })
        drain_completes = parse_lines(
            lines,
            r"ENGINE_NEXT_DRAIN_COMPLETE notified=(?P<notified>\d+) acknowledged=(?P<acknowledged>\d+) forced=(?P<forced>\d+) resumed=(?P<resumed>\d+)",
        )
        drain_rejects = parse_lines(
            lines,
            r"ENGINE_NEXT_REJECT peer_id=(?P<peer_id>\d+) type=(?P<type>\d+) reason=(?P<reason>\d+) fatal=(?P<fatal>\d+)",
        )
        late_lines = next(item["stdout"].splitlines() for item in client_results if item["client_id"] == "C")
        late_rejects = parse_lines(
            late_lines, r"ENGINE_NEXT_CLIENT_REJECT client_id=C reason=(?P<reason>\d+) fatal=(?P<fatal>\d+)"
        )
        result["drain_completes"] = drain_completes
        result["drain_rejects"] = drain_rejects
        result["late_rejects"] = late_rejects
        result["drain_timeouts"] = parse_lines(lines, r"ENGINE_NEXT_DRAIN_TIMEOUT peer_id=(?P<peer_id>\d+)")
        result["drain_acks"] = parse_lines(
            lines, r"ENGINE_NEXT_DRAIN_ACK peer_id=(?P<peer_id>\d+) session_id=(?P<session_id>\d+)"
        )
        return_codes = {item["client_id"]: item["returncode"] for item in client_results}
        valid = (
            server_process.returncode == 1
            and return_codes == {"A": 0, "B": 1, "C": 1}
            and not next(item for item in client_results if item["client_id"] == "A")["stderr"]
            and len(drain_completes) == 1
            and drain_completes[0]["notified"] == "2"
            and drain_completes[0]["acknowledged"] == "1"
            and drain_completes[0]["forced"] == "1"
            and drain_completes[0]["resumed"] == "1"
            and len(result["drain_timeouts"]) == 1
            and len(result["drain_acks"]) == 1
            and len(drain_rejects) == 1
            and drain_rejects[0]["type"] == "1"
            and drain_rejects[0]["reason"] == "8"
            and drain_rejects[0]["fatal"] == "0"
            and len(late_rejects) == 1
            and late_rejects[0]["reason"] == "8"
            and late_rejects[0]["fatal"] == "0"
            and any("ENGINE_NEXT_CLIENT_DRAIN_WITHHELD client_id=B" in item["stdout"] for item in client_results)
            and "ENGINE_NEXT_RUNTIME role=server network=ok status=ok" not in lines
        )
        result["passed"] = valid
        if not valid:
            raise RuntimeError("Drain faults were not observed exactly: " + json.dumps(result))
        result["trace_sha256"] = {
            name: digest(report_path.parent / name)
            for name in ("fault-server.jsonl", "fault-client-A.jsonl", "fault-client-B.jsonl", "fault-client-C.jsonl")
        }
        return result
    except Exception as error:
        result["errors"].append(str(error))
        raise
    finally:
        gate.close()
        for _, process in processes:
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
        result = run_drain_faults(args.server, args.client, args.report)
        print("ENGINE_NEXT_DRAIN_NEGATIVE timeout=1 rejected_new_peer=1 status=ok")
        print(json.dumps({"report": str(args.report), "trace_sha256": result["trace_sha256"]}, indent=2))
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
