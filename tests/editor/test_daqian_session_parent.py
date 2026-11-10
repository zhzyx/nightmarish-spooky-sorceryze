"""Board helpers share the editor process across short-lived Windows venv launchers."""

import os
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path


class SessionParentTests(unittest.TestCase):
    def test_two_board_helpers_share_their_editor_parent(self):
        host = Path(__file__).resolve().parents[2] / "customizations/components/godot-host/daqian"
        probe = "from repository_access import editor_parent_pid; print(editor_parent_pid())"
        with tempfile.TemporaryDirectory() as folder:
            python = sys.executable
            if os.name == "nt":
                venv.EnvBuilder(with_pip=False).create(folder)
                python = str(Path(folder) / "Scripts/python.exe")
            for _ in range(2):
                parent = subprocess.check_output([python, "-c", probe], cwd=host)
                self.assertEqual(int(parent), os.getpid())


if __name__ == "__main__":
    unittest.main()
