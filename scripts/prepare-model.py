"""Download the exact public release, validate pinned digests, then cache its pinned base."""
import hashlib,json,sys
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
REV="c37a0e244e9a559d162fa4758ce831bc3c9bd98c"
FILES={
 "config.json":"6818158094b3324ace3da1fc067470e169cd77563ebe525686248eec3eff0f6d",
 "decision_head.safetensors":"f06d990297b23ffabc7a0d5eba3670830c337b742f8e3a30fe3907783e0bac88",
 "adapter/adapter_config.json":"225fd0b2ecd112f1684d1c4bfa4a1e5c7c5bc99d6792b43bb62dd33341f92fb7",
 "adapter/adapter_model.safetensors":"765e987436517f18ef902641a197c719a415292d082615ca891e38590fbffeda"}
LOADER="e8e101298da719a6192c5fa29a5dba90ed5d670c16714828fda2d50b3bf3fbb3"
release=ROOT/"models/mini-Jev"
for name,expected in {**FILES,"inference.py":LOADER}.items():
 target=ROOT/"vendor/inference.py" if name=="inference.py" else release/name
 if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==expected:continue
 with urlopen(f"https://huggingface.co/samatv256/mini-Jev/resolve/{REV}/{name}",timeout=120) as r: data=r.read()
 if hashlib.sha256(data).hexdigest()!=expected:raise ValueError("Pinned release digest mismatch: "+name)
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
(release/"verified-release.json").write_text(json.dumps({"model":"samatv256/mini-Jev","revision":REV,"files":FILES,"loader_sha256":LOADER},indent=2))
if "--checkpoint-only" not in sys.argv:
 from huggingface_hub import snapshot_download
 snapshot_download("Qwen/Qwen3-0.6B",revision="c1899de289a04d12100db370d81485cdf75e47ca",
                   allow_patterns=["*.json","*.safetensors","*.txt","*.jinja"])
print("Pinned mini-Jev release and loader verified; weights remain ignored by Git.")
