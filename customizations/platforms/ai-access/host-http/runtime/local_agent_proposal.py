"""Operator-installed, mutually authenticated loopback proposal peer."""

import hashlib
import http.client
import json
import re
import ssl
from pathlib import Path

from adapters import TransportUnknown, canonical, model_provenance
from native_proposal_adapter import build_request


def validate(profile):
    allowed = {
        "protocol",
        "id",
        "model",
        "port",
        "peer_sha256",
        "agent_file",
        "agent_sha256",
        "ca_file",
        "certificate_file",
        "private_key_file",
        "timeout_seconds",
        "max_context_bytes",
        "output_token_limit",
        "evaluation",
    }
    if set(profile) - allowed or allowed - {"evaluation"} - set(profile):
        raise ValueError("Closed installed agent profile required")
    for field in ("ca_file", "certificate_file", "private_key_file", "agent_file"):
        if not Path(profile[field]).is_absolute():
            raise ValueError("Absolute installed agent paths required")
    if not re.fullmatch("[0-9a-f]{64}", profile["peer_sha256"]) or not re.fullmatch(
        "[0-9a-f]{64}", profile["agent_sha256"]
    ):
        raise ValueError("Pinned agent installation required")
    with Path(profile["agent_file"]).open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != profile["agent_sha256"]:
            raise ValueError("Installed agent changed")
    if type(profile["port"]) is not int or not 0 < profile["port"] <= 65535:
        raise ValueError("Invalid local agent port")
    if type(profile["timeout_seconds"]) is not int or not 1 <= profile["timeout_seconds"] <= 60:
        raise ValueError("Invalid local agent timeout")
    if profile["output_token_limit"] != "unsupported":
        raise ValueError("Agent proposals have a byte ceiling")


def call_agent(profile, messages, output_limit):
    from runner import digest

    validate(profile)
    if output_limit is not None:
        raise ValueError("Unsupported local agent token ceiling")
    original, _, request = build_request(messages)
    body = canonical(request).encode()
    if len(body) > min(profile["max_context_bytes"], 131072):
        raise ValueError("Agent request exceeds the installed ceiling")
    ctx = ssl.create_default_context(cafile=profile["ca_file"])
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain(profile["certificate_file"], profile["private_key_file"])
    connection = http.client.HTTPSConnection(
        "127.0.0.1", profile["port"], context=ctx, timeout=profile["timeout_seconds"]
    )
    try:
        connection.connect()
        if hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest() != profile["peer_sha256"]:
            raise ValueError("Unexpected local agent certificate")
        connection.request("POST", "/proposal", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(524289)
        if response.status != 200 or len(raw) > 524288:
            raise ValueError("Malformed agent response")
        proposal = json.loads(raw)
        if (
            set(proposal) != {"request_id", "input_digest", "summary", "files"}
            or proposal["request_id"] != original["request_id"]
            or proposal["input_digest"] != digest(request)
            or not isinstance(proposal["summary"], str)
            or len(proposal["summary"].encode()) > 4096
            or not isinstance(proposal["files"], list)
            or not 1 <= len(proposal["files"]) <= min(64, len(original["write_allowlist"]))
        ):
            raise ValueError("Unbound agent proposal")
        paths = set()
        for edit in proposal["files"]:
            if (
                set(edit) != {"path", "content"}
                or edit["path"] not in original["write_allowlist"]
                or edit["path"] in paths
                or not isinstance(edit["content"], str)
                or len(edit["content"].encode()) > 131072
            ):
                raise ValueError("Out-of-scope agent edit")
            paths.add(edit["path"])
    except Exception as error:
        raise TransportUnknown("Local agent proposal unconfirmed; reconcile before another call") from error
    finally:
        connection.close()
    evidence = {
        "original_request_digest": digest(original),
        "input_digest": digest(request),
        "agent_installation_sha256": profile["agent_sha256"],
        "agent_peer_sha256": profile["peer_sha256"],
        "execution_authority": False,
        "status": "proposed",
        "usage": {"raw": None, "status": "unknown"},
    }
    return {
        **model_provenance(profile),
        "text": canonical({"action": "final", "value": proposal}),
        "finish_reason": "stop",
        "usage": {},
        "provider_request_id": original["request_id"],
        "protocol_evidence": evidence,
    }
