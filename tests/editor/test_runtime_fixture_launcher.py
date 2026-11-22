"""Exercise the Windows simulation's managed launcher with an editor-style pipe."""

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from run_runtime_setup_simulation import ENTRIES, clean_env, make_package


@unittest.skipUnless(os.name == "nt", "Windows fixture PE")
class RuntimeFixtureLauncherTest(unittest.TestCase):
    def test_intake_exit_receipt_and_start_failure(self):
        clr_status = 0xE0434352
        with tempfile.TemporaryDirectory(prefix="runtime-fixture-probe-") as temporary:
            root = Path(temporary)
            diagnostics = root / "diagnostics"
            diagnostics.mkdir()
            env = clean_env()
            env["GONGGONG_SIMULATION_DIAGNOSTICS"] = str(diagnostics)
            host = Path(sys.executable)
            targets = dict.fromkeys(ENTRIES, host)
            script = root / "child with spaces.py"
            script.write_text(
                "import ctypes,json,sys\n"
                "from pathlib import Path\n"
                "action,path,code,*args = sys.argv[1:]\n"
                "payload = sys.stdin.buffer.readline()\n"
                "Path(path).write_text(json.dumps([action,args,payload.hex()]), encoding='ascii')\n"
                "ctypes.windll.kernel32.ExitProcess(ctypes.c_uint32(int(code)))\n",
                encoding="ascii",
            )
            receipt = root / "child.json"
            args = ["", 'a"b', "中文 path\\", "two words"]
            payload = b"synthetic pipe input\n"

            def invoke(launcher, code):
                command = [launcher, script, "issue-agent", receipt, str(code), *args]
                with subprocess.Popen(
                    command,
                    cwd=root,
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                ) as process:
                    process.stdin.write(payload)
                    process.stdin.close()
                    process.stdout.close()
                    process.stderr.close()
                    try:
                        return process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        raise

            package = root / "package"
            make_package(package, targets)
            for code in (0, 7, clr_status):
                with self.subTest(code=code):
                    self.assertEqual(invoke(package / ENTRIES["python"], code), code)
                    self.assertEqual(json.loads(receipt.read_bytes()), ["issue-agent", args, payload.hex()])
                    receipt.unlink()

            missing = root / "missing-target-package"
            targets["python"] = root / "unavailable.exe"
            make_package(missing, targets)
            # Let the owned process terminate silently on its deliberate unhandled exception.
            kernel = ctypes.windll.kernel32
            previous = kernel.SetErrorMode(kernel.GetErrorMode() | 0x0002)  # SEM_NOGPFAULTERRORBOX
            try:
                self.assertEqual(invoke(missing / ENTRIES["python"], 0), clr_status)
            finally:
                kernel.SetErrorMode(previous)
            self.assertFalse(receipt.exists())
            failures = [json.loads(path.read_bytes()) for path in diagnostics.glob("*.json")]
            expected = {
                "runtime": "python",
                "action": "issue-agent",
                "phase": "child_exit",
                "exception_type": None,
                "win32_error": None,
                "child_exit": 7,
            }
            self.assertCountEqual(
                failures,
                [
                    expected,
                    dict(expected, child_exit=ctypes.c_int32(clr_status).value),
                    dict(
                        expected,
                        phase="start",
                        exception_type="System.ComponentModel.Win32Exception",
                        win32_error=2,
                        child_exit=None,
                    ),
                ],
            )


if __name__ == "__main__":
    unittest.main()
