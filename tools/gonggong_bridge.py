"""Stable engine entry point for the registered GongGong host adapter."""

import argparse
import runpy
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("action")
    parser.add_argument("--workspace", required=True)
    options, _ = parser.parse_known_args()
    installation = Path(__file__).resolve().parents[1]
    # Acceptance attests candidate data. The candidate cannot choose its verifier.
    source = (
        installation
        if options.action in {"acceptance-capture", "acceptance-verify", "acceptance-current", "project-integration"}
        else Path(options.workspace).resolve()
    )
    runpy.run_path(str(source / "customizations/components/godot-host/bridge.py"), run_name="__main__")
