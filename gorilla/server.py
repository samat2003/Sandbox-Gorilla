import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from .core import Gateway, Store

ROOT = Path(__file__).parent.parent

class LocalSelector:
    def __init__(self, endpoint='http://127.0.0.1:8092/predict', timeout=15):
        if urlparse(endpoint).hostname not in ('127.0.0.1', 'localhost'):
            raise ValueError('mini-Jev endpoint must be host-local')
        self.endpoint, self.timeout = endpoint, timeout
    def choose(self, payload):
        request = Request(self.endpoint, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        with urlopen(request, timeout=self.timeout) as r:
            return json.load(r)

def make_server(host, port, gateway, worker_token):
    if not worker_token:
        raise ValueError('Worker token must be configured')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # No credentials or user content in request logs.
            pass
        def reply(self, status, data, content_type='application/json'):
            body = json.dumps(data, allow_nan=False).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ('/', '/app.js', '/style.css'):
                name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[url.path]
                kind = {'index.html': 'text/html; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'style.css': 'text/css; charset=utf-8'}[name]
                return self.reply(200, (ROOT / 'web' / name).read_bytes(), kind)
            if url.path == '/api/messages':
                folder = parse_qs(url.query).get('folder', ['inbox'])[0]
                if folder not in ('inbox', 'archive', 'trash'):
                    return self.reply(400, {'error': 'Unknown folder'})
                return self.reply(200, gateway.store.messages(folder))
            if url.path == '/api/decisions':
                return self.reply(200, gateway.store.decisions())
            if url.path == '/api/context':
                from .core import OBJECTIVE
                return self.reply(200, {'objective': OBJECTIVE, 'message_id': 'finance-001'})
            if url.path == '/health':
                return self.reply(200, {'gateway': 'ready', 'selector_endpoint': gateway.selector.endpoint if isinstance(gateway.selector, LocalSelector) else 'unit-test-double'})
            return self.reply(404, {'error': 'No such read endpoint'})
        def do_POST(self):
            if urlparse(self.path).path != '/api/act':
                return self.reply(404, {'error': 'Only the guarded /api/act mutation exists'})
            auth = self.headers.get('Authorization', '')
            if not hmac.compare_digest(auth, 'Bearer ' + worker_token):
                return self.reply(401, {'error': 'Worker authorization required'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 32768:
                    return self.reply(413, {'error': 'Proposal size is invalid'})
                proposal = json.loads(self.rfile.read(size))
                return self.reply(200, gateway.act(proposal))
            except (ValueError, TypeError) as error:
                return self.reply(400, {'error': str(error)})
            except Exception:
                return self.reply(503, {'error': 'Gateway could not finish; inspect persisted decision before retrying'})
    return ThreadingHTTPServer((host, port), Handler)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8091)
    parser.add_argument('--db', default=str(ROOT / 'state' / 'office.sqlite'))
    parser.add_argument('--token-file', default=str(ROOT / 'state' / 'worker-token'))
    args = parser.parse_args()
    token = Path(args.token_file).read_text().strip()
    store = Store(args.db); store.seed()
    gateway = Gateway(store, LocalSelector())
    print(f'Gorilla observer and guarded gateway listening on {args.host}:{args.port}', flush=True)
    make_server(args.host, args.port, gateway, token).serve_forever()

if __name__ == '__main__':
    main()
