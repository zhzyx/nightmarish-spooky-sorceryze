"""Read-only, producer-side observations of already admitted model profiles."""

import json
import socket
import ssl
import tempfile
from pathlib import Path

from native_observations import public_model_name


def cli_read(installed, arguments, limit):
    from native_check_runner import _process_helper

    entry = installed["entry"]
    args = [installed["node"], entry] if Path(entry).suffix.lower() in {".js", ".mjs"} else [entry]
    failures = []
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        code = _process_helper().run_owned(
            [*args, *arguments],
            stdout=output,
            stderr=errors,
            env=installed["env"],
            limit=limit,
            timeout=8,
            active=lambda: True,
            fail=failures.append,
        )
        if failures or code is None:
            return None, b"", b""
        output.seek(0)
        errors.seek(0)
        return code, output.read(), errors.read()


def codex_login(installed):
    # Only the CLI uses the credential backend, with its exact installed environment.
    code, output, errors = cli_read(installed, ["login", "status"], 4096)
    lines = [line.strip().lower() for line in (output + b"\n" + errors).splitlines()]
    if code == 0 and b"logged in using chatgpt" in lines:
        return "ready"
    if code == 1 and b"not logged in" in lines:
        return "credential_missing"
    return "credential_unconfirmed"


def codex_models(installed):
    code, output, _ = cli_read(installed, ["debug", "models"], 2 * 1024 * 1024)
    if code != 0:
        return None
    try:
        models = json.loads(output)["models"]
        if isinstance(models, list):
            return {m["slug"] for m in models if m.get("visibility") == "list" and isinstance(m.get("slug"), str)}
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def local_status(profile, environment, *, validation):
    """Report only the locally testable prerequisites; no model request is made."""
    protocol = profile["protocol"]
    if protocol in {"codex-native-proposal", "codex-native-role"}:
        from native_proposal_adapter import validate_profile

        validate_profile(profile)
        if profile.get("validation_probe"):
            return "validation_probe" if validation else "installation_unconfirmed"
        installed = profile["native_installation"]
        login = codex_login(installed)
        if login != "ready":
            return login
        models = codex_models(installed)
        if models is None:
            return "catalog_unconfirmed"
        return "ready" if profile["model"] in models else "model_missing"
    if protocol == "local-agent-proposal":
        from local_agent_proposal import validate

        validate(profile)
        files = [Path(profile[name]) for name in ("ca_file", "certificate_file", "private_key_file")]
        if any(not file.is_file() for file in files):
            return "credential_missing"
        try:
            ctx = ssl.create_default_context(cafile=str(files[0]))
            ctx.load_cert_chain(files[1], files[2], password=lambda: b"")
        except (ssl.SSLError, OSError):
            return "credential_unconfirmed"
        from native_role_service import peer

        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        try:
            with (
                socket.create_connection(("127.0.0.1", profile["port"]), timeout=3) as sock,
                ctx.wrap_socket(sock, server_hostname="127.0.0.1") as conn,
            ):
                peer(conn, profile["peer_sha256"])
        except (OSError, ValueError):
            return "peer_unconfirmed"
        return "ready"
    if profile.get("api_key_env") and not environment.get(profile["api_key_env"]):
        return "credential_missing"
    # An HTTP profile with configured credentials has no observed local CLI
    # or authenticated loopback Agent. Leave business dispatch with its host.
    return "provider_unconfirmed"


def producer_catalog(template, environment, *, validation=False):
    observations = {}
    for profile in template["profiles"]:
        try:
            status = local_status(profile, environment, validation=validation)
        except (OSError, ValueError, KeyError, RuntimeError):
            status = "installation_unconfirmed"
        observations[profile["id"]] = dict(
            agent=template["task"]["agent_id"], requestedModel=public_model_name(profile.get("model")), status=status
        )
    return observations
