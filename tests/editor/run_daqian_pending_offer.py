"""Force-kill the editor with an outstanding Tianshu command and exercise its successor."""

import argparse
import json
import shutil
import subprocess
import time
from functools import partial
from pathlib import Path

import run_daqian_node_approval as fixture


def check_offer(command, env, project, changed_actor, stop, *, missing_cwd=False):
    if missing_cwd:
        (project / "missing-cwd-fixture").touch()
    env["DAQIAN_TEST_PENDING_OFFER"] = "1"
    journal = project / ".godot/editor/ai_chat_resume.json"
    with (project / "child.log").open("wb") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline and process.poll() is None:
                if (project / "old-offer.json").exists():
                    break
                time.sleep(0.1)
            else:
                raise AssertionError((project / "child.log").read_text(errors="replace")[-3000:])
        finally:
            process.kill()
            process.wait(timeout=15)
    original = journal.read_bytes()
    assert json.loads(original)["command_offer"]
    assert not list(project.glob("godot-candidate-*/executions"))
    shutil.copyfile(Path(__file__).with_name("daqian_offer_reopen.gd"), project / "reopen.gd")

    def observe(decision):
        env["DAQIAN_OFFER_DECISION"] = decision
        result = subprocess.run([*command[:-1], "res://reopen.gd"], env=env, capture_output=True, timeout=40)
        assert result.returncode == 0, result.stderr
        return json.loads((project / "offer-observed.json").read_bytes())

    settings = Path(command[0]).parent / "editor_data/editor_settings-4.8.tres"
    text = settings.read_text(encoding="utf-8")
    key = "ai_chat/auto_execute_commands"
    if key in text:
        text = text.replace(key + " = false", key + " = true")
    else:
        text += "\n" + key + " = true\n"
    settings.write_text(text, encoding="utf-8")

    if missing_cwd:
        initial = json.loads(original)
        call = initial["tool_calls"][initial["tool_index"]]
        cwd = Path(json.loads(call["function"]["arguments"])["cwd"])
        cwd.rmdir()
        failed = observe("confirm")
        assert not failed["offered"] and failed["cwd_rejected"] and failed["unexecuted"], failed
        assert journal.read_bytes() == original and not (cwd.parent / "next-step").exists()
        cwd.mkdir()
        print("DAQIAN_MISSING_CWD_BATCH_PAUSED_OK", json.dumps(failed))
    changed = project / ".fixture/changed-authority"
    if changed_actor:
        env["DAQIAN_CHANGED_AUTHORITY"] = "1"
        changed.touch()
    decision = "stop" if stop else "confirm"
    result = observe(decision)
    assert result["unexecuted"] and not result["old_accepted"], result
    effects = list(project.glob("godot-candidate-*/executions"))
    if changed_actor:
        assert not result["offered"] and not effects, result
        assert journal.read_bytes() == original
        env["DAQIAN_DELAY_AUTHORITY"] = str(project / "gate-running")
        delayed = observe("stop")
        assert delayed["stopped_before_card"] and not delayed["offered"] and delayed["unexecuted"], delayed
        assert journal.read_bytes() == original
        print("DAQIAN_STOP_DURING_AUTHORITY_OK", json.dumps(delayed))
        del env["DAQIAN_DELAY_AUTHORITY"]
        del env["DAQIAN_CHANGED_AUTHORITY"]
        changed.unlink()
        result = observe(decision)
        assert result["unexecuted"] and not result["old_accepted"], result
        effects = list(project.glob("godot-candidate-*/executions"))
    fields = [
        "offered",
        "fresh",
        "foreign_rejected",
        "foreign_preserved",
        "detail",
        "step",
        "actor",
        "request",
        "source_sha256",
        "url",
        "board_workspace",
        "root",
    ]
    assert all(result[field] for field in fields), result
    if stop:
        assert not effects and result["foreign_survived_stop"], result
    else:
        assert result["confirmed"] and not result["duplicate"] and len(effects) == 1, result
        assert effects[0].read_text().splitlines() == ["once"]
        effects[0].with_name("release-command").touch()
    journal.write_bytes(original)
    assert not observe("confirm")["offered"]
    final_effects = list(project.glob("godot-candidate-*/executions"))
    assert len(final_effects) == (0 if stop else 1)
    assert all(path.read_text().splitlines() == ["once"] for path in final_effects)
    print("DAQIAN_PENDING_OFFER_OK", json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--changed-actor", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--missing-cwd", action="store_true")
    args = parser.parse_args()
    fixture.check_command_restart = partial(check_offer, missing_cwd=args.missing_cwd)
    fixture.run(args.godot, True, args.changed_actor, args.stop or args.missing_cwd)
