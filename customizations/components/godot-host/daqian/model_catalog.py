"""Personal model profiles, verified test evidence, and host-supplied Sinan preferences."""

import hashlib
import json
import math
import os
import secrets
import sqlite3
import sys
from pathlib import Path

from credentials import secret
from local_models import MODEL_ID, current_profile, discover_cli
from model_api import PROTOCOLS, endpoint, invoke


def identity(profile):
    data = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def config_dir():
    if sys.platform == "win32":
        folder = Path(os.environ["LOCALAPPDATA"])
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Application Support"
    else:
        folder = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return folder / "Godot" / "Daqian"


def database(folder=None):
    folder = Path(folder or config_dir())
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "models.sqlite", timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY, config TEXT NOT NULL)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS evaluations(id TEXT NOT NULL, task TEXT NOT NULL, scope TEXT NOT NULL, score REAL, evidence TEXT NOT NULL, PRIMARY KEY(id,task,scope))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS credential_revisions(id TEXT PRIMARY KEY, revision TEXT NOT NULL, ready INTEGER NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS cli_revisions(id TEXT PRIMARY KEY, revision TEXT NOT NULL, active INTEGER NOT NULL)"
    )
    return db


def credential_revision(db, profile_id):
    row = db.execute("SELECT revision, ready FROM credential_revisions WHERE id=?", (profile_id,)).fetchone()
    if row and not row[1]:
        raise ValueError("凭据正在保存或上次保存未完成，请重新保存后验证")
    return row[0] if row else ""


def verification_revision(db, profile_id):
    profile = profiles(db).get(profile_id, {})
    if profile.get("protocol") not in {"codex-cli", "codebuddy-cli"}:
        return credential_revision(db, profile_id)
    row = db.execute("SELECT revision, active FROM cli_revisions WHERE id=?", (profile_id,)).fetchone()
    if not row or not row[1]:
        raise ValueError("本地模型已从当前发现结果移除，请重新连接并验证")
    return row[0]


def _usable(db, profile_id, profile):
    try:
        verification_revision(db, profile_id)
        return current_profile(profile)
    except ValueError:
        return False


def _refresh_cli(db, label, configs):
    protocol = {"Codex": "codex-cli", "CodeBuddy": "codebuddy-cli"}[label]
    discovered = {identity(config): config for config in configs}
    added = 0
    with db:
        db.execute("BEGIN IMMEDIATE")
        for profile_id, profile in profiles(db).items():
            if profile.get("protocol") == protocol and profile_id not in discovered:
                db.execute("DELETE FROM evaluations WHERE id=? AND scope='live'", (profile_id,))
                db.execute("INSERT OR REPLACE INTO cli_revisions VALUES(?,?,0)", (profile_id, secrets.token_hex(16)))
        for profile_id, config in discovered.items():
            added += db.execute("INSERT OR IGNORE INTO profiles VALUES(?,?)", (profile_id, json.dumps(config))).rowcount
            row = db.execute("SELECT active FROM cli_revisions WHERE id=?", (profile_id,)).fetchone()
            if row != (1,):
                db.execute("DELETE FROM evaluations WHERE id=? AND scope='live'", (profile_id,))
                db.execute("INSERT OR REPLACE INTO cli_revisions VALUES(?,?,1)", (profile_id, secrets.token_hex(16)))
    return added


def add(db, config, key, vault=secret):
    return _save_profile(db, config, key, vault)[0]


def _save_profile(db, config, key, vault, *, only_if_missing=False, verification_bindings=None):
    if set(config) != {"name", "model", "endpoint", "protocol"} or not all(
        isinstance(v, str) and v.strip() == v and v and len(v) <= 2048 for v in config.values()
    ):
        raise ValueError("请填写供应商名称、准确型号、协议和接口地址")
    if config["protocol"] not in PROTOCOLS:
        raise ValueError("不支持该接口协议")
    endpoint(config["endpoint"])
    if config["protocol"] == "gemini-generate-content" and "{model}" not in config["endpoint"]:
        raise ValueError("Gemini 接口地址需要 {model} 占位符")
    key_id = identity(config)
    revision = secrets.token_hex(16)
    # Publish a durable pending generation before touching the external vault.
    # Readers reject pending credentials; an in-flight probe cannot revive old
    # proof. Failed external writes stay pending until an explicit save retries.
    with db:
        db.execute("BEGIN IMMEDIATE")
        created = not db.execute("SELECT 1 FROM profiles WHERE id=?", (key_id,)).fetchone()
        if only_if_missing:
            if not created:
                return key_id, False
            credential_revision(db, key_id)
        if not key:
            raise ValueError("请提供本机凭据")
        db.execute("DELETE FROM evaluations WHERE id=? AND scope='live'", (key_id,))
        db.execute("INSERT OR REPLACE INTO credential_revisions VALUES(?,?,0)", (key_id, revision))
    with db:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute("SELECT revision FROM credential_revisions WHERE id=?", (key_id,)).fetchone()
        if current != (revision,):
            raise ValueError("凭据配置已被另一次保存更新，请重新回读")
        vault(key_id, key)
        db.execute("INSERT OR IGNORE INTO profiles VALUES(?,?)", (key_id, json.dumps(config, ensure_ascii=False)))
        db.execute("UPDATE credential_revisions SET ready=1 WHERE id=? AND revision=?", (key_id, revision))
    if verification_bindings is not None:
        # This action's exact key/revision stay private and never enter source
        # rows or durable evidence. A later vault save cannot retarget its probe.
        verification_bindings[key_id] = (revision, key)
    return key_id, created


