"""Broker-side RPC resolver. Credentials stay outside signed model inputs."""

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class _ResponseBeforeClose:
    def do_open(self, http_class, req, **kwargs):
        class Connection(http_class):
            def putheader(self, header, *values):
                # urllib forces Connection: close. An early admission refusal
                # can then close the peer while our POST body is still being
                # sent, turning a known 503 into an unknown TCP reset. Let the
                # response finish first; urllib and our response context still
                # close each socket, with no pooling or transport replay.
                if header.lower() == "connection":
                    values = ("keep-alive",)
                return super().putheader(header, *values)

        return super().do_open(Connection, req, **kwargs)


class _ContextHTTPHandler(_ResponseBeforeClose, urllib.request.HTTPHandler):
    pass


class _ContextHTTPSHandler(_ResponseBeforeClose, urllib.request.HTTPSHandler):
    def __init__(self):
        # build_opener requires an HTTPSHandler to suppress its eager default.
        # This handler belongs to one attempt: loopback HTTP never needs a CA
        # store, while HTTPS retains fresh stdlib certificate/hostname checks.
        urllib.request.AbstractHTTPHandler.__init__(self)

    def https_open(self, req):
        urllib.request.HTTPSHandler.__init__(self)
        return super().https_open(req)


class ContextNotStarted(urllib.error.HTTPError):
    """Explicit server admission refusal; no context operation was started.

    Callers may retain the same local tool request for later admission. This is
    never authority to repeat a model call or an operation with unknown outcome.
    """


class EntryContextClient:
    # Reserve a complete transport window beyond the server's 30s start deadline.
    # These are local admission bounds, never model retries or durable recovery.
    ADMISSION_SECONDS = 120.0
    MAX_ATTEMPTS = 16
    TRANSPORT_SECONDS = 35.0
    METHODS = frozenset({"binding", "check", "resolve", "delivery", "emit", "events"})

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
        if method not in self.METHODS:
            raise ValueError("Context operation denied")
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

        deadline = time.monotonic() + self.ADMISSION_SECONDS
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                return self._attempt(request, NoRedirect, self.TRANSPORT_SECONDS)
            except ContextNotStarted:
                if attempt + 1 >= self.MAX_ATTEMPTS:
                    raise
                ceiling = min(4.0, 0.25 * 2**attempt)
                delay = random.uniform(ceiling / 2, ceiling)
                # Do not send a doomed final attempt with a shortened timeout.
                if deadline - time.monotonic() < delay + self.TRANSPORT_SECONDS:
                    raise
                time.sleep(delay)
                # Scheduling stalls and outer process cancellation never grant a
                # new execution. Interrupts propagate; the owner retains its lease.
                if deadline - time.monotonic() < self.TRANSPORT_SECONDS:
                    raise

    @staticmethod
    def _attempt(request, redirect, timeout):
        # ProxyHandler mutates Request routing (including its CONNECT target).
        # A typed admission retry must retain the logical request, but never
        # carry that per-attempt routing into a new opener/connection.
        attempt_request = urllib.request.Request(
            request.full_url, data=request.data, headers=dict(request.header_items()), method=request.get_method()
        )
        try:
            response = urllib.request.build_opener(redirect(), _ContextHTTPHandler(), _ContextHTTPSHandler()).open(
                attempt_request, timeout=timeout
            )
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
