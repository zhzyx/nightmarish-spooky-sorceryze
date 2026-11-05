"""Event-driven release orchestration. Only a trusted host supplies the port.

No daemon, credentials, model-selected commands or inferred approval. The host
must authenticate mandate/admission and implement the existing gates and APIs.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Candidate:
    repository: str
    issue: int
    request_id: str
    commit: str
    tree: str
    expected_main: str
    scope_digest: str
    event_id: str


class Host(Protocol):
    def authorize(self, candidate): ...
    def acquire(self, candidate): ...
    def release(self, lease): ...
    def read(self, candidate): ...
    def verify(self, candidate): ...
    def publish(self, candidate): ...
    def read_main(self, candidate): ...
    def record(self, candidate, phase, evidence): ...
    def mark_done(self, candidate): ...
    def close(self, candidate): ...
    def reconcile(self, candidate): ...


REQUIRED = frozenset({
    'scope_acceptance', 'contributions_complete', 'independent_review',
    'admission', 'issue_gate', 'delivery', 'committed_data', 'required_ci',
    'identity', 'reporting_binding',
})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verified(checks):
    require(isinstance(checks, dict) and set(checks) == REQUIRED,
            'Missing or unexpected required checks')
    require(all(v is True for v in checks.values()), 'Failed or unknown check')


def finalize(candidate: Candidate, host: Host):
    """Advance once per real event; reread remote truth on every retry.

    Candidate is a provisional task-branch commit. publish performs the actual
    guarded main integration. A host must never merge on an unknown response;
    the next explicit event enters read() and reconciles remote receipt first.
    """
    require(candidate.issue > 0 and all(isinstance(v, str) and v.strip()
            for k, v in vars(candidate).items() if k != 'issue'), 'Incomplete candidate')
    host.authorize(candidate)
    lease = host.acquire(candidate)
    try:
        state = host.read(candidate)
        require(state['candidate'] == candidate, 'Candidate or scope drift')
        require(type(state['published']) is bool and type(state['closed']) is bool,
                'Unknown publication or Issue state; reconcile first')
        # Remote receipt must bind the exact candidate, target, and full Issue scope.
        if not state['published']:
            require(not state['closed'], 'Issue closed before delivery')
            require(state['main'] == candidate.expected_main, 'Main advanced; reintegrate')
            checks = host.verify(candidate)
            verified(checks)
            host.record(candidate, 'verified', checks)
            current = host.read(candidate)
            require(type(current['published']) is bool and type(current['closed']) is bool,
                    'Unknown state on verification reread')
            require({k: v for k, v in current.items() if k != 'verification'} ==
                    {k: v for k, v in state.items() if k != 'verification'},
                    'Source changed during verification')
            state = current
            proof = state.get('verification') or {}
            require(proof.get('candidate') == candidate and bool(proof.get('receipt_id')),
                    'Missing durable verification receipt')
            verified(proof.get('checks'))
            host.publish(candidate)
        else:
            proof = state.get('verification') or {}
            require(proof.get('candidate') == candidate and bool(proof.get('receipt_id')),
                    'Missing historical verification receipt')
            verified(proof.get('checks'))
        receipt = host.read_main(candidate)
        require(receipt.get('candidate') == candidate and receipt.get('contained') is True
                and bool(receipt.get('remote_commit')) and bool(receipt.get('remote_tree')),
                'Missing exact remote delivery receipt')
        # Durable receipt before any Issue mutation. Failure leaves Issue open.
        host.record(candidate, 'release.completed', receipt)
        host.mark_done(candidate)
        host.close(candidate)
        final = host.read(candidate)
        require(final['candidate'] == candidate and final['published'] is True
                and final['closed'] is True and final['status'] == 'done',
                'Issue completion not confirmed')
        host.record(candidate, 'issue.closed', final)
        host.reconcile(candidate)
        return final
    except Exception as error:
        host.record(candidate, 'pending_reconciliation', {'error': str(error)})
        raise
    finally:
        host.release(lease)