# Only a provider's explicit model and matching credential are imported.
PROVIDERS = Path(__file__).resolve().parents[3] / "platforms/ai-models/daqian/environment-providers.json"


def connect_local(db, settings, vault=secret, *, refresh_selected=False, verification_bindings=None):
    sources = []
    for label, configs, note in discover_cli(settings):
        added = _refresh_cli(db, label, configs)
        sources.append({
            "name": label,
            "candidate": identity(configs[0]) if configs else "",
            "added": added,
            "existing": len(configs) - added,
            "note": note,
            "models": [config["model"] for config in configs],
        })
    for provider in json.loads(PROVIDERS.read_text(encoding="utf-8")):
        prefix = provider["prefix"]
        label = provider["name"]
        protocol = provider["protocol"]
        url = provider["endpoint"]
        model = os.environ.get(prefix + "_MODEL", "")
        key = os.environ.get(prefix + "_API_KEY")
        if not model and not key:
            continue
        row = {"name": label, "added": 0, "existing": 0, "note": ""}
        sources.append(row)
        if not MODEL_ID.fullmatch(model) or not key:
            row["note"] = "需要 " + prefix + "_MODEL 和 " + prefix + "_API_KEY"
            continue
        if os.environ.get(prefix + "_BASE_URL") or os.environ.get(prefix + "_API_BASE"):
            row["note"] = "使用自定义接口地址，请通过手工入口绑定"
            continue
        config = {"name": label, "protocol": protocol, "endpoint": url, "model": model}
        try:
            _, added = _save_profile(
                db,
                config,
                key,
                vault,
                only_if_missing=not (refresh_selected and not settings.get("backend")),
                verification_bindings=verification_bindings,
            )
            row["added"], row["existing"] = int(added), int(not added)
            row["models"] = [model]
            row["candidate"] = identity(config)
        except (ValueError, OSError):
            row["note"] = "系统凭据存储写入失败"
    if settings.get("backend") in {"0", "3"} and settings.get("model") and settings.get("endpoint"):
        url = settings["endpoint"]
        responses = settings["backend"] == "3"
        if url.endswith(("/chat/completions", "/responses")):
            url = url.removesuffix("/chat/completions").removesuffix("/responses") + (
                "/responses" if responses else "/chat/completions"
            )
        config = {
            "name": "AI Chat",
            "protocol": "responses" if responses else "chat-completions",
            "endpoint": url,
            "model": settings["model"],
        }
        row = {"name": "AI Chat", "added": 0, "existing": 0, "note": "", "models": [config["model"]]}
        sources.append(row)
        try:
            endpoint(url)
            _, added = _save_profile(
                db,
                config,
                settings.get("editor_key", ""),
                vault,
                only_if_missing=not refresh_selected,
                verification_bindings=verification_bindings,
            )
            row["added"], row["existing"] = int(added), int(not added)
            row["candidate"] = identity(config)
        except (ValueError, OSError) as error:
            row["note"] = str(error) if isinstance(error, ValueError) else "系统凭据存储写入失败"
    return sources


