"""Private registry control. Read one JSON line from stdin; credentials never appear in argv."""
from contextlib import closing
import json
import sqlite3
import sys
from pathlib import Path
from repository_access import collaborator

import model_catalog as catalog


def main():
    try:
        if len(sys.argv)!=4:
            raise ValueError("模型配置需要当前仓库及已核实账号")
        actor = collaborator(Path(sys.argv[2]))
        if actor["user_id"]!=sys.argv[3]:
            raise ValueError("GitHub 协作账号已切换")
        with closing(catalog.database()) as db:
            action = sys.argv[1]
            if action == "list":
                result = catalog.profiles(db)
            elif action == "add":
                data = json.loads(sys.stdin.buffer.readline(32769))
                result = {"id":catalog.add(db,data["profile"],data["secret"])}
            else:
                raise ValueError("不支持的目录操作")
        print(json.dumps({"result":result},ensure_ascii=False))
    except (ValueError,KeyError,IndexError,OSError,sqlite3.Error) as error:
        print(json.dumps({"error":str(error) if isinstance(error,ValueError) else "系统存储或配置不可用"},ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
