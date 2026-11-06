"""Private registry control. Read one JSON line from stdin; credentials never appear in argv."""
from contextlib import closing
import json
import sqlite3
import sys
from pathlib import Path
from repository_access import AccessDenied, collaborator, session_actor, session_path, work_items

import model_catalog as catalog


def main():
    try:
        if len(sys.argv) not in (4,5):
            raise ValueError("模型配置需要当前仓库及已核实账号")
        root = Path(sys.argv[2])
        actor = session_actor(root,sys.argv[4]) if len(sys.argv)==5 and sys.argv[1]=="list" else collaborator(root)
        if actor["user_id"]!=sys.argv[3]:
            raise AccessDenied("GitHub 协作账号已切换")
        with closing(catalog.database()) as db:
            action = sys.argv[1]
            if action == "list":
                result = catalog.profiles(db)
            elif action == "connect-local":
                settings = json.loads(sys.stdin.buffer.readline(32769))
                if not isinstance(settings, dict) or not all(isinstance(v, str) for v in settings.values()):
                    raise ValueError("本地 CLI 设置格式无效")
                result = catalog.connect_local(db, settings)
            elif action == "add":
                data = json.loads(sys.stdin.buffer.readline(32769))
                result = {"id":catalog.add(db,data["profile"],data["secret"])}
            else:
                raise ValueError("不支持的目录操作")
        print(json.dumps({"result":result},ensure_ascii=False))
    except (AccessDenied, work_items.GitHubCommandError) as error:
        denied = isinstance(error, AccessDenied) or error.http_status in (401, 403)
        if denied and len(sys.argv)==5 and sys.argv[4]:
            session_path(sys.argv[4]).unlink(missing_ok=True)
        print(json.dumps({"denied":denied,"error":str(error)},ensure_ascii=False))
        return 1
    except (ValueError,KeyError,IndexError,OSError,sqlite3.Error) as error:
        print(json.dumps({"error":str(error) if isinstance(error,ValueError) else "系统存储或配置不可用"},ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