def connect_and_verify(db, settings, vault=secret):
    selected_backend = settings.get("backend", "")
    selected_source = {"0": "AI Chat", "1": "CodeBuddy", "2": "Codex", "3": "AI Chat"}.get(selected_backend)
    if selected_backend and selected_source is None:
        raise ValueError("当前连接方式无效，请重新选择后验证")
    verification_bindings = {}
    sources = connect_local(db, settings, vault, refresh_selected=True, verification_bindings=verification_bindings)
    registered = profiles(db)
    # Discovery may enumerate every source, but an explicit connection choice
    # authorizes verification of that source only, including on failure.
    candidates = [row for row in sources if row["name"] == selected_source] if selected_source else sources
    if selected_source and not candidates:
        sources.append({
            "name": selected_source,
            "candidate": "",
            "added": 0,
            "existing": 0,
            "note": "当前选择的连接尚未配置完整，请填写模型、接口地址和凭据后重试",
        })
    for row in candidates:
        candidate = row.get("candidate")
        if candidate not in registered:
            continue
        model = registered[candidate]["model"]
        # An explicit verification must probe the selected current connection.
        # Revoke prior text proof first; a failed retry cannot leave it usable.
        with db:
            db.execute("DELETE FROM evaluations WHERE id=? AND scope='live' AND task='text'", (candidate,))
        challenge = "DAQIAN-" + secrets.token_hex(8)
        try:
            revision = verification_revision(db, candidate)
            probe_key = None
            if registered[candidate]["protocol"] not in {"codex-cli", "codebuddy-cli"}:
                binding = verification_bindings.get(candidate)
                if binding is None or binding[0] != revision:
                    raise ValueError("凭据已被另一次保存更新，请重新验证当前选择")
                probe_key = binding[1]
            # Discovery is bounded to 35 + 40 seconds; leave room for the
            # parent's 180-second UI deadline instead of a 320-second chat call.
            response = invoke(
                registered[candidate], "Reply only with this exact string: " + challenge, [], timeout=60, key=probe_key
            )
            if response["text"].strip() != challenge:
                raise ValueError("验证回复与预期不符")
            record_evaluation(
                db,
                candidate,
                "text",
                "live",
                True,
                [True],
                identity([candidate, challenge]),
                expected_revision=revision,
            )
            row["note"] = f"{model} · 文本验证通过，可用于任务"
            break
        except (ValueError, OSError) as error:
            row["note"] = f"{model} · {error}" if isinstance(error, ValueError) else f"{model} · 验证连接失败"
    return sources


def profiles(db):
    return {i: json.loads(config) for i, config in db.execute("SELECT id,config FROM profiles ORDER BY id")}


def record_evaluation(db, profile_id, task, scope, qualified, outcomes, evidence, *, expected_revision=None):
    """Called by the running evaluation harness, after comparing expected/observed outputs."""
    if (
        profile_id not in profiles(db)
        or scope not in {"synthetic", "live"}
        or type(qualified) is not bool
        or not evidence
    ):
        raise ValueError("评测必须关联确切配置、范围与证据")
    if not all(type(v) is bool for v in outcomes):
        raise ValueError("评测结果无效")
    score = sum(outcomes) / len(outcomes) if outcomes else None
    with db:
        db.execute("BEGIN IMMEDIATE")
        if scope == "live" and (
            expected_revision is None or verification_revision(db, profile_id) != expected_revision
        ):
            raise ValueError("凭据已更新，旧验证结果已失效，请重新验证")
        if scope == "live" and not current_profile(profiles(db)[profile_id]):
            raise ValueError("本地连接来源已改变，旧验证结果已失效，请重新验证")
        if not qualified:
            db.execute("DELETE FROM evaluations WHERE id=? AND task=? AND scope=?", (profile_id, task, scope))
        else:
            db.execute(
                "INSERT OR REPLACE INTO evaluations VALUES(?,?,?,?,?)", (profile_id, task, scope, score, evidence)
            )


def sinan_catalog(db, tasks, scope="live", preferred=""):
    """Only proven capabilities enter the candidate set. Preference is supplied to selectModel."""
    if scope not in {"synthetic", "live"} or not tasks:
        raise ValueError("需要具体任务和评测范围")
    data = profiles(db)
    scores = {}
    for profile_id, task, score in db.execute("SELECT id,task,score FROM evaluations WHERE scope=?", (scope,)):
        if score is None or math.isfinite(score):
            scores.setdefault(profile_id, {})[task] = score
    candidates = []
    for profile_id, values in scores.items():
        if (
            profile_id in data
            and all(task in values for task in tasks)
            and (scope != "live" or _usable(db, profile_id, data[profile_id]))
        ):
            measured = [values[task] for task in tasks]
            score = None if None in measured else min(measured)
            candidates.append((score, profile_id))
    candidates.sort(key=lambda pair: (pair[0] is None, -(pair[0] or 0), pair[1] != preferred, pair[1]))
    return [
        {
            "id": i,
            "available": True,
            "targets": ["agent"],
            "capabilities": sorted(scores[i]),
            "preference": rank,
            "score": score,
            "scope": scope,
            "config": data[i],
        }
        for rank, (score, i) in enumerate(candidates)
    ]
