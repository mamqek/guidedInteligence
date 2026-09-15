"""Replay real source comparisons; never reports full-pipeline acceptance."""
import argparse
import json
from pathlib import Path

from testing.codeRepoQA.run_case import _load_project_llm_config
from testing.codeRepoQA.semantic_owner_comparison import compare


def fixtures(root):
    previous = {}
    coverage = []
    seen = set()
    result = []
    for line in (root / "retrieval-trace.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event["event_type"] == "coverage_evaluated":
            coverage = event["payload"]["coverage"]
        if event["event_type"] != "owner_reevaluation_audited":
            continue
        current = {c["id"]: c for row in event["payload"]["elections"] for c in row["candidates"]}
        for cid in sorted(current.keys() - previous.keys()):
            challenger = current[cid]
            old = [c for c in previous.values() if c["id"] in current and
                   c["handle"]["path"].casefold() == challenger["handle"]["path"].casefold()]
            if not old:
                continue
            incumbent = min(old, key=lambda c: c["ranking_key"])
            shared = set(incumbent["qualification"]["supported_obligation_ids"]) & set(
                challenger["qualification"]["supported_obligation_ids"])
            unresolved = [c for c in coverage if c["obligation_id"] in shared and
                          c["status"] in ("partial", "missing") and c["missing_claim"].strip()]
            if not unresolved:
                continue
            question = unresolved[0]
            payload = {"question": question["missing_claim"]}
            for name, c in (("incumbent", incumbent), ("challenger", challenger)):
                payload[name] = {k: c[k] for k in ("handle", "source_text", "source_mode", "truncation_reason")}
            signature = json.dumps(payload, sort_keys=True)
            if signature in seen:
                continue
            seen.add(signature)
            result.append({"run": root.name, "round": event["payload"]["round"],
                           "obligation": question["obligation_id"],
                           "incumbent_id": incumbent["id"], "challenger_id": cid, "payload": payload})
        previous = current
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    rows = [row for root in args.run for row in fixtures(root)]
    config = _load_project_llm_config(json.loads(Path("configs/testing/workspace.json").read_text())) if args.execute else None
    report = {"kind": "isolated_real_llm_replay" if args.execute else "fixture_inventory", "rows": []}
    for index, row in enumerate(rows):
        item = {**row, "repeats": []}
        report["rows"].append(item)
        if args.execute:
            for repeat in range(2):
                events = []
                record = {"events": events}
                item["repeats"].append(record)
                try:
                    record["result"] = compare(config, row["payload"], lambda name, value: events.append({"event_type": name, "payload": value}))
                except Exception as exc:
                    record["error"] = f"{type(exc).__name__}: {exc}"
                finally:
                    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(index, repeat, record.get("result", {}).get("outcome", record.get("error")), flush=True)
        print(index, row["run"], row["round"], row["payload"]["incumbent"]["handle"]["symbol"], "->", row["payload"]["challenger"]["handle"]["symbol"], flush=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
