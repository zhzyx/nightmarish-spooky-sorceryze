"""Actual ordinary-game command journal cold recovery with no engine candidate."""

import argparse
import inspect
import shutil
from pathlib import Path

import run_daqian_node_approval as fixture

prepare = fixture.prepare_candidate_fixture


def ordinary(project, workspace, row, others=()):
    prepare(project, workspace, row, others)
    (workspace / "SConstruct").unlink()
    (project / "tools/gonggong_bridge.py").write_text(
        "import runpy\nrunpy.run_path("
        + repr(str(workspace / "tools/gonggong_bridge.py"))
        + ", run_name='__main__')\n",
        encoding="utf-8",
    )
    # The ordinary data root is not the installed host. Keep the fixture host
    # adapters with the existing project-side trusted tools.
    for name in ("customizations/components/godot-host/daqian/board.py",):
        destination = project / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workspace / name, destination)
    script = project / "test.gd"
    script.write_text(
        script.read_text(encoding="utf-8").replace(
            'view.find_children("*", "RichTextLabel", true, false)',
            'root.find_child("AI Chat", true, false).find_children("*", "RichTextLabel", true, false)',
        ),
        encoding="utf-8",
    )


fixture.prepare_candidate_fixture = ordinary
# Reuse the complete real restart oracle: exact original call, one result,
# preserved queued messages, late receipt and a second crash-window replay.
source = inspect.getsource(fixture.check_command_restart)
source = source.replace("[-3000:]", "[-30000:]")
source = source.replace(
    'next(project.glob("godot-candidate-*/executions"), None)',
    '(project / "executions") if (project / "executions").exists() else None',
)
source = source.replace('initial["conversation"] == initial["candidate"]["owner"]', 'not initial["candidate"]')
source = source.replace(
    'print("DAQIAN_COMMAND_RESTART_OK",',
    'assert (project / ".fixture/work-items.json").is_file()\n    assert (project / ".fixture/gonggong-diting-data/dataset.json").is_file()\n    print("ORDINARY_GAME_COMMAND_RESTART_OK",',
)
exec(compile(source, __file__, "exec"), fixture.__dict__)
# This is fixture model output only. Production command dispatch remains native.
model = inspect.getsource(fixture.Model)
model = model.replace(
    '"Add-Content -Encoding ascii executions once"',
    '"Remove-Item -LiteralPath .fixture/work-items.json,.fixture/gonggong-diting-data/dataset.json; Add-Content -Encoding ascii executions once"',
)
exec(compile(model, __file__, "exec"), fixture.__dict__)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--godot", type=Path, required=True)
args = parser.parse_args()
if args.godot.name.endswith(".console.exe"):
    parser.error("Use the editor .exe directly: killing the console wrapper terminates the entire child process job.")
fixture.run(args.godot, restart=True)
