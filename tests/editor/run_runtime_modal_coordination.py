"""Exercise missing-runtime and engine approval windows in the self-update fixture.

Reuses the isolated synthetic build/restart driver. Buttons dispatch their normal
GUI actions; runtime installation and original-request recovery are separately
covered by run_requirements_intake.py --runtime-source. This is not OS click QA.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys


def main():
    # Consume only the additional output option; leave --godot to the driver.
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixture-driver", type=Path, default=Path(__file__).with_name("run_editor_self_update.py"))
    parser.add_argument("--baseline-trigger", action="store_true", help="Replay the original trigger and fail on its previously ignored conflict")
    args, remaining = parser.parse_known_args()
    source = args.fixture_driver.resolve()
    if "# Isolated mock build fixture" not in source.read_text(encoding="utf-8"):
        raise RuntimeError("Requires the isolated executable/source-marker driver from Issue #51")
    spec = importlib.util.spec_from_file_location("modal_self_update_fixture", source)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    driver.ROOT = Path(__file__).resolve().parents[2]
    original_script = driver.SCRIPT
    marker = '    build.pressed.emit()\n'
    preflight = '''    var setup = dock.find_child("GongGongRuntimeSetup", true, false)
    if not _check(setup != null and setup.visible and not setup.exclusive,
            "Runtime setup must remain visible without taking root exclusivity"):
        return
    var output = dock.find_child("GongGongOutput", true, false)
    var untouched = output.text
    var pickers = setup.find_children("*", "FileDialog", true, false)
    if not _check(pickers.size() == 1 and pickers[0].get_parent() == setup and pickers[0].exclusive,
            "Source picker must be modal to the setup window"):
        return
    var picker = pickers[0]
    picker.popup_centered_ratio()
    await process_frame
    picker.get_cancel_button().pressed.emit()
    await process_frame
    if not _check(not picker.visible and setup.visible and output.text == untouched,
            "Source cancellation must leave setup available without deploying: picker=%s setup=%s unchanged=%s" % [picker.visible, setup.visible, output.text == untouched]):
        return
    picker.popup_centered_ratio()
    await process_frame
    picker.dir_selected.emit(OS.get_environment("SELF_UPDATE_TEST_ENGINE"))
    picker.hide()
    if not _check(setup.find_child("GongGongRuntimeSource", true, false).text == OS.get_environment("SELF_UPDATE_TEST_ENGINE")
            and output.text == untouched, "Selecting a directory must not authorize installation"):
        return
    setup.get_cancel_button().pressed.emit()
    await process_frame
    if not _check(not setup.visible and cancel.disabled and output.text == untouched,
            "Rejecting setup must not deploy or build"):
        return
    dock.find_child("GongGongEnvironmentSetup", true, false).pressed.emit()
    if not _check(setup.visible, "Setup must reopen after rejection"):
        return
'''
    if driver.SCRIPT.count(marker) != 4:
        raise RuntimeError("Self-update fixture changed; review the injected modal scenario")
    driver.SCRIPT = driver.SCRIPT.replace(marker, preflight + marker, 1)
    driver.SCRIPT = driver.SCRIPT.replace(
        '    approval.hide()\n    approval.canceled.emit()',
        '''    if not _check(approval.exclusive and setup.visible and output.text == untouched,
            "Build approval must not authorize or dismiss runtime setup"):
        return
    approval.get_cancel_button().pressed.emit()
    await process_frame
    if not _check(not approval.visible and setup.visible and output.text == untouched,
            "Build rejection must preserve setup without deploying"):
        return''',
        1,
    )
    driver.SCRIPT = driver.SCRIPT.replace(
        '    approval.hide()\n    approval.confirmed.emit()',
        '    approval.get_ok_button().pressed.emit()',
    )
    if args.baseline_trigger:
        driver.SCRIPT = original_script
    sys.argv = [str(source), *remaining]
    stdout, stderr = io.StringIO(), io.StringIO()
    error = None
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            result = driver.main()
        except Exception as exception:
            result = 1
            error = str(exception)
            for stream, name in ((stdout, "stdout"), (stderr, "stderr")):
                value = getattr(exception, name, None)
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                if value:
                    stream.write(value)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".stdout.log").write_text(stdout.getvalue(), encoding="utf-8")
    args.out.with_suffix(".stderr.log").write_text(stderr.getvalue(), encoding="utf-8")
    logs = stdout.getvalue() + stderr.getvalue()
    conflict = "Attempting to make child window exclusive" in logs
    report = {
        "ok": result == 0 and not conflict,
        "exclusive_child_conflict": conflict,
        "fixture_exit_code": result,
        "error": error,
        "scenario": "original-trigger" if args.baseline_trigger else "modal-coordination",
        "fixture_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "coverage": "Original self-update trigger, synthetic build and isolated restart" if args.baseline_trigger else "Runtime rejection, picker nesting/cancel/select, build rejection/approval, synthetic build cancellation/failure and real isolated restart",
        "limits": "Button action dispatch; no OS pointer QA or real runtime install in this fixture",
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
