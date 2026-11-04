import unittest
from closure import Candidate, REQUIRED, finalize


class FakeHost:
    """Simulation only; never production evidence or authority."""
    def __init__(self):
        self.c = Candidate('owner/repo', 1, 'request', 'a', 'tree', 'base', 'scope', 'event')
        self.state = dict(candidate=self.c, published=False, closed=False, status='in-review', main='base')
        self.calls = []
        self.checks = dict.fromkeys(REQUIRED, True)
        self.fail = None
        self.receipt = True
        self.drift = False

    def action(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise RuntimeError(name)

    def authorize(self, c): self.action('authorize')
    def acquire(self, c): self.action('acquire'); return 'lease'
    def release(self, lease): self.action('release')
    def read(self, c): self.action('read'); return dict(self.state)
    def verify(self, c):
        self.action('verify')
        if self.drift: self.state['main'] = 'new'
        return self.checks
    def publish(self, c): self.action('publish'); self.state['published'] = True
    def read_main(self, c):
        self.action('read_main')
        return dict(candidate=c, contained=self.receipt, remote_commit='merged', remote_tree='tree')
    def record(self, c, phase, evidence):
        self.action(phase)
        if phase == 'verified':
            self.state['verification'] = dict(candidate=c, receipt_id='simulation', checks=dict(evidence))
    def mark_done(self, c): self.action('mark_done'); self.state['status'] = 'done'
    def close(self, c): self.action('close'); self.state['closed'] = True
    def reconcile(self, c): self.action('reconcile')


class ClosureTests(unittest.TestCase):
    def test_success_order(self):
        h = FakeHost()
        self.assertTrue(finalize(h.c, h)['closed'])
        sequence = ['verify', 'verified', 'publish', 'read_main', 'release.completed',
                    'mark_done', 'close', 'issue.closed', 'reconcile', 'release']
        self.assertEqual([x for x in h.calls if x in sequence], sequence)

    def test_all_failed_unknown_and_missing_checks_stop_publish(self):
        for check in REQUIRED:
            for value in (False, None, 'passed'):
                h = FakeHost(); h.checks[check] = value
                with self.assertRaises(ValueError): finalize(h.c, h)
                self.assertNotIn('publish', h.calls)
            h = FakeHost(); del h.checks[check]
            with self.assertRaises(ValueError): finalize(h.c, h)
            self.assertNotIn('close', h.calls)

    def test_drift_stops_publish(self):
        h = FakeHost(); h.drift = True
        with self.assertRaises(ValueError): finalize(h.c, h)
        self.assertNotIn('publish', h.calls)

    def test_missing_remote_receipt_stops_close(self):
        h = FakeHost(); h.receipt = False
        with self.assertRaises(ValueError): finalize(h.c, h)
        self.assertNotIn('mark_done', h.calls)

    def test_failed_durable_receipt_stops_close(self):
        h = FakeHost(); h.fail = 'release.completed'
        with self.assertRaises(RuntimeError): finalize(h.c, h)
        self.assertNotIn('mark_done', h.calls)

    def test_retry_close_does_not_republish(self):
        h = FakeHost(); h.fail = 'close'
        with self.assertRaises(RuntimeError): finalize(h.c, h)
        h.fail = None
        finalize(h.c, h)
        self.assertEqual(h.calls.count('publish'), 1)

    def test_retry_reconcile_does_not_republish(self):
        h = FakeHost(); h.fail = 'reconcile'
        with self.assertRaises(RuntimeError): finalize(h.c, h)
        h.fail = None
        finalize(h.c, h)
        self.assertEqual(h.calls.count('publish'), 1)

    def test_unauthorized_no_mutation(self):
        h = FakeHost(); h.fail = 'authorize'
        with self.assertRaises(RuntimeError): finalize(h.c, h)
        self.assertEqual(h.calls, ['authorize'])

    def test_closed_before_delivery_rejected(self):
        h = FakeHost(); h.state['closed'] = True
        with self.assertRaises(ValueError): finalize(h.c, h)
        self.assertNotIn('publish', h.calls)

    def test_unknown_remote_states_rejected(self):
        for field in ('published', 'closed'):
            for value in (None, 'unknown', 0, 1):
                h = FakeHost(); h.state[field] = value
                with self.assertRaises(ValueError): finalize(h.c, h)
                self.assertNotIn('publish', h.calls)
                self.assertNotIn('close', h.calls)

    def test_published_without_verification_cannot_close(self):
        h = FakeHost(); h.state['published'] = True
        with self.assertRaises(ValueError): finalize(h.c, h)
        self.assertNotIn('close', h.calls)

    def test_stale_verification_cannot_close(self):
        h = FakeHost(); h.fail = 'close'
        with self.assertRaises(RuntimeError): finalize(h.c, h)
        h.fail = None
        h.state['verification']['candidate'] = 'stale'
        with self.assertRaises(ValueError): finalize(h.c, h)
        self.assertEqual(h.calls.count('close'), 1)

    def test_unknown_state_on_second_read_rejected(self):
        h = FakeHost()
        original = h.read
        def read(c):
            state = original(c)
            if 'verified' in h.calls:
                state['published'] = 0
            return state
        h.read = read
        with self.assertRaises(ValueError): finalize(h.c, h)
        self.assertNotIn('publish', h.calls)


if __name__ == '__main__': unittest.main()
