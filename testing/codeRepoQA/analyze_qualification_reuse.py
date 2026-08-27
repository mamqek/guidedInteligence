"""Run/line-backed audit of qualification reuse, output limits and final snippet survival."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from testing.codeRepoQA.analyze_qualified_file_leads import analyze


def audit(directory):
    result = analyze(directory)
    cards, sources, fingerprints, histories, requests = {}, {}, {}, {}, []
    hits, changed, responses = [], [], []
    for line, raw in enumerate((directory / "retrieval-trace.jsonl").read_text(encoding="utf8").splitlines(), 1):
        event = json.loads(raw)
        p, kind = event["payload"], event["event_type"]
        if kind == "disclosure_cards_created":
            cards.update({c["observation_id"]: c for c in p["cards"]})
        elif kind == "qualification_reuse_evaluated":
            key = (p["observation_id"], p["fingerprint"])
            if p["reused"]:
                assert key in fingerprints or p.get("reason") == "retained_prior_direct_source_over_crop", "Cache reuse without prior matching input"
                hits.append(dict(trace_line=line, **p))
                histories.setdefault(key[0], []).append(dict(trace_line=line, reused=True, round=p["round"], **p["decision"]))
            else:
                if any(identifier == key[0] for identifier, _ in fingerprints):
                    changed.append(dict(trace_line=line, **p))
                fingerprints[key] = line
        elif kind == "qualification_decisions_created":
            for d in p["decisions"]:
                histories.setdefault(d["observation_id"], []).append(dict(trace_line=line, round=p["round"], reused=False, **d))
        elif kind == "llm_request_sent":
            request = p["request_payload"]
            record = dict(trace_line=line, stage=p.get("stage"), round=p.get("round"),
                          capped=any(k in request for k in ("max_tokens", "max_completion_tokens")))
            if p.get("stage") == "evidence_qualification":
                payload = json.loads(next(m["content"] for m in request["messages"] if m["role"] == "user"))
                record["ids"] = [item["observation_id"] for item in payload["observations"]]
                for item in payload["observations"]:
                    sources[item["observation_id"]] = dict(trace_line=line, source_text=item["source_text"])
            requests.append(record)
        elif kind == "llm_response_received":
            response = p["raw_response"]
            responses.append(dict(trace_line=line, stage=p.get("stage"), round=p.get("round"),
                                  usage=response.get("usage"), finish_reason=response["choices"][0].get("finish_reason")))
    for item in hits:
        identifier = item["observation_id"]
        card = cards[identifier]
        item["handle"] = card["handle"]
        item["history"] = histories[identifier]
        item["last_source"] = sources.get(identifier)
        item["final_ranks"] = [e["rank"] for e in result["final"] if
                                e["path"] == card["handle"]["path"] and e["symbol"] == card["handle"].get("symbol")]
        assert not any(identifier in r.get("ids", ()) for r in requests if r["round"] == item["round"]
                       and r["trace_line"] > item["trace_line"]), "Reused snippet sent again"
    result.update(reuse_hits=hits, changed_semantic_inputs=changed, requests=requests, responses=responses,
                  qualification_history=histories)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = [audit(path) for path in args.runs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf8")
    for r in results:
        print(json.dumps({k: r[k] for k in ("run_id", "coverage_status", "sufficient", "implementation_oracles", "retrieval_tokens")}))
        print(json.dumps({"reused": len(r["reuse_hits"]), "changed_inputs": len(r["changed_semantic_inputs"]),
                          "capped_requests": sum(x["capped"] for x in r["requests"])}))
