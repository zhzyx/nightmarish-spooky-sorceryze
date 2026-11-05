"""Plan source client/stdio service for a trusted shared installation.

The optional SSH alias resolves using the user's existing OpenSSH configuration. The
server operator binds each OS login to its own authenticated gh and to the same store.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

from board import work_items
import plan_store

MAX_REQUEST = 32 * 1024 * 1024


def execute(root, envelope):
    repo = work_items.config(root)[0]["repository"]
    if envelope.get("repository") != repo:
        raise ValueError("共享宿主绑定的仓库不同")
    number = envelope["number"]
    if type(number) is not int or number < 1:
        raise ValueError("工单编号无效")
    source = plan_store.read_source(root, number)
    with plan_store.connect(root) as db:
        if envelope["action"] == "read":
            return plan_store.snapshot(db, source)
        if envelope["action"] == "apply":
            return plan_store.apply(db,source,envelope["draft"])
        raise ValueError("不支持该图操作")


def via_shared_host(alias, payload):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",alias):
        raise ValueError("共享宿主应为 OpenSSH 配置中的主机别名")
    command = ["ssh","-T","-oBatchMode=yes","-oStrictHostKeyChecking=yes","-oClearAllForwardings=yes",
               "-oForwardAgent=no",alias,"daqian-plan-source"]
    try:
        reply = subprocess.run(command,input=payload,capture_output=True,timeout=180)
    except subprocess.TimeoutExpired:
        raise ValueError("共享宿主回执超时，请先回读原工单") from None
    if reply.returncode != 0:
        raise ValueError("共享宿主不可达或登录未获准，请保留草稿并回读")
    parsed = json.loads(reply.stdout)
    if not isinstance(parsed,dict):
        raise ValueError("共享宿主回执格式无效")
    return parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,required=True)
    parser.add_argument("--number",type=int)
    parser.add_argument("action",choices=["read","apply","serve-stdio"])
    parser.add_argument("--request",type=Path)
    parser.add_argument("--result",type=Path)
    args = parser.parse_args()
    root = args.repo.resolve()
    try:
        if args.action == "serve-stdio":
            raw=sys.stdin.buffer.read(MAX_REQUEST+1)
            if len(raw)>MAX_REQUEST:
                raise ValueError("共享计划请求超过大小上限")
            result=execute(root,json.loads(raw))
        else:
            envelope={"action":args.action,"number":args.number,"repository":work_items.config(root)[0]["repository"]}
            if args.action == "apply":
                if not args.request or args.request.stat().st_size>MAX_REQUEST:
                    raise ValueError("计划请求无效或超长")
                envelope["draft"]=json.loads(args.request.read_text(encoding="utf-8"))
            remote=os.environ.get("DAQIAN_PLAN_SSH_HOST","")
            result=via_shared_host(remote,json.dumps(envelope,ensure_ascii=False).encode()) if remote else execute(root,envelope)
            result["source_mode"]="shared_host" if remote else "local_installation"
    except (KeyError,OSError,RuntimeError,ValueError,TypeError,sqlite3.Error) as error:
        result={"ok":False,"error":str(error)}
    if args.action=="serve-stdio":
        sys.stdout.buffer.write(json.dumps(result,ensure_ascii=False).encode("utf-8"))
    elif args.result:
        temporary=args.result.with_suffix(".partial")
        temporary.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
        os.replace(temporary,args.result)
    else:
        parser.error("--result required for editor commands")


if __name__=="__main__":
    main()
