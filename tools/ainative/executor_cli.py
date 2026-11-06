"""JSON subprocess bridge; factories are trusted local Python configuration.

--factory package.module:function returns (NodeRegistry, {name: Provider}).
Credentials are obtained by that function from the runtime, never CLI arguments.
"""
import argparse
import importlib
import json
import sys

try:
    from .executor import Executor
    from .extensions import NodeRegistry
except ImportError:
    from executor import Executor
    from extensions import NodeRegistry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--factory")
    parser.add_argument("command", choices=["create", "status", "step", "cancel", "retry", "export"])
    parser.add_argument("--run")
    parser.add_argument("--node")
    args = parser.parse_args()
    host = None
    try:
        registry, providers = NodeRegistry(), {}
        if args.command in ("create", "step"):
            if not args.factory:
                raise ValueError("factory required")
            module, function = args.factory.split(":")
            registry, providers = getattr(importlib.import_module(module), function)()
        host = Executor(args.db, registry, providers)
        if args.command == "create":
            spec = json.load(sys.stdin)
            result = {"run_id": host.create(spec["graph"], spec["manifest"], args.run)}
        elif args.command == "retry":
            host.retry(args.run, args.node)
            result = host.status(args.run)
        else:
            result = getattr(host, args.command)(args.run)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({"ok": False, "error": "executor_command_failed"}))
        return 1
    finally:
        if host:
            host.close()


if __name__ == "__main__":
    sys.exit(main())
