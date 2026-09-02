from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = ROOT / "testing" / "codeRepoQA" / "statistics" / "runs" / "2026-08-15-native-vs-codex.json"
DEFAULT_CONFIG = ROOT / "configs" / "testing" / "statistics-codex-luna.json"
DEFAULT_LEDGER = ROOT / "testing" / "codeRepoQA" / "statistics" / "runs" / "2026-08-26-codex-luna-four-runs.json"
TEST_ROOT = Path(r"C:\Programming\guidedInteligence_testcases")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a fixed-count CodeRepoQA repetition campaign.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--run-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--max-consecutive-failures", type=int, default=3)
    parser.add_argument("--initialize-only", action="store_true")
    return parser.parse_args()


def case_ids(report_path: Path) -> list[str]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return sorted({str(row["case_id"]) for row in report["rows"]})


def historical_runs(case_id: str, *, retrieval_mode: str, config: dict[str, Any]) -> list[str]:
    result: list[str] = []
    runs = TEST_ROOT / case_id / "runs"
    if not runs.is_dir():
        return result
    for run_dir in sorted(runs.iterdir()):
        metadata_path = run_dir / "run-metadata.json"
        if not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        matches_mode = metadata.get("retrieval_mode") == retrieval_mode
        matches_profile = retrieval_mode != "codex" or (
            metadata.get("codex_model") == config.get("codex_model")
            and metadata.get("codex_prompt_profile") == config.get("codex_prompt_profile")
        )
        if matches_mode and matches_profile and (run_dir / "orchestration-result.json").is_file() and (
            run_dir / "evaluator-comparison.json"
        ).is_file():
            result.append(run_dir.name)
    return result


def initialize(args: argparse.Namespace) -> dict[str, Any]:
    if args.ledger.is_file():
        return json.loads(args.ledger.read_text(encoding="utf-8"))
    config = json.loads(args.run_config.read_text(encoding="utf-8"))
    retrieval_mode = str(config["retrieval_mode"])
    cases = {
        case_id: {
            "status": "pending",
            "historical_runs": historical_runs(case_id, retrieval_mode=retrieval_mode, config=config),
            "campaign_runs": [],
            "failed_attempts": [],
        }
        for case_id in case_ids(args.report)
    }
    return {
        "schema_version": 1,
        "campaign": f"{datetime.now(timezone.utc).date().isoformat()}-{retrieval_mode}-four-runs",
        "created_at": now(),
        "updated_at": now(),
        "retrieval_mode": retrieval_mode,
        "codex_model": config.get("codex_model", ""),
        "codex_prompt_profile": config.get("codex_prompt_profile", ""),
        "run_config": str(args.run_config.relative_to(ROOT)).replace("\\", "/"),
        "target_valid_runs_per_case": args.repetitions,
        "historical_runs_are_reference_only": True,
        "active_case": "",
        "stop_reason": "",
        "cases": cases,
    }


def is_valid_run(run_dir: Path, ledger: dict[str, Any]) -> tuple[bool, str]:
    required = ("run-metadata.json", "orchestration-result.json", "evaluator-comparison.json")
    missing = [name for name in required if not (run_dir / name).is_file()]
    if missing:
        return False, "missing artifacts: " + ", ".join(missing)
    metadata = json.loads((run_dir / "run-metadata.json").read_text(encoding="utf-8"))
    expected = {"retrieval_mode": ledger["retrieval_mode"]}
    if ledger["retrieval_mode"] == "codex":
        expected.update(
            codex_model=ledger["codex_model"],
            codex_prompt_profile=ledger["codex_prompt_profile"],
        )
    mismatches = [f"{key}={metadata.get(key)!r}" for key, value in expected.items() if metadata.get(key) != value]
    if mismatches:
        return False, "configuration mismatch: " + ", ".join(mismatches)
    orchestration = json.loads((run_dir / "orchestration-result.json").read_text(encoding="utf-8"))
    retrieval = orchestration.get("retrieval_result")
    if not isinstance(retrieval, dict):
        return False, "orchestration result has no retrieval_result"
    coverage_status = str(retrieval.get("coverage_status") or "unknown")
    evidence = retrieval.get("evidence")
    if coverage_status == "failed":
        return False, "retrieval coverage_status=failed"
    if not isinstance(evidence, list) or not evidence:
        summary = retrieval.get("retrieval_summary")
        stop_reason = str(summary.get("stop_reason") or "") if isinstance(summary, dict) else ""
        suffix = f", stop_reason={stop_reason}" if stop_reason else ""
        return False, f"retrieval returned no usable evidence (coverage_status={coverage_status}{suffix})"
    return True, ""


