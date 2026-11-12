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
    # The project selects data, never the implementation authenticating it.
    runpy.run_path(str(installation / "customizations/components/godot-host/bridge.py"), run_name="__main__")
