import os, secrets, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gorilla.core import Store
state=Path("state");state.mkdir(exist_ok=True)
if os.name != "nt":state.chmod(0o700)
token=state/"worker-token"
if not token.exists():
    with token.open("x") as f:f.write(secrets.token_urlsafe(32))
if os.name != "nt":token.chmod(0o600)
Store(state/"office.sqlite").seed()
print("Synthetic finance-001 seeded; existing state preserved. Private worker token is not displayed.")