def write_ledger(path: Path, ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    markdown_path = path.with_suffix(".md")
    target = int(ledger["target_valid_runs_per_case"])
    completed = sum(len(value["campaign_runs"]) for value in ledger["cases"].values())
    lines = [
        f"# {ledger['retrieval_mode'].title()} Four-Run Campaign",
        "",
        f"- Configuration: `{ledger['retrieval_mode']}` / `{ledger.get('codex_model') or 'workspace pipeline'}` / `{ledger.get('codex_prompt_profile') or 'current defaults'}`",
        f"- Campaign target: {len(ledger['cases'])} cases × {target} valid runs = {len(ledger['cases']) * target}",
        f"- Completed valid runs: {completed}",
        f"- Active testcase: `{ledger.get('active_case') or 'none'}`",
        f"- Stop reason: `{ledger.get('stop_reason') or 'none'}`",
        "- Historical runs are references only and are not included in the four-run campaign average.",
        "",
        "| Testcase | Status | Campaign run IDs | Failed attempts | Historical Luna reference | Remaining |",
        "|---|---|---|---|---|---:|",
    ]
    for case_id, value in sorted(ledger["cases"].items()):
        campaign = "<br>".join(item["run_id"] for item in value["campaign_runs"])
        failures = "<br>".join(
            f"{item.get('run_id') or 'no run'}: {item['reason']}" for item in value["failed_attempts"]
        )
        historical = "<br>".join(value.get("historical_runs", value.get("historical_luna_runs", [])))
        remaining = max(0, target - len(value["campaign_runs"]))
        lines.append(
            f"| `{case_id}` | {value['status']} | {campaign} | {failures} | {historical} | {remaining} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def newest_new_run(case_id: str, before: set[str]) -> Path | None:
    runs = TEST_ROOT / case_id / "runs"
    if not runs.is_dir():
        return None
    created = [item for item in runs.iterdir() if item.is_dir() and item.name not in before]
    return max(created, key=lambda item: item.stat().st_mtime, default=None)


def main() -> int:
    args = parse_args()
    ledger = initialize(args)
    write_ledger(args.ledger, ledger)
    if args.initialize_only:
        print(args.ledger)
        return 0

    consecutive_failures = 0
    target = int(ledger["target_valid_runs_per_case"])
    for case_id, state in sorted(ledger["cases"].items()):
        while len(state["campaign_runs"]) < target:
            state["status"] = "running"
            ledger["active_case"] = case_id
            ledger["stop_reason"] = ""
            write_ledger(args.ledger, ledger)
            runs_dir = TEST_ROOT / case_id / "runs"
            before = {item.name for item in runs_dir.iterdir()} if runs_dir.is_dir() else set()
            issue = ROOT / "testing" / "codeRepoQA" / "corpus" / "cases" / case_id / "issue.json"
            command = [
                sys.executable,
                str(ROOT / "testing" / "codeRepoQA" / "run_case.py"),
                "evaluate-case",
                "--run-config",
                str(args.run_config),
                "--issue-json",
                str(issue),
            ]
            started_at = now()
            completed = subprocess.run(command, cwd=ROOT, check=False)
            run_dir = newest_new_run(case_id, before)
            valid, reason = (False, "run directory was not created") if run_dir is None else is_valid_run(run_dir, ledger)
            if completed.returncode == 0 and valid and run_dir is not None:
                state["campaign_runs"].append({
                    "run_id": run_dir.name,
                    "started_at": started_at,
                    "completed_at": now(),
                })
                consecutive_failures = 0
            else:
                state["failed_attempts"].append({
                    "run_id": run_dir.name if run_dir else "",
                    "started_at": started_at,
                    "completed_at": now(),
                    "return_code": completed.returncode,
                    "reason": reason or f"runner exited {completed.returncode}",
                })
                consecutive_failures += 1
            state["status"] = "complete" if len(state["campaign_runs"]) >= target else "pending"
            ledger["active_case"] = ""
            write_ledger(args.ledger, ledger)
            if consecutive_failures >= args.max_consecutive_failures:
                ledger["stop_reason"] = f"stopped_after_{consecutive_failures}_consecutive_failures"
                write_ledger(args.ledger, ledger)
                return 1
    ledger["active_case"] = ""
    ledger["stop_reason"] = "complete"
    write_ledger(args.ledger, ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
