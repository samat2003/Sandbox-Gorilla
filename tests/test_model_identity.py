import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from gorilla.model_server import verify_release

class ModelIdentityTests(unittest.TestCase):
    def test_manifest_is_required_and_altered_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);loader=root/'inference.py';loader.write_text('loader')
            (root/'config.json').write_text('{}')
            with self.assertRaises(ValueError):verify_release(root,loader)
            manifest={'model':'samatv256/mini-Jev','revision':'c37a0e244e9a559d162fa4758ce831bc3c9bd98c',
                      'files':{'config.json':hashlib.sha256(b'{}').hexdigest()},
                      'loader_sha256':hashlib.sha256(b'loader').hexdigest()}
            (root/'verified-release.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):verify_release(root,loader) # Incomplete manifest.
            for name in ['decision_head.safetensors','adapter/adapter_config.json','adapter/adapter_model.safetensors']:
                path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(b'fixture')
                manifest['files'][name]=hashlib.sha256(b'fixture').hexdigest()
            (root/'verified-release.json').write_text(json.dumps(manifest))
            self.assertEqual(verify_release(root,loader)['revision'],manifest['revision'])
            (root/'decision_head.safetensors').write_bytes(b'altered')
            with self.assertRaises(ValueError):verify_release(root,loader)
