"""Vendor the official agent-gw wheel inside this repository, with hash verification."""

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "thirdparty" / "agent_gw_runtime"
URL = "https://cdn.kimi.com/agentgw/pysdk/v0.5.0/agent_gw-0.5.0-py3-none-any.whl"
SHA256 = "a880f15c21c58f232271283629e50971302c2c878219f9d04d39de4124797c42"


def main():
    if TARGET.exists():
        raise SystemExit("Refusing to overwrite the existing project-local runtime")
    TARGET.mkdir(parents=True)
    wheel = TARGET / "agent_gw-0.5.0-py3-none-any.whl"
    with urllib.request.urlopen(URL, timeout=60) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != SHA256:
        raise SystemExit("agent-gw wheel digest mismatch")
    wheel.write_bytes(payload)
    receipt = {
        "name": "agent-gw",
        "version": "0.5.0",
        "url": URL,
        "sha256": SHA256,
        "wheel": "thirdparty/agent_gw_runtime/agent_gw-0.5.0-py3-none-any.whl",
    }
    (TARGET / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
