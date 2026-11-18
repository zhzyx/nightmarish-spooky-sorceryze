"""Optional installed proposal transport; CLI counters retain their own protocol."""

import hashlib
import importlib.util
import json
from pathlib import Path

from adapters import TransportUnknown, canonical, model_provenance

ROOT = Path(__file__).resolve().parents[5]
HOST = ROOT / "customizations/components/tianxuan/sinan-workorders/native_model_host.py"
HELPER = ROOT / "tools/ainative/owned_process.py"


def host_for(profile):
    spec = importlib.util.spec_from_file_location("installed_native_model_host", HOST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    installed = profile["native_installation"]
    host = module.NativeModelHost(installed, lambda p: p == installed, HELPER)
    if profile.get("validation_probe"):
        probe = Path(profile["validation_probe"])
        if (
            not probe.is_absolute()
            or hashlib.sha256(probe.read_bytes()).hexdigest() != profile["validation_probe_sha256"]
        ):
            raise ValueError("Installed validation probe changed")
        original = host.configuration

        def configuration():
            p, b = original()
            return p, module.digest([b, hashlib.sha256(probe.read_bytes()).hexdigest()])

        host.configuration = configuration

        # Preserve the production dependency roots used by original.configuration.
        class ProbeHost(type(host)):
            def run(self, request, cancel=None):
                configured = self.configuration()
                old_wrapper, old_configuration = self.wrapper, self.configuration
                self.wrapper, self.configuration = probe, lambda: configured
                try:
                    return super().run(request, cancel)
                finally:
                    self.wrapper, self.configuration = old_wrapper, old_configuration

        host.__class__ = ProbeHost
    return host


def validate_profile(profile):
    host = host_for(profile)
    if host.configuration()[1] != profile["installation_digest"]:
        raise ValueError("Native installation changed; reevaluate and reauthorize")
    if profile.get("output_token_limit") != "unsupported" or profile.get("response_bytes") != 524288:
        raise ValueError("Explicit unsupported token ceiling and 524288 outer receipt bytes required")
    if profile["timeout_seconds"] != profile["native_installation"]["timeout"]:
        raise ValueError("Installed process time ceiling mismatch")
    if profile["model"] != profile["native_installation"]["model"]:
        raise ValueError("Installed requested model mismatch")
    return host


def build_request(messages):
    """Pure ordered original/governance/effective input construction for host evaluation."""
    requests = [json.loads(m["content"])["input"]["native_request"] for m in messages if m["role"] == "user"]
    if len(requests) != 1:
        raise ValueError("Exactly one fixed native request required")
    original = {k: requests[0][k] for k in ("request_id", "task", "context", "write_allowlist", "acceptance")}
    governance = []
    for message in messages:
        if message["role"] == "user":
            payload = json.loads(message["content"])
            payload.pop("input", None)
            governance.append({"role": "user", "content": canonical(payload)})
        else:
            governance.append(message)
    effective = {**original, "context": original["context"] + "\nRuntime governing context:\n" + canonical(governance)}
    return original, governance, effective


def installed_profile(identifier, installation, max_context_bytes=131072):
    """Construct unevaluated production CLI profile from host-owned installation."""
    profile = dict(
        id=identifier,
        protocol="codex-native-proposal",
        model=installation["model"],
        native_installation=installation,
        timeout_seconds=installation["timeout"],
        max_context_bytes=max_context_bytes,
        output_token_limit="unsupported",
        response_bytes=524288,
    )
    profile["installation_digest"] = host_for(profile).configuration()[1]
    return profile


def call_native(profile, messages, output_limit):
    if output_limit is not None:
        raise ValueError("CLI does not support output-token ceilings")
    host = validate_profile(profile)
    original, governance, effective = build_request(messages)
    terminal = host.run(effective)
    # Explicit original/effective binding, separate from proposal and raw usage.
    from runner import digest

    terminal["original_request_digest"] = digest(original)
    terminal["governance_digest"] = digest(governance)
    if terminal["status"] != "proposed":
        raise TransportUnknown("Native proposal unavailable; reconciliation required", terminal)
    return {
        **model_provenance(profile),
        "text": canonical({"action": "final", "value": terminal["proposal"]}),
        "finish_reason": "stop",
        "usage": {},  # No silent conversion of CLI last/total into HTTP counters.
        "provider_request_id": terminal["usage"].get("turn_id", "unavailable"),
        "protocol_evidence": terminal,
    }
