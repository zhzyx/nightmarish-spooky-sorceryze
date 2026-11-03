"""Stable engine entry point for the registered GongGong host adapter."""

import argparse
import runpy
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--workspace", required=True)
    options, _ = parser.parse_known_args()
    runpy.run_path(
        str(Path(options.workspace).resolve() / "customizations/components/godot-host/bridge.py"), run_name="__main__"
    )
