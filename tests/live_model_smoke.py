"""Explicit real-model check: python -m tests.live_model_smoke. No model double."""
import json
import tempfile
from pathlib import Path
from gorilla.core import Gateway, Store
from gorilla.server import LocalSelector

def main():
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp)/'live.sqlite'); store.seed()
        gateway = Gateway(store, LocalSelector(timeout=60))
        result = gateway.act({'request_id':'live-mini-1','message_id':'finance-001',
                              'proposed_choices':['DELETE','ARCHIVE','KEEP','FLAG'],
                              'agent_activity':'Explicit real-model smoke check; not an autonomous worker run.'})
        assert result['status'] == 'verified', result.get('error', result['status'])
        assert result['model_output']['model'] == 'samatv256/mini-Jev'
        assert [x['id'] for x in result['permitted_candidates']] == ['ARCHIVE','KEEP','FLAG']
        selected = result['selected_candidate']
        assert selected == result['approved_action']['operation'] == result['receipt']['action']['operation']
        assert all(result['verification'].values())
        before = store.message('finance-001')
        failed = Gateway(store, LocalSelector('http://127.0.0.1:1/predict', timeout=1)).act(
            {'request_id':'live-mini-unavailable','message_id':'finance-001','proposed_choices':['DELETE']})
        assert failed['status'] == 'pending'
        assert store.message('finance-001') == before
        print(json.dumps({'LIVE-1':'passed','LIVE-5':'passed','decision':result}, indent=2))

if __name__ == '__main__': main()
