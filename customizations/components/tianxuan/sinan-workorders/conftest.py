"""Installed sibling modules for isolated host-tool tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "duobao")]
