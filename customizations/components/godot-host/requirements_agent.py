"""Bounded Yanshi/ClarifyFeature intake before a development Issue exists; no production tools."""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

_paths_spec = importlib.util.spec_from_file_location(
    "gonggong_workspace_paths", Path(__file__).with_name("workspace_paths.py")
)
if _paths_spec is None or _paths_spec.loader is None:
    raise ImportError("Cannot load workspace path resolver")
_paths_module = importlib.util.module_from_spec(_paths_spec)
_paths_spec.loader.exec_module(_paths_module)
framework_root = _paths_module.framework_root


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Requirements Agent dependency is unavailable")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def save(path, value):
    """Cancellation may kill the process at any instruction; retain the previous complete journal."""
    fd, temporary = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def proposal(value, categories):
    if not isinstance(value, dict) or set(value) != {
        "decision",
        "title",
        "category",
        "goal",
        "scope",
        "acceptance",
        "questions",
    }:
        raise ValueError("Yanshi must return the complete requirements schema")
    if value["decision"] not in {"new", "continue"} or value["category"] not in categories:
        raise ValueError("Invalid requirements decision/category")
    for key, maximum in [("title", 120), ("goal", 4000)]:
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > maximum:
            raise ValueError("Missing/oversized requirement " + key)
    if "\n" in value["title"] or "\r" in value["title"]:
        raise ValueError("Requirement title must be a single line")
    for key in ["scope", "acceptance", "questions"]:
        if not isinstance(value[key], list) or len(value[key]) > 20:
            raise ValueError("Invalid requirement " + key)
        if any(not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in value[key]):
            raise ValueError("Invalid requirement item")
    if not value["scope"] or not value["acceptance"]:
        raise ValueError("Requirements must include scope and acceptance")
    if re.search(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})", json.dumps(value)):
        raise ValueError("Remove credentials from requirements before publication")
    return value


def complete(root, request, profile, messages, env):
    if request.get("backend") != "codebuddy":
        return load(framework_root(root) / "runtime/adapters.py", "requirements_transport").call(
            profile, messages, 3000
        )
    node = request.get("cli_node") or env.get("GONGGONG_NODE", "")
    entry = request.get("cli_entry", "")
    bridge = root / "tools/codebuddy_cli/godot_bridge.js"
    if not all(Path(p).is_file() for p in [node, entry, str(bridge)]):
        raise ValueError("Repair CodeBuddy Node/CLI installation before requirements intake")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "requirements.json"
        payload = {
            "messages": messages,
            "model": request.get("cli_model", ""),
            "available_tools": [],
            "agent_id": "yanshi",
            "tool_context": {"permission_enabled": False, "tool_rounds": 0, "max_tool_rounds": None},
        }
        payload["messages"][0]["content"] += (
            "\nFor the CLI envelope put the requirement JSON string in content and return actions: []."
        )
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [node, str(bridge), "chat", entry, str(path)],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=150,
        )
    if result.returncode:
        raise ValueError(
            "Requirements model API failed in CodeBuddy; repair the existing CLI login, model or native dependencies before retrying"
        )
    choice = json.loads(result.stdout)["choices"][0]
    if choice["message"].get("tool_calls"):
        raise ValueError("Requirements Agent cannot execute tools")
    return {"text": choice["message"]["content"], "finish_reason": choice["finish_reason"], "usage": {}}


def intake(root, request, bridge):
    key = hashlib.sha256(
        json.dumps(
            [request.get("conversation_id"), request.get("issue_number"), request.get("outcome")], ensure_ascii=False
        ).encode()
    ).hexdigest()
    with bridge.outbox_lock(root / ".gonggong-outbox/requirements-locks" / key, time.monotonic() + 2):
        return _intake(root, request, bridge)


