"""Operator-origin integration against the real resident mini-Jev; no model double."""
import json
from pathlib import Path
from urllib.request import Request,urlopen
root=Path(__file__).resolve().parents[1]
proposal={"request_id":"operator-demo-finance-001","message_id":"finance-001",
          "proposed_choices":["DELETE","ARCHIVE","KEEP","FLAG"],
          "agent_activity":"Trusted operator integration demo; autonomous NemoClaw worker integration is pending."}
request=Request("http://127.0.0.1:8091/api/act",json.dumps(proposal).encode(),
                {"Content-Type":"application/json","Authorization":"Bearer "+(root/"state/worker-token").read_text().strip()})
with urlopen(request,timeout=90) as response:result=json.load(response)
assert result["status"]=="verified",result.get("error",result["status"])
assert result["model_output"]["model"]=="samatv256/mini-Jev"
assert any(x["candidate"]=="DELETE" for x in result["excluded"])
assert result["selected_candidate"]==result["approved_action"]["operation"]==result["receipt"]["action"]["operation"]=="ARCHIVE"
assert all(result["verification"].values())
with urlopen("http://127.0.0.1:8091/api/messages?folder=archive",timeout=15) as response:archive=json.load(response)
assert any(m["id"]=="finance-001" and m["body"]==result["before"]["body"] for m in archive)
print(json.dumps(result,indent=2))
print("PASS: protected DELETE excluded, real mini-Jev selected ARCHIVE, exact execution and persisted content verified.")
