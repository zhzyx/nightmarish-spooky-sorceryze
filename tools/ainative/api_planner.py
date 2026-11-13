"""Explicit Chat Completions planner. One owned request, no retry or CLI fallback."""

import base64
import hashlib
import ipaddress
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from extensions import canonical, require

MAX_RESPONSE = 16 * 1024 * 1024
MAX_REQUEST = 48 * 1024 * 1024


def _is_openai_model(model):
    model = model.casefold()
    if model.startswith("openai/"):
        return True
    model = model.removeprefix("ft:").split(":", 1)[0]
    return (
        re.fullmatch(
            r"(?:chatgpt(?:-[0-9][a-z0-9]*(?:[.-][a-z0-9]+)*)?|gpt-(?:[0-9][a-z0-9]*|oss)(?:[.-][a-z0-9]+)*)", model
        )
        is not None
    )


def validate_config(config):
    require(isinstance(config, dict) and set(config) == {"endpoint", "model", "key_env"}, "api_config_invalid")
    require(all(isinstance(v, str) and v.strip() == v and v for v in config.values()), "api_config_invalid")
    url = urllib.parse.urlsplit(config["endpoint"])
    try:
        _ = url.port
    except ValueError:
        raise ValueError("api_config_invalid") from None
    try:
        local = ipaddress.ip_address(url.hostname).is_loopback
    except ValueError:
        local = url.hostname == "localhost"
    require(
        url.hostname
        and (url.scheme == "https" or (url.scheme == "http" and local))
        and not url.username
        and not url.password
        and not url.query
        and not url.fragment,
        "api_config_invalid",
    )
    require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config["key_env"]) is not None, "api_config_invalid")
    require(len(config["model"]) <= 256 and not any(ord(c) < 32 for c in config["model"]), "api_config_invalid")
    host = url.hostname.rstrip(".").lower()
    require(
        host != "api.openai.com"
        and not host.endswith((".api.openai.com", ".openai.azure.com", ".openai.azure.us", ".openai.azure.cn"))
        and not _is_openai_model(config["model"]),
        "gpt_modeling_retired",
    )
    return config


def check_configuration(config):
    validate_config(config)
    ready = bool(os.environ.get(config["key_env"]))
    return dict(
        connected=ready,
        code="" if ready else "api_key_missing",
        version="",
        auth_mode="api_key",
        message="Configuration checked; endpoint and inference are not yet verified.",
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("api_output_invalid")


def perform(config, directory):
    validate_config(config)
    key = os.environ.get(config["key_env"])
    require(bool(key), "api_key_missing")
    raw = (directory / "api-request.json").read_bytes()
    require(len(raw) <= MAX_REQUEST, "invalid_input")
    require(json.loads(raw)["model"] == config["model"], "api_config_invalid")
    request = urllib.request.Request(
        config["endpoint"].rstrip("/") + "/chat/completions",
        data=raw,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    # No redirects, proxies, retries or secondary endpoints. Secrets stay in this process.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=120) as response:
        data = response.read(MAX_RESPONSE + 1)
    require(len(data) <= MAX_RESPONSE, "api_output_invalid")
    value = json.loads(data)
    require(
        isinstance(value, dict) and isinstance(value.get("choices"), list) and len(value["choices"]) == 1,
        "api_output_invalid",
    )
    observed_model = value.get("model")
    if isinstance(observed_model, str):
        require(not _is_openai_model(observed_model), "gpt_modeling_retired")
    choice = value["choices"][0]
    require(choice.get("finish_reason") == "stop" and isinstance(choice.get("message"), dict), "api_output_invalid")
    message = choice["message"]
    require(
        not message.get("tool_calls") and not message.get("refusal") and isinstance(message.get("content"), str),
        "api_output_invalid",
    )
    plan = json.loads(message["content"])
    require(isinstance(plan, dict), "api_output_invalid")
    (directory / "api-plan.json").write_text(canonical(plan), encoding="utf-8")
    receipt = dict(
        provider="configured_chat_completions",
        requested_model=config["model"],
        observed_model=value.get("model") if isinstance(value.get("model"), str) else None,
        request_sha256=hashlib.sha256(raw).hexdigest(),
        response_sha256=hashlib.sha256(data).hexdigest(),
        instructions_sha256=hashlib.sha256(canonical(plan).encode()).hexdigest(),
        scope="completed_api_response_before_semantic_validation",
    )
    (directory / "api-receipt.json").write_text(canonical(receipt), encoding="utf-8")


def instructions(provider, key, directory, images):
    config = validate_config(provider.config["planner"])
    content = [dict(type="text", text=(directory / "prompt.txt").read_text(encoding="utf-8"))]
    for path in images:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        content.append(
            dict(
                type="image_url",
                image_url=dict(url="data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode()),
            )
        )
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(
            type="json_schema",
            json_schema=dict(
                name="modeling_plan",
                strict=True,
                schema=json.loads((directory / "schema.json").read_text(encoding="utf-8")),
            ),
        ),
    )
    raw = canonical(body).encode("utf-8")
    require(len(raw) <= MAX_REQUEST, "invalid_input")
    (directory / "api-request.json").write_bytes(raw)
    (directory / "planner-config.json").write_text(canonical(config), encoding="utf-8")
    exit_code = provider._run_owned(
        key,
        [
            sys.executable,
            "-X",
            "utf8",
            str(Path(__file__).resolve()),
            str(directory / "planner-config.json"),
            str(directory),
        ],
        directory,
        "api",
        timeout=135,
        error_codes=("api_timeout", "api_output_invalid"),
    )
    if exit_code is None:
        return None
    require(exit_code == 0, "api_execution_failed")
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    plan = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    require(
        receipt["request_sha256"] == hashlib.sha256(raw).hexdigest()
        and receipt["instructions_sha256"] == hashlib.sha256(canonical(plan).encode()).hexdigest(),
        "api_output_invalid",
    )
    provider.write(key, api_turn_receipt=receipt)
    return plan, receipt


if __name__ == "__main__":
    try:
        perform(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]))
    except Exception:
        # Do not echo request headers, remote errors, or environment secrets.
        sys.exit(1)
