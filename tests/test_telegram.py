import tempfile
import unittest
from pathlib import Path
from gorilla.telegram import Bridge

class GatewayDouble:
    def __init__(self): self.calls = []
    def request(self, path, body=None):
        self.calls.append((path, body))
        if path.startswith('/api/messages'): return [{'id':'finance-001','subject':'Acquisition financing','folder':'inbox'}]
        if path == '/api/act': return {'decision_id':'d1','status':'pending','filtered_candidates':['DELETE']}
        return []

class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gateway = GatewayDouble()
        self.bridge = Bridge(self.gateway, Path(self.tmp.name)/'telegram.json', 'test-pair-code')
    def tearDown(self): self.tmp.cleanup()
    def message(self, text, user=7, kind='private'):
        return {'update_id':42,'message':{'text':text,'chat':{'id':user,'type':kind},'from':{'id':user}}}
    def test_unpaired_and_groups_cannot_access_business_state(self):
        self.assertIsNone(self.bridge.handle(self.message('/inbox')))
        self.assertIsNone(self.bridge.handle(self.message('/pair test-pair-code', kind='group')))
        self.assertEqual(self.gateway.calls, [])
    def test_pairing_persists_and_other_user_is_rejected(self):
        self.assertIn('Connected', self.bridge.handle(self.message('/pair test-pair-code')))
        resumed = Bridge(self.gateway, self.bridge.state_path, '999999')
        self.assertIn('Acquisition financing', resumed.handle(self.message('/inbox')))
        self.assertIsNone(resumed.handle(self.message('/inbox', user=8)))
    def test_process_uses_only_guarded_route_and_stable_request(self):
        self.bridge.handle(self.message('/pair test-pair-code'))
        reply = self.bridge.handle(self.message('/process'))
        path, body = self.gateway.calls[-1]
        self.assertEqual(path, '/api/act')
        self.assertEqual(body['request_id'], 'telegram-7-42')
        self.assertEqual(body['proposed_choices'], ['DELETE','ARCHIVE','KEEP','FLAG'])
        self.assertIn('pending', reply)
        self.assertIn('No inbox change', reply)
    def test_no_arbitrary_action_or_text_execution(self):
        self.bridge.handle(self.message('/pair test-pair-code'))
        self.bridge.handle(self.message('/delete finance-001'))
        self.assertEqual(self.gateway.calls, [])
