"""Package-free Telegram task interface. This is not an OpenClaw worker."""
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.request import Request, urlopen
from .core import CATALOG

ROOT = Path(__file__).parent.parent

def save_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    tmp.replace(path)

class GatewayClient:
    def __init__(self):
        self.token = (ROOT/'state/worker-token').read_text().strip()
    def request(self, path, body=None):
        headers = {'Content-Type':'application/json'}
        if body is not None: headers['Authorization'] = 'Bearer ' + self.token
        req = Request('http://172.18.0.1:8091'+path,
                      json.dumps(body).encode() if body is not None else None, headers)
        with urlopen(req, timeout=25) as r: return json.load(r)

class Bridge:
    def __init__(self, gateway, state_path, pair_code):
        self.gateway, self.state_path, self.pair_code = gateway, state_path, pair_code
        self.state = json.loads(state_path.read_text()) if state_path.exists() else {}
    def handle(self, update):
        msg = update.get('message', {})
        chat, sender = msg.get('chat', {}), msg.get('from', {})
        if chat.get('type') != 'private' or sender.get('is_bot') or chat.get('id') != sender.get('id'):
            return None
        user = chat.get('id')
        if not isinstance(user, int): return None
        text = msg.get('text', '').strip()
        if not self.state.get('owner'):
            if not text.startswith('/pair ') or not hmac.compare_digest(text[6:].strip(), self.pair_code):
                return None
            self.state['owner'] = user
            save_private(self.state_path, self.state)
            return 'Connected to Sandbox Gorilla. Use /inbox, /process, or /status.'
        if user != self.state['owner']: return None
        command = text.split()[0].split('@')[0] if text else ''
        if command in ('/start','/help','/pair'):
            return 'Sandbox Gorilla: /inbox reads the inbox; /archive reads archive; /process submits the finance email to the policy gate; /status shows the latest decision. This interface is a command adapter; OpenClaw is not running.'
        if command in ('/inbox','/archive'):
            rows = self.gateway.request('/api/messages?folder='+('archive' if command=='/archive' else 'inbox'))
            return '\n'.join(f"{m['id']}: {m['subject']} ({m['folder']})" for m in rows) or 'Folder is empty.'
        if command == '/process':
            d = self.gateway.request('/api/act', {'request_id':f"telegram-{user}-{update['update_id']}",
                'message_id':'finance-001','proposed_choices':list(CATALOG),
                'agent_activity':'Telegram operator command adapter: submit bounded inbox choices to Gorilla; no worker model invoked.'})
            return self.describe(d)
        if command == '/status':
            ds = self.gateway.request('/api/decisions')
            return self.describe(ds[0]) if ds else 'No decision yet. Use /process.'
        return 'Use /inbox, /archive, /process, or /status. Free-form autonomous work requires the local worker runtime.'
    @staticmethod
    def describe(d):
        status = d.get('status','unknown')
        lines = [f"Decision {d.get('decision_id','unknown')}: {status}"]
        lines.append('Selected: '+str(d.get('selected_candidate') or 'none'))
        if status != 'verified': lines.append('No inbox change is confirmed. If pending, local mini-Jev is unavailable or its response was rejected.')
        else: lines.append('Approved action executed; stored inbox state independently verified.')
        return '\n'.join(lines)

class TelegramClient:
    def __init__(self, token): self.token = token
    def call(self, method, body):
        # Never log URL, request, response, exception text, or token.
        req = Request('https://api.telegram.org/bot'+self.token+'/'+method,
                      json.dumps(body).encode(), {'Content-Type':'application/json'})
        with urlopen(req, timeout=40) as r: data = json.load(r)
        if not data.get('ok'): raise RuntimeError('Telegram request rejected')
        return data['result']

def main():
    config = Path('/home/dell/.config/sandbox-gorilla')
    client = TelegramClient((config/'telegram.token').read_text().strip())
    code_path = config/'telegram-pair-code'
    if not code_path.exists(): save_private(code_path, secrets.token_hex(4))
    bridge = Bridge(GatewayClient(), config/'telegram-state.json', json.loads(code_path.read_text()))
    print('Telegram command adapter running; inbox mutations use the guarded gateway.', flush=True)
    while True:
        try:
            updates = client.call('getUpdates', {'offset':bridge.state.get('offset',0),'timeout':25,'allowed_updates':['message']})
            bridge.state['last_poll_ok'] = time.time()
            save_private(bridge.state_path, bridge.state)
            for update in updates:
                try: reply = bridge.handle(update)
                except Exception:
                    reply = 'Gorilla could not finish. Check /status before retrying.' if update.get('message',{}).get('chat',{}).get('id') == bridge.state.get('owner') else None
                if reply: client.call('sendMessage', {'chat_id':update['message']['chat']['id'],'text':reply})
                bridge.state['offset'] = update['update_id']+1
                save_private(bridge.state_path, bridge.state)
        except Exception:
            print('Telegram connection retry; credentials and message content omitted.', flush=True)
            time.sleep(3)

if __name__ == '__main__': main()
