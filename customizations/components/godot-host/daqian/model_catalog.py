"""Personal model profiles, verified test evidence, and host-supplied Sinan preferences."""
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys

from credentials import secret
from model_api import PROTOCOLS, endpoint


def identity(profile):
    data = json.dumps(profile,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(data).hexdigest()


def config_dir():
    if sys.platform == "win32":
        folder = Path(os.environ["LOCALAPPDATA"])
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Application Support"
    else:
        folder = Path(os.environ.get("XDG_CONFIG_HOME",Path.home()/".config"))
    return folder / "Godot" / "Daqian"


def database(folder=None):
    folder = Path(folder or config_dir())
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    db = sqlite3.connect(folder / "models.sqlite",timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY, config TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS evaluations(id TEXT NOT NULL, task TEXT NOT NULL, scope TEXT NOT NULL, score REAL, evidence TEXT NOT NULL, PRIMARY KEY(id,task,scope))")
    return db


def add(db, config, key, vault=secret):
    if set(config) != {"name","model","endpoint","protocol"} or not all(isinstance(v,str) and v.strip() == v and v and len(v)<=2048 for v in config.values()):
        raise ValueError("请填写供应商名称、准确型号、协议和接口地址")
    if config["protocol"] not in PROTOCOLS:
        raise ValueError("不支持该接口协议")
    endpoint(config["endpoint"])
    if config["protocol"]=="gemini-generate-content" and "{model}" not in config["endpoint"]:
        raise ValueError("Gemini 接口地址需要 {model} 占位符")
    key_id = identity(config)
    if not key:
        raise ValueError("请提供本机凭据")
    vault(key_id,key)
    with db:
        db.execute("INSERT OR IGNORE INTO profiles VALUES(?,?)", (key_id,json.dumps(config,ensure_ascii=False)))
    return key_id


def profiles(db):
    return {i:json.loads(config) for i,config in db.execute("SELECT id,config FROM profiles ORDER BY id")}


def record_evaluation(db, profile_id, task, scope, qualified, outcomes, evidence):
    """Called by the running evaluation harness, after comparing expected/observed outputs."""
    if profile_id not in profiles(db) or scope not in {"synthetic","live"} or type(qualified) is not bool or not evidence:
        raise ValueError("评测必须关联确切配置、范围与证据")
    if not all(type(v) is bool for v in outcomes):
        raise ValueError("评测结果无效")
    if not qualified:
        with db:
            db.execute("DELETE FROM evaluations WHERE id=? AND task=? AND scope=?", (profile_id,task,scope))
        return
    score = sum(outcomes)/len(outcomes) if outcomes else None
    with db:
        db.execute("INSERT OR REPLACE INTO evaluations VALUES(?,?,?,?,?)",(profile_id,task,scope,score,evidence))


def sinan_catalog(db, tasks, scope="live", preferred=""):
    """Only proven capabilities enter the candidate set. Preference is supplied to selectModel."""
    if scope not in {"synthetic","live"} or not tasks:
        raise ValueError("需要具体任务和评测范围")
    data = profiles(db)
    scores = {}
    for profile_id, task, score in db.execute("SELECT id,task,score FROM evaluations WHERE scope=?", (scope,)):
        if score is None or math.isfinite(score):
            scores.setdefault(profile_id,{})[task] = score
    candidates = []
    for profile_id, values in scores.items():
        if profile_id in data and all(task in values for task in tasks):
            measured = [values[task] for task in tasks]
            score = None if None in measured else min(measured)
            candidates.append((score,profile_id))
    candidates.sort(key=lambda pair:(pair[0] is None,-(pair[0] or 0),pair[1]!=preferred,pair[1]))
    return [{"id":i, "available":True, "targets":["agent"], "capabilities":sorted(scores[i]),"preference":rank,
             "score":score,"scope":scope, "config":data[i]} for rank,(score,i) in enumerate(candidates)]
