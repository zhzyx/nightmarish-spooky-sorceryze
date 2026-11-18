"""Explicit trusted installation entry point, never enabled by create_app alone."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "sinan-workorders"), str(ROOT / "duobao")]


def main():
    import uvicorn
    from api import create_app
    from native_node_api import mount_native_nodes
    from native_remote_worker import RemoteNativeWorker

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--factory", required=True, help="Trusted installed module:function(config) returning NativeWorkflow"
    )
    parser.add_argument("--config", required=True, help="Absolute trusted host JSON; no producer argv/env")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()
    path = Path(args.config)
    if not path.is_absolute():
        parser.error("Absolute configuration path required")
    module, name = args.factory.split(":", 1)
    factory = getattr(importlib.import_module(module), name)
    workflow = factory(json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(workflow.worker, RemoteNativeWorker):
        raise ValueError("Factory must install RemoteNativeWorker explicitly")
    if workflow.worker.workflow is None:
        workflow.worker.bind(workflow)
    app = create_app(workflow.domain, native_store=workflow.worker.store, native_only=True, native_workflow=workflow)
    uvicorn.run(mount_native_nodes(app, workflow.worker), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
