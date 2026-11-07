"""Bootstrap the editor's read-only projection against its explicitly selected workspace."""

import argparse
import hashlib
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--workspace-board-sha256", required=True)
    args, remaining = parser.parse_known_args()
    root = args.repo.resolve(strict=True)
    host = root / "customizations/components/godot-host"
    daqian = host / "daqian"
    original = (daqian / "board.py").read_text(encoding="utf-8")
    if hashlib.sha256(original.encode("utf-8")).hexdigest() != args.workspace_board_sha256:
        raise SystemExit("The bound workspace board helper changed")
    # The ZIP is first under -I. Reuse this workspace's repository access, Git
    # origin, plan store and receipt validators, exactly as its native CLI does.
    sys.path.extend([str(daqian), str(host)])
    import board

    sys.argv = [sys.argv[0], "--repo", str(root), *remaining]
    board.main()


if __name__ == "__main__":
    main()
