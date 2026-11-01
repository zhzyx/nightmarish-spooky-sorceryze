"""Verify registered Sinan sources and relocate their complete bound implementation."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath


def merge(raw, binding):
    # Current mainline includes the full event-driven module. Do not resurrect
    # the archived scheduler or require the previous host's implementation tree.
    base = json.loads(raw['framework-manifest.json'])
    current = next((m for m in base.get('modules', []) if m['id'] == 'sinan'), None)
    if current and 'modules/sinan/refresh.mjs' in raw:
        record = json.loads(raw[current['admission_pass']])
        module = json.loads(raw[current['manifest']])
        digest = record['subject']['version_or_digest']
        if record.get('template') is not False or record.get('status') != 'approved' or record['subject']['id'] != 'sinan' or current['version'] != digest['version'] or module['version'] != digest['version']:
            raise ValueError('Current module approval mismatch')
        decision, review = record['approval'], record['review']
        if not decision.get('approver_id') or decision.get('approver_id')==review.get('evaluator_id') or not decision.get('authority_ref') or decision.get('revocation_ref') or decision.get('superseded_by'):
            raise ValueError('Current module approval inactive')
        if review.get('independence')!='independent_subagent_review' or not review.get('evaluator_id') or any(review.get(k)!='pass' for k in ['gonggong_framework','applicable_validation']) or review.get('concision',{}).get('status')!='pass' or any(review.get('yuanheng',{}).get(k)!='pass' for k in ['purpose','truth','economy','authority','adaptation','continuity']):
            raise ValueError('Current module review incomplete')
        baseline=record['baseline'];lock=json.loads(raw['foundation.lock.json'])
        if baseline.get('foundation_sha256')!=lock['sha256'] or baseline.get('foundation_version')!=lock['version'] or baseline.get('policy_version')!=base['version'] or baseline.get('yuanheng_version')!=base['yuanheng_version']:
            raise ValueError('Current module baseline mismatch')
        approved=datetime.fromisoformat(decision['approved_at'].replace('Z','+00:00'))
        if approved.tzinfo is None or approved>datetime.now(timezone.utc) or not record['subject'].get('scope'):
            raise ValueError('Current module scope/time invalid')
        if decision.get('expires_at') and datetime.fromisoformat(decision['expires_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc):
            raise ValueError('Current module approval expired')
        evidence={'registration/'+current['admission_pass']:raw[current['admission_pass']]}
        seen=set()
        for item in digest['files']:
            rel=item['path']
            if rel.casefold() in seen or rel not in raw or hashlib.sha256(raw[rel]).hexdigest()!=item['sha256']:
                raise ValueError('Current module evidence changed: '+rel)
            seen.add(rel.casefold());evidence['registration/'+rel]=raw[rel]
        source=Path(binding['framework']).resolve()
        for rel in [*review['evidence_refs'],decision['decision_evidence_ref']]:
            if PureWindowsPath(rel).drive or Path(rel).is_absolute():raise ValueError('Absolute evidence reference forbidden')
            target=source/rel
            boundary=source.parent/'work' if rel.startswith('../work/') else source
            target.resolve().relative_to(boundary.resolve())
            if not target.is_file() or any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in [target,*target.parents]):raise ValueError('Module review evidence unavailable or linked')
            evidence['source-package/'+target.resolve().relative_to(source.parent).as_posix()]=target.read_bytes()
        return evidence
    raise ValueError('Current self-contained event-driven Sinan module required')
