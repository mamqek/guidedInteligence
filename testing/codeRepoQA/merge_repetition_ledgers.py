"""Merge disjoint repetition-campaign ledgers without duplicating valid runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--campaign",
        default="2026-09-03-graphless-four-runs-complete",
        help="Campaign identifier recorded in the merged ledger.",
    )
    args = parser.parse_args()
    merged = load(args.base)
    sources = [args.base.name]
    for path in args.input:
        incoming = load(path)
        sources.append(path.name)
        for case_id, state in incoming["cases"].items():
            target = merged["cases"].get(case_id)
            if target is None:
                raise RuntimeError(f"{path}: unexpected case {case_id}")
            known = {entry["run_id"] for entry in target["campaign_runs"]}
            target["campaign_runs"].extend(entry for entry in state["campaign_runs"] if entry["run_id"] not in known)
            target["failed_attempts"].extend(state["failed_attempts"])
            target["status"] = "complete" if len(target["campaign_runs"]) >= merged["target_valid_runs_per_case"] else "pending"
    incomplete = [case_id for case_id, state in merged["cases"].items() if len(state["campaign_runs"]) != merged["target_valid_runs_per_case"]]
    if incomplete:
        raise RuntimeError("incomplete cases: " + ", ".join(incomplete))
    merged["campaign"] = args.campaign
    merged["source_ledgers"] = sources
    merged["active_case"] = ""
    merged["stop_reason"] = "complete"
    merged["valid_run_count"] = sum(len(state["campaign_runs"]) for state in merged["cases"].values())
    merged["failed_attempt_count"] = sum(len(state["failed_attempts"]) for state in merged["cases"].values())
    args.output.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
