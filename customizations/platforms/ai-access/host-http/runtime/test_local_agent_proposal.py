"""Regression checks for the fixed external Agent trust and mandate boundaries."""

import hashlib
from unittest.mock import MagicMock, patch

import pytest
from adapters import TransportUnknown, canonical
from local_agent_proposal import call_agent, validate
from native_proposal_adapter import build_request
from runner import digest


def test_external_agent_only_sends_bound_proposals(tmp_path):
    path = tmp_path / "agent"
    path.write_bytes(b"isolated fixture")
    peer = b"fixture peer"
    profile = dict(
        protocol="local-agent-proposal",
        id="agent",
        model="agent",
        port=2123,
        peer_sha256=hashlib.sha256(peer).hexdigest(),
        agent_file=str(path),
        agent_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        ca_file=str(path),
        certificate_file=str(path),
        private_key_file=str(path),
        timeout_seconds=5,
        max_context_bytes=131072,
        output_token_limit="unsupported",
    )
    request = dict(request_id="a" * 64, task="write", context="{}", write_allowlist=["text/output"], acceptance="ok")
    msg = [
        {
            "role": "user",
            "content": canonical({
                "input": {"native_request": request, "native_binding": {"workspace": "private-path"}}
            }),
        }
    ]
    original, _, effective = build_request(msg)
    proposal = dict(
        request_id=original["request_id"],
        input_digest=digest(effective),
        summary="ok",
        files=[{"path": "text/output", "content": "ok"}],
    )
    conn = MagicMock()
    conn.sock.getpeercert.return_value = peer
    response = conn.getresponse.return_value
    response.status = 200
    response.read.return_value = canonical(proposal).encode()
    with (
        patch("local_agent_proposal.ssl.create_default_context"),
        patch("local_agent_proposal.http.client.HTTPSConnection", return_value=conn),
    ):
        result = call_agent(profile, msg, None)
        assert result["protocol_evidence"]["original_request_digest"] == digest(original)
        assert b"private-path" not in conn.request.call_args.kwargs["body"]
        proposal["files"][0]["path"] = "outside/output"
        response.read.return_value = canonical(proposal).encode()
        with pytest.raises(TransportUnknown):
            call_agent(profile, msg, None)
        conn.request.reset_mock()
        conn.sock.getpeercert.return_value = b"different"
        with pytest.raises(TransportUnknown):
            call_agent(profile, msg, None)
        conn.request.assert_not_called()
    with pytest.raises(ValueError):
        validate(dict(profile, endpoint="https://example.invalid"))
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        validate(profile)
