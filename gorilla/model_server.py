"""Real mini-Jev only. Uses the existing CUDA runtime; never installs dependencies."""
import argparse
import hashlib
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).parent.parent
REVISION = 'c37a0e244e9a559d162fa4758ce831bc3c9bd98c'

def verify_release(release, loader):
    manifest_path = Path(release) / 'verified-release.json'
    if not manifest_path.is_file(): raise ValueError('Verified mini-Jev release manifest is required')
    manifest = json.loads(manifest_path.read_text())
    required = {'config.json','decision_head.safetensors','adapter/adapter_config.json','adapter/adapter_model.safetensors'}
    if (manifest.get('model') != 'samatv256/mini-Jev' or manifest.get('revision') != REVISION
            or set(manifest.get('files',{})) != required):
        raise ValueError('mini-Jev release identity or files do not match the pinned checkpoint')
    for name, expected in manifest['files'].items():
        if hashlib.sha256((Path(release)/name).read_bytes()).hexdigest() != expected:
            raise ValueError('mini-Jev checkpoint file digest mismatch')
    if hashlib.sha256(Path(loader).read_bytes()).hexdigest() != manifest.get('loader_sha256'):
        raise ValueError('mini-Jev published loader digest mismatch')
    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', default=str(ROOT / 'models' / 'mini-Jev'))
    parser.add_argument('--port', type=int, default=8092)
    args = parser.parse_args()
    identity = verify_release(args.release, ROOT / 'vendor' / 'inference.py')
    sys.path.insert(0, str(ROOT / 'vendor'))
    from inference import MiniJev
    import torch
    load_started = time.perf_counter()
    model = MiniJev.load(args.release)
    torch.cuda.synchronize()
    load_ms = (time.perf_counter()-load_started)*1000
    print('Loaded real mini-Jev on ' + torch.cuda.get_device_name(0), flush=True)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            if self.path != '/predict': self.send_error(404); return
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 32768: raise ValueError('Invalid input size')
                payload = json.loads(self.rfile.read(size))
                torch.cuda.synchronize()
                start = time.perf_counter()
                result = model.predict(**payload)
                torch.cuda.synchronize()
                result.update(latency_ms=(time.perf_counter()-start)*1000,
                              model=identity['model'], revision=identity['revision'],
                              device=torch.cuda.get_device_name(0), load_ms=load_ms)
                body=json.dumps(result,allow_nan=False).encode()
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
            except Exception:
                self.send_error(503,'mini-Jev could not produce a valid decision')
    HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__ == '__main__': main()
