"""Standalone entry for the shared Executor, with explicit local module roots."""

import sys
from pathlib import Path


def main():
    tools = Path(__file__).resolve().parent
    sys.path.insert(0, str(tools.parents[1] / "tools/ainative"))
    sys.path.insert(0, str(tools))
    from executor_cli import main as executor_main

    return executor_main()


if __name__ == "__main__":
    raise SystemExit(main())