def _intake(root, request, bridge):
    if request.get("_cancel_path") and not Path(request["_cancel_path"]).is_file():
        raise ValueError("Requirements intake cancelled before processing")
    outcome = request.get("outcome")
    conversation = request.get("conversation_id")
    if not isinstance(outcome, str) or not outcome.strip() or len(outcome) > 16000:
        raise ValueError("A bounded user requirement is required")
    if not isinstance(conversation, str) or not conversation or len(conversation) > 200:
        raise ValueError("A stable conversation identity is required")
    work = bridge.work_items_module(root)
    settings, labels = work.config(root)
    env = bridge.host_environment(root)
    origin = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"], env=env, capture_output=True, text=True, timeout=30
    )
    if origin.returncode or origin.stdout.strip().removesuffix(".git") not in {
        "https://github.com/" + settings["repository"],
        "git@github.com:" + settings["repository"],
    }:
        raise ValueError("Requirements repository does not match Git origin")
    gh, error = bridge.gh_state(root)
    if error:
        return {
            "ok": False,
            "error": error,
            "phase": "repair_environment",
            "login_command": bridge.login_command(gh) if gh else "",
            "remote_created": False,
        }
    # Check actual repository access before spending a model request.
    repo = json.loads(work.gh("api", "repos/" + settings["repository"]))
    if str(repo.get("full_name", "")).casefold() != settings["repository"].casefold():
        raise ValueError("GitHub repository response does not match the configured workspace")
    if repo.get("has_issues") is False:
        return {"ok": False, "error": "repository_issues_disabled", "phase": "repair_environment"}
    # Git push permission is not Issue-write permission (public contributors and scoped PATs differ).
    # Actual Issue permission is checked by the authorized create; failures retain the proposal.
    existing = None
    number = request.get("issue_number")
    if type(number) is int and number > 0:
        existing = json.loads(work.gh("api", f"repos/{settings['repository']}/issues/{number}"))
        if "pull_request" in existing:
            raise ValueError("A pull request cannot be a requirements Issue")
    digest = hashlib.sha256((conversation + "\0" + str(number) + "\0" + outcome).encode()).hexdigest()
    identity = "requirement-" + digest[:32]
    journal = root / ".gonggong-outbox/requirements" / (identity + ".json")
    journal.parent.mkdir(parents=True, exist_ok=True)
    framework = framework_root(root)
    env = bridge.host_environment(root)
    mandate = {
        "feature_id": identity,
        "outcome": outcome,
        "authority_ref": "godot-editor:user-requirements:" + digest,
        "phase": "requirements_only_before_issue",
        "tools_enabled": False,
        "production_execution_authorized": False,
    }
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "mandate.json"
        path.write_text(json.dumps(mandate, ensure_ascii=False), encoding="utf-8")
        context = subprocess.run(
            [env.get("GONGGONG_NODE", "node"), str(framework / "tools/agent-context.mjs"), "yanshi", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=120,
        )
    if context.returncode:
        raise ValueError("Yanshi independent admission/context validation failed")
    context_text = context.stdout
    for name in ["agents/yanshi/skills/clarify-feature/SKILL.md", "agents/yanshi/references/understanding.md"]:
        context_text += "\n\n" + (framework / name).read_text(encoding="utf-8")
    categories = [x["name"].removeprefix("type:") for x in labels]
    current = next(
        a
        for a in json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))["agents"]
        if a["id"] == "yanshi"
    )
    if journal.exists():
        saved = json.loads(journal.read_text(encoding="utf-8"))
        if saved.get("phase") == "publication_attempted":
            pages = json.loads(
                work.gh("api", f"repos/{settings['repository']}/issues?state=all&per_page=100", "--paginate", "--slurp")
            )
            found = [
                x
                for page in pages
                for x in page
                if "pull_request" not in x and work.request_ids(x.get("body", "")) == {identity}
            ]
            if len(found) != 1:
                raise ValueError("Issue publication outcome unknown; reconcile the prior request before any new create")
            saved.update(phase="proposal_ready", publication={"url": found[0]["html_url"]})
            save(journal, saved)
        stale = saved.get("candidate_digest") != current["candidate_digest"]
        if (saved.get("phase") != "proposal_ready" or stale) and request.get("retry_authorized") is True:
            archive = journal.with_name(journal.stem + "-attempt-" + str(time.time_ns()) + ".json")
            archive.write_bytes(journal.read_bytes())
            journal.unlink()
    if journal.exists():
        saved = json.loads(journal.read_text(encoding="utf-8"))
        if saved.get("phase") != "proposal_ready":
            # Unknown transport outcome must not cause a second model charge automatically.
            raise ValueError("Requirements model outcome needs reconciliation; original attempt retained")
        current = next(
            a
            for a in json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))["agents"]
            if a["id"] == "yanshi"
        )
        if saved.get("candidate_digest") != current["candidate_digest"]:
            raise ValueError("Requirements candidate changed; reauthorize/regenerate the proposal")
        if (
            saved.get("request_sha256") != digest
            or saved.get("agent") != "yanshi"
            or saved.get("skill") != "clarify-feature"
        ):
            raise ValueError("Requirements journal identity mismatch")
        design = proposal(saved["proposal"], categories)
    else:
        instruction = (
            "Requirements intake only. You are the registered Yanshi using ClarifyFeature, not a generic form filler. "
            "Do not implement, invoke tools, grant permissions, or approve design gates. "
            "Interpret the actual user goal; preserve material unknowns in questions. "
            "New distinct requirements MUST be decision=new; follow-up to the supplied open Issue may be continue. "
            "A closed Issue cannot be continued. Do not expose credentials or local private paths in public requirements. "
            "Return only JSON with exactly decision(new|continue), title, category, goal, scope(string[]), "
            "acceptance(string[]), questions(string[]). Categories: " + ",".join(categories)
        )
        profile = {
            "protocol": "chat-completions",
            "endpoint": request.get("endpoint", ""),
            "model": request.get("model", ""),
            "timeout_seconds": 90,
        }
        if request.get("backend") != "codebuddy" and (not profile["endpoint"] or not profile["model"]):
            raise ValueError("Configure the requirements Agent model endpoint and model before intake")
        previous_key = os.environ.get("GONGGONG_REQUIREMENTS_KEY")
        private_key = (
            (request.get("_private_api_key") or previous_key) if request.get("backend") != "codebuddy" else None
        )
        if private_key:
            profile["api_key_env"] = "GONGGONG_REQUIREMENTS_KEY"
        saved = {
            "phase": "model_attempted",
            "request_sha256": digest,
            "agent": "yanshi",
            "skill": "clarify-feature",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        save(journal, saved)
        try:
            if private_key:
                os.environ["GONGGONG_REQUIREMENTS_KEY"] = private_key
            result = complete(
                root,
                request,
                profile,
                [
                    {"role": "system", "content": context_text + "\n" + instruction},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "request": outcome,
                                "existing_issue": None
                                if existing is None
                                else {
                                    "number": existing.get("number"),
                                    "state": existing.get("state"),
                                    "title": existing.get("title"),
                                    "body_excerpt": existing.get("body", "")[:10000],
                                    "body_truncated": len(existing.get("body", "")) > 10000,
                                    "request_ids": sorted(work.request_ids(existing.get("body", ""))),
                                },
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                env,
            )
        except RuntimeError:
            raise ValueError(
                "Requirements model API failed; check endpoint, model and credentials before explicitly retrying; prior attempt retained"
            ) from None
        finally:
            if previous_key is None:
                os.environ.pop("GONGGONG_REQUIREMENTS_KEY", None)
            else:
                os.environ["GONGGONG_REQUIREMENTS_KEY"] = previous_key
        if result["finish_reason"] != "stop":
            raise ValueError("Requirements model response incomplete; reconcile retained attempt")
        design = proposal(json.loads(result["text"]), categories)
        agent = next(
            a
            for a in json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))["agents"]
            if a["id"] == "yanshi"
        )
        saved.update(
            phase="proposal_ready", proposal=design, candidate_digest=agent["candidate_digest"], usage=result["usage"]
        )
        save(journal, saved)

    def check_cancel():
        if request.get("_cancel_path") and not Path(request["_cancel_path"]).is_file():
            raise ValueError("Requirements intake cancelled; reconcile any previously submitted remote request")

    check_cancel()
    if design["decision"] == "continue":
        if not existing or existing.get("state") != "open" or len(work.request_ids(existing.get("body", ""))) != 1:
            saved["phase"] = "proposal_invalid"
            save(journal, saved)
            raise ValueError("Yanshi continuation does not match a real open bound Issue")
        issue_number, request_id = number, next(iter(work.request_ids(existing.get("body", ""))))
        revision = "<!-- requirement-revision:" + digest + " -->"
        comments = json.loads(
            work.gh(
                "api",
                f"repos/{settings['repository']}/issues/{number}/comments?per_page=100",
                "--paginate",
                "--slurp",
            )
        )
        if not any(revision in c.get("body", "") for page in comments for c in page):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "revision.md"
                path.write_text(
                    revision
                    + "\n\nYanshi / ClarifyFeature 澄清更新\n\n"
                    + design["goal"]
                    + "\n\n验收：\n"
                    + "\n".join("- " + x for x in design["acceptance"]),
                    encoding="utf-8",
                )
                check_cancel()
                work.gh("issue", "comment", str(number), "--repo", settings["repository"], "--body-file", str(path))
    else:
        request_id = identity
        document = "design-docs/" + request_id + ".md"
        content = "# " + design["title"] + "\n\n<!-- gonggong-request:" + request_id + " -->\n\n"
        content += "需求整理：Yanshi / ClarifyFeature；原始输入摘要：`" + digest + "`。\n\n" + design["goal"] + "\n"
        for heading, key in [("范围", "scope"), ("验收条件", "acceptance"), ("待确认", "questions")]:
            content += "\n## " + heading + "\n\n" + "\n".join("- " + x for x in design[key]) + "\n"
        path = root / document
        path.parent.mkdir(exist_ok=True)
        if path.is_symlink() or (path.exists() and path.read_text(encoding="utf-8") != content):
            raise ValueError("Preserve existing requirement original; cannot overwrite a different proposal")
        if not path.exists():
            with path.open("x", encoding="utf-8") as stream:
                stream.write(content)
        check_cancel()
        if saved.get("publication"):
            created = saved["publication"]
        else:
            saved["phase"] = "publication_attempted"
            save(journal, saved)
            try:
                created = work.issue(root, document, design["title"], design["category"], request_id, True)
            except ValueError as error:
                # A definite GitHub rejection cannot have created an Issue. Retain the
                # proposal so a repaired login/permission can retry without model cost.
                if getattr(error, "http_status", None) in {400, 401, 403, 404, 405, 410, 422}:
                    saved.update(phase="proposal_ready", publication_rejected=error.http_status)
                    save(journal, saved)
                raise
            saved.update(phase="proposal_ready", publication=created)
            save(journal, saved)
        match = re.fullmatch(
            r"https://github.com/" + re.escape(settings["repository"]) + r"/issues/([1-9][0-9]*)", created["url"]
        )
        if not match:
            raise ValueError("Issue creation did not return the configured repository")
        issue_number = int(match[1])
    binding = {"issue_number": issue_number, "request_id": request_id}
    framework = framework_root(root)
    agent = next(
        a
        for a in json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))["agents"]
        if a["id"] == "yanshi"
    )
    if "event" not in saved:
        saved["event"] = {
            "schema_version": 1,
            "event_id": "requirements-" + digest[:32],
            "tenant_id": settings["tenant_id"],
            "request_id": request_id,
            "kind": "step",
            "occurred_at": saved["occurred_at"],
            "source_ref": f"https://github.com/{settings['repository']}/issues/{issue_number}",
            "agent": {
                "id": "yanshi",
                "version": agent["version"],
                "origin": "gonggong-framework",
                "definition_sha256": hashlib.sha256((framework / agent["entry"]).read_bytes()).hexdigest(),
            },
            "payload": {
                "phase": "requirements_only_before_development",
                "skill": "clarify-feature",
                "candidate_digest": saved["candidate_digest"],
                "request_sha256": digest,
                "usage": saved["usage"],
                "input_tokens": saved["usage"].get("input_tokens"),
                "output_tokens": saved["usage"].get("output_tokens"),
                "decision": design["decision"],
                "note": "Requirements generation, not production execution or design approval",
            },
            "evidence_refs": [],
        }
        save(journal, saved)
    bridge.enqueue(root, saved["event"])
    bridge.flush(root)
    if not design["questions"]:
        check_cancel()
        started = bridge.issue_start(root, binding)
        if not started["ok"]:
            return started
    return {
        "ok": True,
        **binding,
        "url": f"https://github.com/{settings['repository']}/issues/{issue_number}",
        "questions": design["questions"],
        "agent": "yanshi",
        "skill": "clarify-feature",
        "ready": not design["questions"],
        "decision": design["decision"],
    }
