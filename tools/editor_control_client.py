"""Local AI editor-control client. Uses only Python's standard library.

Connected AI: discover capabilities, plan a declarative operation, route it, then
wait/query its real host result. Never interpret a pending approval as success.
"""

import argparse
import http.client
import json
import re
import sys
import time
import urllib.parse
import uuid
from pathlib import Path


class EditorControlError(Exception):
    pass


class EditorClient:
    def __init__(self, project, instance=None):
        self.project = Path(project).resolve(strict=True)
        candidates = []
        for path in sorted((self.project / ".godot/editor/ai_control").glob("*.json")):
            if instance is not None and path.stem != str(instance):
                continue
            try:
                if path.stat().st_size > 8192:
                    continue
                info = json.loads(path.read_text(encoding="utf-8"))
                endpoint = urllib.parse.urlsplit(info["url"])
                if (
                    info.get("protocol_version") != 1
                    or Path(info["project"]).resolve() != self.project
                    or endpoint.scheme != "http"
                    or endpoint.hostname != "127.0.0.1"
                    or not endpoint.port
                    or endpoint.username
                    or endpoint.password
                    or endpoint.path
                    or endpoint.query
                    or endpoint.fragment
                    or not re.fullmatch(r"[0-9a-f]{64}", info["token"])
                    or not re.fullmatch(r"[0-9a-f]{32}", info["session"])
                    or str(info["pid"]) != path.stem
                ):
                    continue
                self.info = info
                status, result = self.request("GET", "/v1/capabilities")
                # Permission-disabled editors are still live, selectable instances.
                if result.get("session") == info["session"] and status in (200, 403):
                    candidates.append(info)
            except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException, EditorControlError):
                continue
        if not candidates:
            raise EditorControlError(
                "No live editor bridge for this project. Open the editor and enable ai_chat/editor_control_bridge_enabled."
            )
        if len(candidates) != 1:
            raise EditorControlError(
                "Multiple live editors; choose --instance from PIDs: "
                + ", ".join(str(item["pid"]) for item in candidates)
            )
        self.info = candidates[0]

    def request(self, method, path, message=None):
        body = (
            None if message is None else json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        if body is not None and len(body) > 32768:
            raise EditorControlError("Message exceeds 32768 UTF-8 bytes.")
        connection = http.client.HTTPConnection("127.0.0.1", urllib.parse.urlsplit(self.info["url"]).port, timeout=7)
        try:
            connection.request(
                method,
                path,
                body,
                {
                    "Authorization": "Bearer " + self.info["token"],
                    "X-Godot-Session": self.info["session"],
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            data = response.read(512 * 1024 + 1)
            if len(data) > 512 * 1024:
                raise EditorControlError("Editor response exceeds limit.")
            result = json.loads(data)
            if not isinstance(result, dict) or result.get("session") != self.info["session"]:
                raise EditorControlError(
                    "Editor session changed or response is invalid; rediscover before sending another operation."
                )
            return response.status, result
        finally:
            connection.close()

    def capabilities(self, query="", limit=20, offset=0):
        return self.request(
            "GET", "/v1/capabilities?" + urllib.parse.urlencode({"query": query, "limit": limit, "offset": offset})
        )[1]

    def events(self, after=0, limit=100):
        return self.request("GET", "/v1/events?" + urllib.parse.urlencode({"after": after, "limit": limit}))[1]

    def state(self):
        return self.request("GET", "/v1/state")[1]

    def cancel(self, request_id, source="external-ai"):
        return self.request("POST", "/v1/cancel?" + urllib.parse.urlencode({"id": request_id, "source": source}))[1]

    def route(self, message):
        return self.request("POST", "/v1/messages", message)[1]

    def status(self, request_id, source="external-ai"):
        return self.request("GET", "/v1/requests?" + urllib.parse.urlencode({"id": request_id, "source": source}))[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--instance", type=int)
    commands = parser.add_subparsers(dest="command", required=True)
    capabilities = commands.add_parser("capabilities", help="Discover targets, tool schemas and routing instructions")
    capabilities.add_argument("--query", default="")
    capabilities.add_argument("--limit", type=int, default=20)
    capabilities.add_argument("--offset", type=int, default=0)
    route = commands.add_parser("route", help="Submit a structured engine-operation message")
    route.add_argument("--message", help="JSON message file, or - for stdin; otherwise use --operation/--request")
    route.add_argument("--operation", help="One declarative operation as JSON; no shell evaluation")
    route.add_argument("--request", help="Natural-language planning request; does not execute on its own")
    route.add_argument("--request-id", default=None)
    route.add_argument("--source", default="external-ai")
    route.add_argument(
        "--wait", type=float, default=0, help="Wait at most this many seconds for native approval, up to 300"
    )
    events = commands.add_parser("events", help="Read a bounded page of request outcome events")
    events.add_argument("--after", type=int, default=0)
    events.add_argument("--limit", type=int, default=100)
    commands.add_parser("state", help="Read the current bounded editor state")
    cancel = commands.add_parser("cancel", help="Cancel only the named pending external request")
    cancel.add_argument("request_id")
    cancel.add_argument("--source", default="external-ai")
    status = commands.add_parser("status", help="Recover a result without resubmitting the operation")
    status.add_argument("request_id")
    status.add_argument("--source", default="external-ai")
    args = parser.parse_args()
    try:
        client = EditorClient(args.project, args.instance)
        if args.command == "capabilities":
            result = client.capabilities(args.query, args.limit, args.offset)
        elif args.command == "events":
            result = client.events(args.after, args.limit)
        elif args.command == "state":
            result = client.state()
        elif args.command == "cancel":
            result = client.cancel(args.request_id, args.source)
        elif args.command == "status":
            result = client.status(args.request_id, args.source)
        else:
            if not 0 <= args.wait <= 300:
                raise EditorControlError("--wait must be between 0 and 300 seconds.")
            if args.message:
                if args.operation or args.request or args.request_id:
                    raise EditorControlError("Use --message or the individual message fields.")
                if args.message == "-":
                    text = sys.stdin.buffer.read(32769)
                else:
                    with Path(args.message).open("rb") as file:
                        text = file.read(32769)
                if len(text) > 32768:
                    raise EditorControlError("Message exceeds 32768 bytes.")
                message = json.loads(text)
            else:
                message = {
                    "intent": "engine_operation",
                    "request_id": args.request_id or uuid.uuid4().hex,
                    "source": args.source,
                }
                if args.operation:
                    message["operation"] = json.loads(args.operation)
                elif args.request:
                    message["request"] = args.request
                else:
                    raise EditorControlError("Provide --message, --operation or --request.")
            if not isinstance(message, dict):
                raise EditorControlError("Message must be a JSON object.")
            result = client.route(message)
            deadline = time.monotonic() + args.wait
            while result.get("routing_status") == "awaiting_confirmation" and time.monotonic() < deadline:
                time.sleep(min(0.25, max(0, deadline - time.monotonic())))
                result = client.status(message["request_id"], message.get("source", "external-ai"))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") or result.get("routing_status") == "awaiting_confirmation" else 1
    except EditorControlError as error:
        print(json.dumps({"ok": False, "error": "editor_client_failed", "message": str(error)}))
        return 1
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        # Exceptions may contain an untrusted URL/descriptor. Never print credentials.
        print(
            json.dumps({
                "ok": False,
                "error": "editor_client_failed",
                "recovery": "Check project/instance, bridge setting and host tool permission; query status with the original ID after a lost response.",
            })
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
