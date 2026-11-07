"""Real concurrent-editor receipt ownership and stale-owner recovery, headless."""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from editor_test_isolation import copy_editor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("editor_client", source / "tools/editor_control_client.py")
    client_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client_module)
    with tempfile.TemporaryDirectory(prefix="receipt-lock-") as folder:
        project = Path(folder)
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Receipt Ownership"\n')
        shutil.copyfile(Path(__file__).with_name("editor_receipt_lock.gd"), project / "test.gd")
        processes = []
        logs = []

        def launch(index):
            editor = copy_editor(args.godot, project / f"editor-{index}")
            (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
                '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/editor_control_bridge_enabled = true\n'
            )
            log = (project / f"process-{index}.log").open("w")
            logs.append(log)
            process = subprocess.Popen(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                env={**os.environ, "GODOT_AI_API_KEY": ""},
                stdout=log,
                stderr=log,
            )
            processes.append(process)
            return process

        def ready(process):
            deadline = time.monotonic() + 45
            while not (project / f"lock-ready-{process.pid}.json").exists():
                assert process.poll() is None and time.monotonic() < deadline, "Editor did not become ready"
                time.sleep(0.03)
            return client_module.EditorClient(project, process.pid)

        def stop(process):
            if process.poll() is None:
                (project / f"lock-finish-{process.pid}").touch()
                assert process.wait(timeout=20) == 0

        try:
            first, second = launch(0), launch(1)
            clients = [ready(first), ready(second)]

            def attempt(client, label):
                return client.route({
                    "intent": "engine_operation",
                    "source": "locktest",
                    "request_id": label,
                    "operation": {"action": "clear_highlight"},
                })

            results = [attempt(client, f"initial-{i}") for i, client in enumerate(clients)]
            assert sum(bool(r["ok"]) for r in results) == 1, results
            owner_index = next(i for i, result in enumerate(results) if result["ok"])
            assert results[1 - owner_index]["error"] == "receipt_store_unavailable", results
            owner = [first, second][owner_index]
            owner.kill()
            assert owner.wait(timeout=20) != 0
            stop([first, second][1 - owner_index])
            third, fourth = launch(2), launch(3)
            recovered_clients = [ready(third), ready(fourth)]
            recovered = [attempt(client, f"recovered-{i}") for i, client in enumerate(recovered_clients)]
            assert sum(bool(r["ok"]) for r in recovered) == 1, recovered
            winning_pid = [third, fourth][next(i for i, r in enumerate(recovered) if r["ok"])].pid
            marker = project / ".godot/editor/ai_control_receipts.json.lock/owner"
            assert int(marker.read_text()) == winning_pid
            assert not (project / ".godot/editor/ai_control_receipts.json.acquiring").exists()
            stop(third)
            stop(fourth)
            assert not marker.parent.exists()
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "checks": [
                            "one writer across simultaneous editors",
                            "second editor fails closed",
                            "SIGKILL stale owner",
                            "one writer across simultaneous stale-lock recovery",
                            "owner marker retained",
                            "clean release",
                        ],
                        "desktop_control": False,
                    },
                    indent=2,
                )
            )
        except BaseException:
            for path in project.glob("process-*.log"):
                print(path.read_text()[-1500:])
            raise
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            for log in logs:
                log.close()


if __name__ == "__main__":
    main()
