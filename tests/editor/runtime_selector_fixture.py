"""Native Windows fixture: validates governed UTF-8 stdin and writes a fixed plan."""

import json
import os
import subprocess
from pathlib import Path

SOURCE = r"""
using System;
using System.IO;
using System.Text;
class RuntimeSelectorFixture {
    static int Main(string[] args) {
        File.WriteAllText(MARKER, "native fixture invoked");
        try {
            string prompt;
            using (var input = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false, true))) {
                prompt = input.ReadToEnd();
            }
            if (!prompt.Contains("--- VERIFIED HOST POLICY: framework/FOUNDATION.md ---") ||
                !prompt.Contains("--- CURRENT HOST STEP MANDATE ---") ||
                !prompt.Contains("\u5171\u5de5")) {
                throw new Exception("Missing governed UTF-8 context in native stdin");
            }
            int option = Array.IndexOf(args, "--output-last-message");
            if (option < 0 || option + 1 >= args.Length) throw new Exception("Missing output path");
            File.WriteAllText(args[option + 1], PLAN, new UTF8Encoding(false));
            Console.WriteLine("{\"type\":\"turn.completed\"}");
            return 0;
        } catch (Exception error) {
            Console.Error.WriteLine(error.Message);
            return 17;
        }
    }
}
"""


def native_selector(folder, paths):
    if os.name != "nt":
        raise RuntimeError("The native selector fixture requires Windows")
    folder.mkdir(parents=True, exist_ok=True)
    compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework/v4.0.30319/csc.exe"
    plan = {
        "ok": True,
        "summary": "governed host selection fixture 中文",
        **{name: str(paths[name]) for name in ("python", "node", "git", "gh")},
        "source_runtime": "",
    }
    marker = folder / "invoked"
    source = folder / "selector.cs"
    executable = folder / "selector.exe"
    text = SOURCE.replace("MARKER", json.dumps(str(marker))).replace(
        "PLAN", json.dumps(json.dumps(plan, ensure_ascii=False))
    )
    source.write_text(text, encoding="ascii")
    result = subprocess.run(
        [str(compiler), "/nologo", "/target:exe", f"/out:{executable}", str(source)],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError((result.stdout + result.stderr).decode(errors="replace"))
    assert executable.read_bytes()[:2] == b"MZ"
    return executable, marker
