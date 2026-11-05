"""Private registry control. Read one JSON line from stdin; credentials never appear in argv."""
from contextlib import closing
import json
import sqlite3
import sys

import model_catalog as catalog


def main():
    try:
        with closing(catalog.database()) as db:
            action = sys.argv[1]
            if action == "list":
                result = catalog.profiles(db)
            elif action == "add":
                data = json.loads(sys.stdin.readline(32769))
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
