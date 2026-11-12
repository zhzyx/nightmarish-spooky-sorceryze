"""Isolated native text layout regression; accepts private original input JSON."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--godot", type=Path, required=True)
p.add_argument("--input", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
binary_paths = [a.godot.resolve()]
if a.godot.name.endswith(".console.exe"):
    binary_paths.append(a.godot.resolve().with_name(a.godot.name.replace(".console.exe", ".exe")))
binary_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in binary_paths}
input_bytes = a.input.read_bytes()
a.out.mkdir(parents=True, exist_ok=False)
project = a.out.resolve() / "project"
project.mkdir(exist_ok=True)
(project / "project.godot").write_text(
    '[application]\nconfig/name="Unicode layout regression"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
    encoding="utf-8",
)
(project / "check.gd").write_bytes(Path(__file__).with_name("unicode_input_layout.gd").read_bytes())
env = os.environ.copy()
env.update(UNICODE_INPUT_FILE=str(a.input.resolve()), UNICODE_INPUT_RESULT=str(a.out.resolve() / "result.json"))
for key in ["APPDATA", "LOCALAPPDATA", "TEMP", "TMP"]:
    folder = a.out.resolve() / key
    folder.mkdir(exist_ok=True)
    env[key] = str(folder)
r = subprocess.run(
    [
        str(a.godot.resolve()),
        "--headless",
        "--audio-driver",
        "Dummy",
        "--path",
        str(project),
        "--script",
        "res://check.gd",
    ],
    env=env,
    capture_output=True,
    timeout=180,
)
(a.out / "stdout.log").write_bytes(r.stdout)
(a.out / "stderr.log").write_bytes(r.stderr)
result_path = a.out / "result.json"
result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
source = json.loads(input_bytes.decode("utf-8"))["value"]
surfaces = [env["UNICODE_INPUT_SURFACE"]] if env.get("UNICODE_INPUT_SURFACE") else ["TextEdit", "RichTextLabel"]
cases = result.get("cases", [])
valid = result.get("ok") is True and {(c["surface"], c["case"]) for c in cases} == {
    (s, i) for s in surfaces for i in range(4)
}
valid = valid and all(
    c["sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    and c["characters"] == len(source)
    and c["lines"] > 2
    for c in cases
    if c["case"] == 0
)
report = {
    "ok": valid
    and r.returncode == 0
    and b"ERROR:" not in r.stderr
    and input_bytes == a.input.read_bytes()
    and all(hashlib.sha256(path.read_bytes()).hexdigest() == binary_hashes[path.name] for path in binary_paths),
    "exit_code": r.returncode,
    "binary_sha256": binary_hashes[a.godot.name],
    "binary_files": binary_hashes,
    "input_file_sha256": hashlib.sha256(input_bytes).hexdigest(),
}
(a.out / "process.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(report))
raise SystemExit(0 if report["ok"] else 1)
