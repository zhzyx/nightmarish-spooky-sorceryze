"""Parallel host lifecycle reporting through the existing Godot Diting outbox."""
import sys
import json
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
import importlib.util

root = Path(sys.argv[1]).resolve()
source = Path(__file__).resolve()
sys.path.insert(0, str(source.parents[2] / 'customizations/components/godot-host'))
spec = importlib.util.spec_from_file_location('godot_host_report', source.parents[2] / 'customizations/components/godot-host/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
payload = json.load(sys.stdin)
settings = json.loads((root / 'work-items.json').read_text(encoding='utf-8'))
request_id = payload.pop('requestId')
issue = payload.pop('issue')
kind = payload.pop('kind')
event = {
    'schema_version': 1, 'event_id': 'parallel-' + uuid.uuid4().hex,
    'tenant_id': settings['tenant_id'], 'request_id': request_id,
    'kind': kind, 'occurred_at': datetime.now(timezone.utc).isoformat(),
    'source_ref': f"https://github.com/{settings['repository']}/issues/{issue}",
    'agent': {'id': 'godot-parallel-codex-host', 'version': '0.1.0',
              'definition_sha256': hashlib.sha256(source.with_name('runner.mjs').read_bytes()).hexdigest(),
              'origin': 'external-authorized-host'},
    'payload': {**payload, 'usage': None, 'usage_reason': 'provider usage not collected by this host',
                'model_basis': 'requested CLI model; provider routing not attested'},
    'evidence_refs': []
}
bridge.enqueue(root, event)
print(json.dumps(bridge.flush(root)))
