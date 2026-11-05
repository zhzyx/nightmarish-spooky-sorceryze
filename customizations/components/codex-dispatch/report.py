"""Current operator host reporting through the existing Diting file adapter."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone

root = Path(sys.argv[1]).resolve()
module = root / 'customizations/components/godot-host/bridge.py'
sys.path.insert(0, str(module.parent))
spec = importlib.util.spec_from_file_location('operator_reporting', module)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
payload = json.load(sys.stdin)
settings = json.loads((root / 'work-items.json').read_text(encoding='utf-8'))
record = payload['record']
# Private transport retains raw tool arguments; published events carry only identity.
assignment = record.get('assignment', {})
receipt = record.get('receipt') or {}
public = {'ticket': assignment.get('ticket'), 'reservation_key': assignment.get('key'),
          'state': record.get('state'), 'stage': record.get('stage'),
          'record_sha256': hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest(),
          'source_revision': assignment.get('sourceSnapshot', {}).get('sha256'),
          'requested_model': assignment.get('model', {}).get('id'),
          'worker_id': receipt.get('workerId'), 'receipt_reference': receipt.get('reference'),
          'setup_pending': receipt.get('setupPending'), 'observed_model': receipt.get('observedModel')}
event = {
    'schema_version': 1, 'event_id': 'dispatch-' + uuid.uuid4().hex,
    'tenant_id': settings['tenant_id'], 'request_id': payload['requestId'],
    'kind': 'handoff' if record.get('state') in ('running', 'delegated_pending_host') else 'step',
    'occurred_at': datetime.now(timezone.utc).isoformat(),
    'source_ref': f"https://github.com/{settings['repository']}/issues/{payload['issue']}",
    'agent': {'id': 'codex-current-operator-host', 'version': '0.1.0',
              'definition_sha256': hashlib.sha256(Path(__file__).with_name('operator.mjs').read_bytes()).hexdigest(),
              'origin': 'external-authorized-host'},
    'payload': {'record': public, 'usage': None,
                'usage_unknown_reason': 'native tool usage not exposed'}, 'evidence_refs': []}
bridge.enqueue(root, event)
print(json.dumps(bridge.flush(root)))
