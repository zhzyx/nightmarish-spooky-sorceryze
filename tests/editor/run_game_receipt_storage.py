"""Ordinary native game command deletes receipt metadata; real flush/next tool must continue.

Uses the existing isolated native production transport fixture. No production
Issue, user editor, installed consumer or business acceptance is represented.
"""

import runpy
import sys

import native_game_integration as game
import run_design_batch as batch

original_command = batch.python_command


def command(code):
    if "production-output.gd" in code and "subprocess.run" in code:
        code = (
            "from pathlib import Path; root=Path.cwd(); "
            "root=next(p for p in [root,*root.parents] if (p/'work-items.json').is_file()); "
            "(root/'work-items.json').unlink(); (root/'gonggong-diting-data/dataset.json').unlink(); " + code
        )
    return original_command(code)


batch.python_command = command
original_valid = game.valid


def valid(observed, acceptance):
    result = observed.get("game_run", {})
    guard = result.get("provenance_guard", {})
    observed["receipt_metadata_recovery"] = guard
    return original_valid(observed, acceptance) and guard.get("ok") is True and guard.get("restored_count") == 2


game.valid = valid
if "--complete-game" not in sys.argv:
    sys.argv.append("--complete-game")
runpy.run_module("run_native_production_setup", run_name="__main__")
