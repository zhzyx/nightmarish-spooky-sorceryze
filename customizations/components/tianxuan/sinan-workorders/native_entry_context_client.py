"""Broker-side RPC resolver. Credentials stay outside signed model inputs."""

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class ContextNotStarted(urllib.error.HTTPError):
    """Explicit server admission refusal; no context operation was started.

    Callers may retain the same local tool request for later admission. This is
    never authority to repeat a model call or an operation with unknown outcome.
    """


class EntryContextClient:
    def __init__(self, config, execution):
        if set(config) != {"server", "token_file"}:
            raise ValueError("Closed context transport required")
        self.url = config["server"].rstrip("/")
        parsed = urllib.parse.urlsplit(self.url)
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path
            or not parsed.hostname
            or not (
                parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port)
            )
        ):
            raise ValueError("Verified HTTPS required outside loopback")
        path = Path(config["token_file"])
        if not path.is_absolute() or path.is_symlink():
            raise ValueError("Private absolute context token file required")
        self.token = path.read_text(encoding="utf-8").strip()
        self.execution = execution
        result = self.call("binding")
        self.binding, self.full_bytes = result["binding"], result["full_bytes"]
        from native_context import digest

        self.identity = digest(self.binding)

    def call(self, method, *args):
        data = json.dumps(dict(method=method, args=args), ensure_ascii=False).encode()
        if len(data) > 262144:
            raise ValueError("Context request budget exceeded")
        request = urllib.request.Request(
            self.url + "/native-context/" + self.execution,
            data=data,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise urllib.error.HTTPError(req.full_url, code, "Context redirect rejected", headers, fp)

        try:
            response = urllib.request.build_opener(NoRedirect()).open(request, timeout=35)
        except urllib.error.HTTPError as error:
            try:
                if error.code == 503:
                    raw = error.read(262145)
                    try:
                        detail = json.loads(raw) if len(raw) <= 262144 else None
                    except (ValueError, UnicodeError):
                        detail = None
                    if detail == {"detail": {"status": "not_started", "reason": "context_capacity"}}:
                        raise ContextNotStarted(
                            error.url, 503, "Context operation not started", error.headers, None
                        ) from None
            finally:
                error.close()
            raise
        with response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Context response budget exceeded")
        return json.loads(raw)

    def events(self):
        return self.call("events")

    def check(self, operation="model_turn"):
        return self.call("check", operation)

    def resolve(self, args, call=None):
        return self.call("resolve", args, call)

    def delivery(self, call, messages, status):
        return self.call("delivery", call, messages, status)

    def emit(self, kind, data):
        return self.call("emit", "model_process_closed" if kind == "process_closed" else kind, data)
