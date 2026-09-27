"""Validate the curated source-transition Oracle against local snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ORACLE = Path(__file__).with_name("source-transition-oracle.json")
DEFAULT_INVENTORY = ROOT / "testing/codeRepoQA/statistics/runs/2026-09-16-five-mode-four-runs.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument(
        "--test-root",
        type=Path,
        default=Path(r"C:\Programming\guidedInteligence_testcases"),
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    args = parse_args()
    oracle = load_json(args.oracle)
    inventory = load_json(args.inventory)
    errors: list[str] = []

    campaign_cases = {run["case"] for run in inventory["run_inventory"]}
    cases = oracle.get("cases", [])
    oracle_ids = [case.get("case_id") for case in cases]

    if len(cases) != 35:
        errors.append(f"expected 35 Oracle cases, found {len(cases)}")
    if len(oracle_ids) != len(set(oracle_ids)):
        errors.append("case IDs are not unique")
    missing = sorted(campaign_cases - set(oracle_ids))
    extra = sorted(set(oracle_ids) - campaign_cases)
    if missing:
        errors.append(f"campaign cases missing from Oracle: {missing}")
    if extra:
        errors.append(f"Oracle cases absent from campaign: {extra}")

    for case in cases:
        case_id = case.get("case_id", "<missing-case-id>")
        snapshot = case.get("pre_resolution", {}).get("snapshot", "")
        snapshot_root = args.test_root / case_id / "s" / snapshot
        if not snapshot_root.is_dir():
            errors.append(f"{case_id}: missing snapshot directory {snapshot_root}")
            continue

        unit_ids: set[str] = set()
        required_paths: set[str] = set()
        for section in ("evidence_units", "supporting_units"):
            for unit in case.get(section, []):
                unit_id = unit.get("id", "")
                if not unit_id or unit_id in unit_ids:
                    errors.append(f"{case_id}: missing or duplicate unit ID {unit_id!r}")
                unit_ids.add(unit_id)
                source = unit.get("source", {})
                source_path = source.get("path", "")
                path = snapshot_root / Path(source_path)
                if section == "evidence_units" and unit.get("required", True):
                    required_paths.add(source_path)
                if not path.is_file():
                    if unit.get("evidence_type") != "scoped_absence":
                        errors.append(f"{case_id}/{unit_id}: missing source file {source_path}")
                    if source.get("source_presence") != "absent" or source.get("sha256") is not None:
                        errors.append(f"{case_id}/{unit_id}: absent source is not recorded consistently")
                    continue
                if source.get("source_presence") != "present":
                    errors.append(f"{case_id}/{unit_id}: existing source is not recorded as present")
                start = source.get("line_start")
                end = source.get("line_end")
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > len(lines):
                    errors.append(
                        f"{case_id}/{unit_id}: invalid range {start}-{end} for {source_path} ({len(lines)} lines)"
                    )
                    continue
                text = "\n".join(lines[start - 1 : end])
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if source.get("sha256") != digest:
                    errors.append(f"{case_id}/{unit_id}: source hash differs for {source_path}:{start}-{end}")
                for anchor in unit.get("anchors", []):
                    if anchor not in text:
                        errors.append(
                            f"{case_id}/{unit_id}: anchor {anchor!r} absent from {source_path}:{start}-{end}"
                        )
                partial_range = unit.get("partial_range")
                if partial_range:
                    partial_start = partial_range.get("line_start")
                    partial_end = partial_range.get("line_end")
                    if not isinstance(partial_start, int) or not isinstance(partial_end, int) or partial_start < 1 or partial_end < partial_start or partial_end > len(lines):
                        errors.append(f"{case_id}/{unit_id}: invalid partial range {partial_start}-{partial_end}")

        if case.get("required_file_count") != len(required_paths):
            errors.append(f"{case_id}: required_file_count differs from required evidence paths")
        implementation_files = case.get("implementation_oracle_files", [])
        if case.get("implementation_oracle_file_count") != len(implementation_files):
            errors.append(f"{case_id}: implementation_oracle_file_count is inconsistent")

        transition_ids: set[str] = set()
        for transition in case.get("transitions", []):
            transition_id = transition.get("id", "")
            if not transition_id or transition_id in transition_ids:
                errors.append(f"{case_id}: missing or duplicate transition ID {transition_id!r}")
            transition_ids.add(transition_id)
            for endpoint in ("from", "to"):
                ref = transition.get(endpoint)
                if ref not in unit_ids:
                    errors.append(f"{case_id}/{transition_id}: unknown {endpoint} unit {ref!r}")

    if errors:
        print("Oracle validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validated {len(cases)} cases against {args.test_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
