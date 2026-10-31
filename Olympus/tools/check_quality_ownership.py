"""File-level ownership and duplicate execution checks; not host authorization."""
import json
import sys
from pathlib import Path

FORBIDDEN = {'public_quality_policy', 'local_self_check_and_repair', 'check_and_regression_verdict', 'professional_acceptance', 'risk_and_delivery_acceptance', 'identity_and_state_commit'}

def validate(mapping, plan=None):
    owners = {}
    for item in mapping['responsibilities']:
        key, owner = item['id'], item['owner']
        if key in owners:
            raise ValueError('Multiple responsibility assignments: ' + key)
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError('Responsibility owner is missing')
        owners[key] = owner
    if set(owners) != FORBIDDEN | {'feature_standard_mapping', 'quality_event_impact_disposition_followup'}:
        raise ValueError('Missing or unexpected responsibility')
    if owners['quality_event_impact_disposition_followup'] != 'themis' or any(owners[k] == 'themis' for k in FORBIDDEN | {'feature_standard_mapping'}):
        raise ValueError('Themis responsibility overlap')
    if len(set(owners.values())) != len(owners):
        raise ValueError('Competing quality responsibilities share a role')
    if mapping['themis_owns'] != ['quality_event_impact_disposition_followup'] or set(mapping['themis_must_not_own']) != FORBIDDEN:
        raise ValueError('Themis ownership declaration contradicts responsibility assignments')
    if mapping['event_repairer_must_differ_from_independent_validator'] is not True:
        raise ValueError('Independent verification separation is required')
    if mapping['event_closure_is_delivery_acceptance'] is not False:
        raise ValueError('Event closure cannot approve delivery')
    if mapping['same_check_requires_single_id_and_owner'] is not True:
        raise ValueError('Duplicate checks must be rejected')
    if plan is not None:
        seen, ids = {}, set()
        known = set(plan.get('existing_check_ids', []))
        described = set()
        for existing in plan.get('existing_checks', []):
            known.add(existing['check_id']);described.add(existing['check_id'])
            if existing.get('active', True):
                key = tuple(json.dumps(existing[field], sort_keys=True) for field in mapping['check_identity_fields'])
                if key in seen:
                    raise ValueError('Multiple authoritative active checks have the same identity')
                seen[key] = existing['check_id']
        for task in plan['checks']:
            if task['mode'] == 'reference':
                if task['check_id'] not in known | ids:
                    raise ValueError('Reference has no authoritative check')
                continue
            if known - described:
                raise ValueError('Execution needs existing check definitions, not IDs alone')
            responsibility = task.get('responsibility', 'check_and_regression_verdict')
            if responsibility not in {'check_and_regression_verdict', 'local_self_check_and_repair'}:
                raise ValueError('Check execution has an invalid responsibility')
            if task['mode'] != 'execute' or task['owner_role'] != owners[responsibility]:
                raise ValueError('Check execution assigned outside its responsible role')
            key = tuple(json.dumps(task[field], sort_keys=True) for field in mapping['check_identity_fields'])
            previous = task.get('supersedes_check_id')
            if previous is not None:
                if previous not in known | ids or not isinstance(task.get('revalidation_reason'), str) or not task['revalidation_reason'].strip():
                    raise ValueError('Revalidation needs a known prior check and explicit reason')
                if key in seen and seen[key] != previous:
                    raise ValueError('Revalidation must supersede the current check of this identity')
            if (key in seen and previous != seen[key]) or task['check_id'] in ids or task['check_id'] in known:
                raise ValueError('Duplicate check execution; reuse or explicitly version revalidation')
            seen[key] = task['check_id'];ids.add(task['check_id'])
    return True

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    try:
        mapping = json.loads((root/'domains/quality/responsibility-map.json').read_text(encoding='utf-8'))
        plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')) if len(sys.argv) == 2 else None
        if len(sys.argv) > 2:
            raise ValueError('Usage: check_quality_ownership.py [PLAN.json]')
        validate(mapping, plan)
        print('passed file-level quality ownership checks; host identity and runtime not verified')
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
