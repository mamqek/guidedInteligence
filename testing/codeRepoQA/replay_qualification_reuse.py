"""Audit recorded judgments with the runtime reuse key; never generate substitute decisions."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationReuseCache


def audit(directory):
    cache, pending, rows = {}, {}, []
    for line, raw in enumerate((directory / "retrieval-trace.jsonl").read_text(encoding="utf8").splitlines(), 1):
        event = json.loads(raw)
        p = event["payload"]
        if event["event_type"] == "llm_request_sent" and p.get("stage") == "evidence_qualification":
            request = p["request_payload"]
            payload = json.loads(next(x["content"] for x in request["messages"] if x["role"] == "user"))
            prompt = next(x["content"] for x in request["messages"] if x["role"] == "system")
            pending = {}
            for item in payload["observations"]:
                fingerprint = QualificationReuseCache.fingerprint(payload, item, prompt_text=prompt,
                                                                  model_context={"model": request["model"]})
                key = (item["observation_id"], fingerprint)
                prior = cache.get(key)
                row = {"request_line": line, "round": p["round"], "observation_id": key[0],
                       "fingerprint": fingerprint, "chars": len(item["source_text"]),
                       "path": payload["file_contexts"][item["file_context_id"]]["path"],
                       "symbol": item["source_handle"].get("symbol"), "would_reuse": prior is not None,
                       "previous": prior}
                rows.append(row)
                pending[key[0]] = (key, row)
        elif event["event_type"] == "qualification_decisions_created":
            for decision in p["decisions"]:
                if decision["observation_id"] not in pending:
                    continue
                key, row = pending[decision["observation_id"]]
                row["recorded_decision"] = decision
                row["decision_line"] = line
                cache.setdefault(key, {"round": p["round"], "line": line, "decision": decision})
            pending = {}
    return {"run_id": directory.name, "judgments": len(rows),
            "reuse_count": sum(x["would_reuse"] for x in rows), "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}))
