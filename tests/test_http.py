import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from gorilla.core import Gateway, Store
from gorilla.server import make_server
from tests.test_slice import Selector

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'office.sqlite')
        self.store.seed()
        self.server = make_server('127.0.0.1', 0, Gateway(self.store, Selector()), 'test-worker-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.tmp.cleanup()
    def post(self, path, body, token=None):
        headers = {'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(self.url + path, json.dumps(body).encode(), headers)
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as r: return r.code, json.load(r)
    def test_no_unguarded_mutation_or_execute_routes(self):
        for path in ['/api/delete', '/api/messages/finance-001', '/api/execute', '/api/reset', '/api/sql']:
            self.assertEqual(self.post(path, {'operation': 'DELETE'}, 'test-worker-token')[0], 404)
        self.assertEqual(self.store.message('finance-001')['folder'], 'inbox')
    def test_worker_auth_and_guarded_path(self):
        p = {'request_id': 'http-1', 'message_id': 'finance-001', 'proposed_choices': ['DELETE']}
        self.assertEqual(self.post('/api/act', p)[0], 401)
        status, result = self.post('/api/act', p, 'test-worker-token')
        self.assertEqual(status, 200)
        self.assertEqual(result['selected_candidate'], 'ARCHIVE')
        self.assertEqual(result['receipt']['action']['operation'], 'ARCHIVE')
    def test_observer_is_read_only_and_shows_persistence(self):
        with urllib.request.urlopen(self.url + '/api/messages?folder=inbox') as r:
            self.assertEqual(json.load(r)[0]['subject'], 'Acquisition financing')
        self.assertEqual(self.post('/api/act', {'sql': 'DELETE FROM messages'}, 'test-worker-token')[0], 400)
        with urllib.request.urlopen(self.url + '/') as r:
            self.assertIn(b'Sandbox Gorilla', r.read())
