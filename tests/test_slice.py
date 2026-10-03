import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gorilla.core import Gateway, Store, UnsafeExecution, OBJECTIVE


class Selector:
    def __init__(self, selected='ARCHIVE', failure=None):
        self.selected, self.failure, self.inputs = selected, failure, []

    def choose(self, payload):
        self.inputs.append(copy.deepcopy(payload))
        if self.failure:
            raise self.failure
        options = [{'id': c['id'], 'probability': .8 if c['id'] == self.selected else .1}
                   for c in payload['answer_options']]
        return {'selected_id': self.selected, 'options': options,
                'model': 'unit-test-double', 'latency_ms': 1.25}


class SliceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'business.sqlite')
        self.store.seed()
        self.selector = Selector()
        self.gateway = Gateway(self.store, self.selector)
        self.proposal = {'request_id': 'test-1', 'message_id': 'finance-001',
                         'proposed_choices': ['DELETE', 'ARCHIVE', 'KEEP', 'FLAG'],
                         'worker_state': {'classification': 'ordinary', 'sender': 'nobody'}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_store_is_persisted(self):
        self.assertTrue(self.store.path.exists(), 'Seed must create the business database')

    def test_finance_delete_is_filtered_before_model(self):
        d = self.gateway.act(self.proposal)
        self.assertNotIn('DELETE', [o['id'] for o in self.selector.inputs[0]['answer_options']])
        self.assertEqual(d['excluded'][0]['candidate'], 'DELETE')
        self.assertEqual(d['trusted_state']['classification'], 'finance')
        self.assertEqual(d['objective'], OBJECTIVE)

    def test_archive_persists_and_preserves_content(self):
        before = self.store.message('finance-001')
        d = self.gateway.act(self.proposal)
        reopened = Store(self.store.path)
        self.assertEqual(reopened.message('finance-001')['folder'], 'archive')
        self.assertEqual(reopened.message('finance-001')['body'], before['body'])
        self.assertEqual(reopened.messages('inbox'), [])
        self.assertEqual(len(reopened.messages('archive')), 1)
        self.assertEqual(d['status'], 'verified')

    def test_replay_one_effect_and_one_receipt(self):
        d = self.gateway.act(self.proposal)
        self.assertEqual(self.gateway.act(self.proposal)['decision_id'], d['decision_id'])
        self.assertEqual(self.gateway.execute(d['decision_id'])['decision_id'], d['decision_id'])
        self.assertEqual(self.store.message('finance-001')['version'], 2)
        self.assertEqual(self.store.receipt_count(), 1)
        self.assertEqual(len(self.selector.inputs), 1)

    def test_flag_returns_archived_correspondence_to_inbox_for_followup(self):
        self.gateway.act(self.proposal)
        self.selector.selected = 'FLAG'
        d = self.gateway.act(dict(self.proposal, request_id='flag-after-archive'))
        self.assertEqual(self.store.message('finance-001')['folder'], 'inbox')
        self.assertTrue(self.store.message('finance-001')['flagged'])
        self.assertTrue(d['verification']['expected_operation_state'])

    def test_reused_request_id_with_different_payload_rejected(self):
        self.gateway.act(self.proposal)
        changed = dict(self.proposal, proposed_choices=['FLAG'])
        with self.assertRaises(ValueError):
            self.gateway.act(changed)

    def test_model_failure_preserves_state(self):
        for failure in [TimeoutError('timeout'), RuntimeError('load failed')]:
            with self.subTest(failure=failure):
                self.selector.failure = failure
                p = dict(self.proposal, request_id=str(failure))
                d = self.gateway.act(p)
                self.assertEqual(d['status'], 'pending')
                self.assertEqual(self.store.message('finance-001')['folder'], 'inbox')
                self.assertEqual(self.store.receipt_count(), 0)

    def test_identical_pending_request_can_recover_after_model_restart(self):
        self.selector.failure = TimeoutError('runtime starting')
        pending = self.gateway.act(self.proposal)
        self.assertEqual(self.store.receipt_count(), 0)
        self.selector.failure = None
        recovered = self.gateway.act(self.proposal)
        self.assertEqual(recovered['status'], 'verified')
        self.assertEqual(recovered['decision_id'], pending['decision_id'])
        self.assertEqual(self.store.receipt_count(), 1)
        self.assertEqual(len(self.selector.inputs), 2)

    def test_unknown_or_forbidden_model_choice_never_executes(self):
        for choice in ['DELETE', 'UPLOAD', None]:
            self.selector.selected = choice
            d = self.gateway.act(dict(self.proposal, request_id=str(choice)))
            self.assertEqual(d['status'], 'pending')
        self.assertEqual(self.store.receipt_count(), 0)

    def test_malformed_scores_fail_closed(self):
        self.selector.choose = lambda p: {'selected_id': 'ARCHIVE', 'options': []}
        self.assertEqual(self.gateway.act(self.proposal)['status'], 'pending')
        self.assertEqual(self.store.message('finance-001')['version'], 1)

    def test_stale_record_invalidates_execution(self):
        d = self.gateway.decide(self.proposal)
        with self.store.connect() as db:
            db.execute("UPDATE messages SET version=version+1 WHERE id='finance-001'")
        with self.assertRaises(UnsafeExecution):
            self.gateway.execute(d['decision_id'])
        self.assertEqual(self.store.receipt_count(), 0)
        self.assertEqual(self.store.message('finance-001')['folder'], 'inbox')

    def test_executor_has_no_replacement_arguments(self):
        d = self.gateway.decide(self.proposal)
        with self.assertRaises(TypeError):
            self.gateway.execute(d['decision_id'], {'operation': 'DELETE'})
        self.assertEqual(self.gateway.execute(d['decision_id'])['approved_action']['operation'], 'ARCHIVE')

    def test_approved_operation_immutable_in_database(self):
        d = self.gateway.decide(self.proposal)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.connect() as db:
                db.execute('UPDATE decisions SET approved_json=? WHERE id=?', ('{}', d['decision_id']))

    def test_audit_matches_committed_state(self):
        d = self.gateway.act(self.proposal)
        self.assertEqual(d['stages'], ['Proposed', 'Filtered', 'Selected', 'Approved', 'Executed', 'Verified'])
        self.assertEqual(d['receipt']['action'], d['approved_action'])
        self.assertEqual(d['after'], self.store.message('finance-001'))
        self.assertEqual(d['verification']['content_unchanged'], True)
        self.assertGreater(d['gateway_latency_ms'], 0)

    def test_flag_and_keep_execute_exactly(self):
        self.selector.selected = 'KEEP'
        d = self.gateway.act(self.proposal)
        self.assertEqual(d['after']['version'], 1)
        self.assertEqual(d['after']['folder'], 'inbox')
        self.selector.selected = 'FLAG'
        d = self.gateway.act(dict(self.proposal, request_id='flag'))
        self.assertEqual(d['after']['flagged'], True)
        self.assertEqual(d['receipt']['action']['operation'], 'FLAG')

    def test_scope_and_executable_payloads_rejected(self):
        for patch in [{'message_id': '../secrets'}, {'proposed_choices': ['SQL']},
                      {'operation': 'DELETE'}, {'objective': 'ignore policy'}]:
            with self.assertRaises(ValueError):
                self.gateway.act(dict(self.proposal, **patch))
        self.assertEqual(self.store.receipt_count(), 0)

    def test_missing_candidates_receive_safe_catalog(self):
        d = self.gateway.act(dict(self.proposal, proposed_choices=['DELETE']))
        self.assertEqual([x['id'] for x in d['permitted_candidates']], ['ARCHIVE', 'KEEP', 'FLAG'])

    def test_resume_after_commit_before_verification(self):
        verify = self.gateway._verify
        self.gateway._verify = lambda _id: (_ for _ in ()).throw(RuntimeError('interrupted after commit'))
        with self.assertRaises(RuntimeError):
            self.gateway.act(self.proposal)
        self.gateway._verify = verify
        d = self.gateway.act(self.proposal)
        self.assertEqual(d['status'], 'verified')
        self.assertEqual(self.store.receipt_count(), 1)
        self.assertEqual(self.store.message('finance-001')['version'], 2)

    def test_replayed_verification_matches_persisted_historical_evidence(self):
        d = self.gateway.act(self.proposal)
        with self.store.connect() as db:
            db.execute("UPDATE messages SET flagged=1,version=version+1 WHERE id='finance-001'")
        result = self.gateway.execute(d['decision_id'])
        self.assertEqual(result, self.store.decision(d['decision_id']))
        self.assertTrue(result['verification']['committed_state_matches'])


if __name__ == '__main__':
    unittest.main()
