from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path(r"C:\Programming\guidedInteligence_testcases")
MANIFEST = ROOT / "testing" / "codeRepoQA" / "corpus" / "selection_manifest.json"
OUTPUT_DIR = ROOT / "testing" / "codeRepoQA" / "statistics" / "runs"
OUTPUT_STEM = "2026-08-15-native-vs-codex"
NATIVE_RUN_FLOOR = "run-20260815T011600Z"
K_VALUES = (1, 2, 5, 10)


@dataclass(frozen=True)
class RunSelection:
    run_id: str
    run_dir: Path
    model: str
    profile: str
    coverage_status: str
    sufficient: bool
    evidence_count: int
    comparison: dict[str, object]


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def run_health(run_dir: Path) -> tuple[str, bool, int]:
    result = load_json(run_dir / "orchestration-result.json")
    retrieval = result.get("retrieval_result", {})
    if not isinstance(retrieval, dict):
        return "unknown", False, 0
    evidence = retrieval.get("evidence", [])
    return (
        str(retrieval.get("coverage_status", "unknown")),
        bool(retrieval.get("sufficient", False)),
        len(evidence) if isinstance(evidence, list) else 0,
    )


def select_native(case_id: str) -> RunSelection | None:
    runs_root = TEST_ROOT / case_id / "runs"
    # The campaign rule is the first valid run at/after NATIVE_RUN_FLOOR.
    # Later successful diagnostic or repeat runs must not replace it based on score.
    for run_dir in sorted(runs_root.glob("run-*")):
        if run_dir.name < NATIVE_RUN_FLOOR:
            continue
        metadata_path = run_dir / "run-metadata.json"
        comparison_path = run_dir / "evaluator-comparison.json"
        result_path = run_dir / "orchestration-result.json"
        if not (metadata_path.exists() and comparison_path.exists() and result_path.exists()):
            continue
        metadata = load_json(metadata_path)
        if metadata.get("retrieval_mode") != "workspace":
            continue
        llm = metadata.get("llm_config", {})
        model = str(llm.get("model", "")) if isinstance(llm, dict) else ""
        coverage, sufficient, evidence_count = run_health(run_dir)
        if coverage == "failed" or evidence_count == 0:
            continue
        return RunSelection(
            run_id=run_dir.name,
            run_dir=run_dir,
            model=model,
            profile="workspace-final",
            coverage_status=coverage,
            sufficient=sufficient,
            evidence_count=evidence_count,
            comparison=load_json(comparison_path),
        )
    return None


def latest_native_attempt(case_id: str) -> dict[str, object] | None:
    runs_root = TEST_ROOT / case_id / "runs"
    for run_dir in sorted(runs_root.glob("run-*"), reverse=True):
        if run_dir.name < NATIVE_RUN_FLOOR:
            continue
        metadata_path = run_dir / "run-metadata.json"
        if not metadata_path.exists():
            return {"case_id": case_id, "run_id": run_dir.name, "state": "hard_error", "reason": "run terminated before run-metadata.json"}
        metadata = load_json(metadata_path)
        if metadata.get("retrieval_mode") != "workspace":
            continue
        result_path = run_dir / "orchestration-result.json"
        if not result_path.exists():
            return {"case_id": case_id, "run_id": run_dir.name, "state": "hard_error", "reason": "run terminated before orchestration-result.json"}
        result = load_json(result_path)
        retrieval = result.get("retrieval_result", {})
        summary = retrieval.get("retrieval_summary", {}) if isinstance(retrieval, dict) else {}
        reason = str(summary.get("failure_reason", "")) if isinstance(summary, dict) else ""
        return {
            "case_id": case_id,
            "run_id": run_dir.name,
            "state": "invalid_artifact",
            "coverage_status": retrieval.get("coverage_status", "unknown") if isinstance(retrieval, dict) else "unknown",
            "reason": reason,
        }
    return None


def select_codex(case_id: str) -> RunSelection:
    runs_root = TEST_ROOT / case_id / "runs"
    candidates: list[RunSelection] = []
    for run_dir in sorted(runs_root.glob("run-*"), reverse=True):
        metadata_path = run_dir / "run-metadata.json"
        comparison_path = run_dir / "evaluator-comparison.json"
        result_path = run_dir / "orchestration-result.json"
        if not (metadata_path.exists() and comparison_path.exists() and result_path.exists()):
            continue
        metadata = load_json(metadata_path)
        if metadata.get("retrieval_mode") != "codex" or metadata.get("codex_prompt_profile") != "efficient":
            continue
        model = str(metadata.get("codex_model", ""))
        if model not in {"gpt-5.4-mini", "gpt-5.6-luna"}:
            continue
        coverage, sufficient, evidence_count = run_health(run_dir)
        if coverage == "failed" or evidence_count == 0:
            continue
        candidates.append(RunSelection(
            run_id=run_dir.name,
            run_dir=run_dir,
            model=model,
            profile="efficient",
            coverage_status=coverage,
            sufficient=sufficient,
            evidence_count=evidence_count,
            comparison=load_json(comparison_path),
        ))
    if not candidates:
        raise RuntimeError(f"No valid Codex efficient run found for {case_id}")
    luna = [item for item in candidates if item.model == "gpt-5.6-luna"]
    return luna[0] if luna else candidates[0]


def unique_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).replace("\\", "/") for item in value if str(item)))


def metrics(comparison: dict[str, object], case_id: str) -> dict[str, float]:
    ranked = unique_strings(comparison.get("retrieved_source_files"))
    verification = load_json(ROOT / "testing" / "codeRepoQA" / "corpus" / "cases" / case_id / "verification.json")
    oracle = verification.get("oracle", {})
    if not isinstance(oracle, dict):
        raise ValueError(f"Case has no Oracle object: {case_id}")
    implementation = unique_strings(oracle.get("implementation_files"))
    supporting = [
        item for item in unique_strings(
            [
                *unique_strings(oracle.get("test_or_validation_files")),
                *unique_strings(oracle.get("documentation_files")),
            ]
        )
        if item not in implementation
    ]
    if not implementation:
        raise ValueError(f"Case has no implementation Oracle: {comparison.get('case_id')}")
    implementation_set = set(implementation)
    supporting_set = set(supporting)
    result: dict[str, float] = {}
    ideal_grades = [2] * len(implementation) + [1] * len(supporting)
    for k in K_VALUES:
        top = ranked[:k]
        hits = sum(item in implementation_set for item in top)
        result[f"p@{k}"] = hits / k
        result[f"r@{k}"] = hits / len(implementation)
        dcg = 0.0
        for index in range(k):
            item = ranked[index] if index < len(ranked) else ""
            grade = 2 if item in implementation_set else 1 if item in supporting_set else 0
            dcg += (2**grade - 1) / math.log2(index + 2)
        idcg = sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal_grades[:k]))
        result[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0
    result["ranked_file_count"] = float(len(ranked))
    return result


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


METRIC_KEYS = tuple(f"{family}@{k}" for family in ("p", "r", "ndcg") for k in K_VALUES)


def aggregate(rows: list[dict[str, object]], system: str) -> dict[str, float]:
    return {key: mean(float(row[system][key]) for row in rows) for key in METRIC_KEYS}


def f(value: float) -> str:
    return f"{value:.3f}"


def metric_tables(rows: list[dict[str, object]], title: str, note: str = "") -> list[str]:
    native = aggregate(rows, "native")
    codex = aggregate(rows, "codex")
    lines = [f"### {title}", ""]
    if note:
        lines.extend([note, ""])
    lines.extend([
        f"Cases: **{len(rows)}**",
        "",
        "| System | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| Native | " + " | ".join(f(native[f"{family}@{k}"]) for family in ("p", "r") for k in K_VALUES) + " |",
        "| Codex | " + " | ".join(f(codex[f"{family}@{k}"]) for family in ("p", "r") for k in K_VALUES) + " |",
        "",
        "| System | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |",
        "| --- | ---: | ---: | ---: | ---: |",
        "| Native | " + " | ".join(f(native[f"ndcg@{k}"]) for k in K_VALUES) + " |",
        "| Codex | " + " | ".join(f(codex[f"ndcg@{k}"]) for k in K_VALUES) + " |",
        "",
    ])
    return lines


def codex_metric_tables(rows: list[dict[str, object]], title: str, note: str = "") -> list[str]:
    codex = aggregate(rows, "codex")
    lines = [f"### {title}", ""]
    if note:
        lines.extend([note, ""])
    lines.extend([
        f"Cases: **{len(rows)}**",
        "",
        "| P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| " + " | ".join(f(codex[f"{family}@{k}"]) for family in ("p", "r") for k in K_VALUES) + " |",
        "",
        "| NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |",
        "| ---: | ---: | ---: | ---: |",
        "| " + " | ".join(f(codex[f"ndcg@{k}"]) for k in K_VALUES) + " |",
        "",
    ])
    return lines


def breakdown_table(rows: list[dict[str, object]], key: str, title: str) -> list[str]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    lines = [f"## {title}", "", "| Group | Cases | Codex models | Native P@5 | Codex P@5 | Native R@5 | Codex R@5 | Native NDCG@5 | Codex NDCG@5 |", "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for group in sorted(grouped):
        items = grouped[group]
        native = aggregate(items, "native")
        codex = aggregate(items, "codex")
        models = Counter(str(item["codex_model"]) for item in items)
        model_text = ", ".join(f"{model}: {count}" for model, count in sorted(models.items()))
        lines.append(
            f"| `{group}` | {len(items)} | {model_text} | {f(native['p@5'])} | {f(codex['p@5'])} | {f(native['r@5'])} | {f(codex['r@5'])} | {f(native['ndcg@5'])} | {f(codex['ndcg@5'])} |"
        )
    lines.append("")
    return lines


def main() -> None:
    manifest = load_json(MANIFEST)
    cases = [
        item for item in manifest["cases"]
        if item.get("group") != "question_usage" and item.get("statistics_partition") in {"development", "final"}
    ]
    if len(cases) != 35:
        raise RuntimeError(f"Expected 35 retrieval cases, found {len(cases)}")
    rows: list[dict[str, object]] = []
    codex_rows: list[dict[str, object]] = []
    missing_native: list[str] = []
    invalid_native_attempts: list[dict[str, object]] = []
    not_started_native: list[str] = []
    for case in cases:
        case_id = str(case["case_id"])
        codex = select_codex(case_id)
        codex_row = {
            "case_id": case_id,
            "category": case["group"],
            "repository": case["repository"],
            "partition": case["statistics_partition"],
            "codex_model": codex.model,
            "codex_profile": codex.profile,
            "codex_run": codex.run_id,
            "codex_coverage": codex.coverage_status,
            "codex_sufficient": codex.sufficient,
            "codex_evidence_count": codex.evidence_count,
        "codex": metrics(codex.comparison, case_id),
        }
        codex_rows.append(codex_row)
        native = select_native(case_id)
        if native is None:
            missing_native.append(case_id)
            attempt = latest_native_attempt(case_id)
            if attempt is None:
                not_started_native.append(case_id)
            else:
                invalid_native_attempts.append(attempt)
            continue
        rows.append({
            "case_id": case_id,
            "category": case["group"],
            "repository": case["repository"],
            "partition": case["statistics_partition"],
            "native_model": native.model,
            "native_run": native.run_id,
            "native_coverage": native.coverage_status,
            "native_sufficient": native.sufficient,
            "native_evidence_count": native.evidence_count,
            "native": metrics(native.comparison, case_id),
            **codex_row,
        })

    historical = [row for row in rows if row["codex_model"] == "gpt-5.4-mini"]
    luna = [row for row in rows if row["codex_model"] == "gpt-5.6-luna"]
    development = [row for row in rows if row["partition"] == "development"]
    final = [row for row in rows if row["partition"] == "final"]
    codex_historical_all = [row for row in codex_rows if row["codex_model"] == "gpt-5.4-mini"]
    codex_luna_all = [row for row in codex_rows if row["codex_model"] == "gpt-5.6-luna"]
    codex_development_all = [row for row in codex_rows if row["partition"] == "development"]
    codex_final_all = [row for row in codex_rows if row["partition"] == "final"]
    if (len(codex_rows), len(codex_historical_all), len(codex_luna_all), len(codex_development_all), len(codex_final_all)) != (35, 21, 14, 28, 7):
        raise RuntimeError("Unexpected full Codex cohort sizes")
    complete = len(rows) == 35
    if complete and (len(historical), len(luna), len(development), len(final)) != (21, 14, 28, 7):
        raise RuntimeError("Unexpected cohort sizes")

    native_status = Counter(str(row["native_coverage"]) for row in rows)
    codex_status = Counter(str(row["codex_coverage"]) for row in rows)
    codex_status_all = Counter(str(row["codex_coverage"]) for row in codex_rows)
    lines = [
        f"# Native Retrieval vs Codex Retrieval — {'35-Case Evaluation' if complete else 'Partial Evaluation'}",
        "",
        "> **Run date:** 2026-08-15  ",
        f"> **Status:** {'completed evaluation; 35 paired retrieval-grounded cases' if complete else f'partial evaluation; {len(rows)}/35 paired cases completed before an external quota stop'}.",
        "",
        "## Executive Summary",
        "",
        f"This campaign currently has one selected valid native run for {len(rows)} cases, using `gpt-5.6-luna`. Additional valid executions do not replace or get averaged with those selections. Codex retrieval is available for all 35 planned cases: 21 reusable historical `efficient` runs made with `gpt-5.4-mini` and 14 new `efficient` runs made with `gpt-5.6-luna`. Only the {len(rows)} cases with a selected native run enter paired metrics in this report.",
        "",
        "Because the Codex model differs across cohorts, any combined table is a **coverage summary**, not a homogeneous single-model Codex benchmark. Model-specific cohorts are reported separately and should be used for configuration-specific conclusions.",
        "",
        "No Codex usage-limit or token-exhaustion event occurred. All 14 requested new Codex runs completed.",
        "",
        *([] if complete else [
            f"After the {len(rows)} valid cases, {sum(item.get('state') == 'invalid_artifact' for item in invalid_native_attempts)} subsequent commands wrote invalid native artifacts with `coverage_status=failed`, primarily because embedding TPM rate limits caused `qdrant_index_sync_failed`. Those artifacts are excluded. Execution then stopped at `microsoft-TypeScript-35468` when the embeddings API returned HTTP 429 `credit_balance_exhausted` (`You have no credits remaining`). The {len(not_started_native)} later native cases were not started. No deterministic or historical native fallback was substituted.",
            "",
            "Invalid or hard-failed native attempts: " + ", ".join(f"`{item['case_id']}`" for item in invalid_native_attempts) + ".",
            "",
            "Native cases not started: " + ", ".join(f"`{case_id}`" for case_id in not_started_native) + ".",
            "",
        ]),
        "## How The Metrics Are Calculated",
        "",
        "The ranking unit is an ordered unique file path. Multiple snippets from the same file count once, at the file's first position.",
        "",
        "- **P@k:** implementation Oracle files found in the first k ranks divided by k. If fewer than k files are returned, empty ranks are nonrelevant.",
        "- **R@k:** implementation Oracle files found in the first k ranks divided by all implementation Oracle files for that case.",
        "- **NDCG@k:** position-sensitive graded ranking quality. Implementation Oracle files have relevance 2, test/validation or documentation Oracle files have relevance 1, and all other files have relevance 0.",
        "",
        "Exactly one valid run per testcase and system enters headline metrics. Failed infrastructure attempts do not count. Extra successful runs are retained separately rather than averaged or selected by score. Testcase scores are macro-averaged and rounded to three decimals only for display.",
        "",
        "## Configuration And Validity",
        "",
        "| Condition | Cases | Model | Profile | Run selection |",
        "| --- | ---: | --- | --- | --- |",
        f"| Native final | {len(rows)} valid paired | `gpt-5.6-luna` | workspace final | First valid run at/after `run-20260815T011600Z` |",
        "| Codex historical | 21 | `gpt-5.4-mini` | `efficient` | Latest valid reusable run |",
        "| Codex current | 14 | `gpt-5.6-luna` | `efficient` | New run from this evaluation |",
        "",
        "Native runs are valid only when infrastructure completed, `coverage_status` is not `failed`, evidence is nonempty, and evaluator comparison artifacts exist. Earlier attempts from this date that failed because Node lacked `node:sqlite` or Qdrant was unavailable are explicitly excluded.",
        "",
        f"Native coverage statuses: {dict(sorted(native_status.items()))}; sufficient: {sum(bool(row['native_sufficient']) for row in rows)}/{len(rows)}.  ",
        f"Codex coverage statuses within the paired subset: {dict(sorted(codex_status.items()))}; sufficient: {sum(bool(row['codex_sufficient']) for row in rows)}/{len(rows)}.  ",
        f"Codex coverage statuses across all 35: {dict(sorted(codex_status_all.items()))}; sufficient: {sum(bool(row['codex_sufficient']) for row in codex_rows)}/35.",
        "",
        "## Aggregate Results",
        "",
    ]
    lines.extend(metric_tables(rows, f"Paired coverage summary — {len(rows)} cases", f"Codex model composition: historical Mini={len(historical)}; current Luna={len(luna)}."))
    if historical:
        lines.extend(metric_tables(historical, f"Historical reusable cohort — paired cases: {len(historical)}", "Paired native final runs versus Codex `gpt-5.4-mini` / `efficient`."))
    if luna:
        lines.extend(metric_tables(luna, f"Current homogeneous cohort — paired cases: {len(luna)}", "Paired native final runs versus Codex `gpt-5.6-luna` / `efficient`."))
    if development:
        development_note = (
            "All 28 planned development cases are included."
            if complete
            else "Only development cases completed before the native stop are included."
        )
        lines.extend(metric_tables(development, f"Development partition — {len(development)} paired cases", development_note))
    if final:
        lines.extend(metric_tables(final, f"Final partition — {len(final)} paired cases", "Both conditions use `gpt-5.6-luna`."))
    codex_only_note = (
        "These supplemental tables show Codex results without the adjacent native columns. The mixed-model total is a coverage summary; use the model-specific cohorts for configuration conclusions."
        if complete
        else "These tables preserve the complete Codex evidence obtained while native pairing is incomplete. They must not be read as a native-versus-Codex comparison."
    )
    lines.extend(["## Codex-Only Results Across All 35 Cases", "", codex_only_note, ""])
    lines.extend(codex_metric_tables(codex_rows, "All Codex cases — mixed-model coverage", "This combines 21 historical Mini and 14 current Luna cases; use the model-specific tables below for configuration conclusions."))
    lines.extend(codex_metric_tables(codex_historical_all, "Historical Codex cohort — 21 cases", "`gpt-5.4-mini` with the `efficient` profile."))
    lines.extend(codex_metric_tables(codex_luna_all, "Current Codex cohort — 14 cases", "`gpt-5.6-luna` with the `efficient` profile."))
    lines.extend(codex_metric_tables(codex_development_all, "Codex development partition — 28 cases", "Mixed-model: 21 Mini and 7 Luna cases."))
    lines.extend(codex_metric_tables(codex_final_all, "Codex final partition — 7 cases", "All seven held-out categories use `gpt-5.6-luna`."))
    lines.extend(breakdown_table(rows, "category", "Category Breakdown At Rank 5"))
    lines.extend(breakdown_table(rows, "repository", "Repository Breakdown At Rank 5"))
    lines.extend([
        "## Per-case Audit At Rank 5",
        "",
        "| Testcase | Selected native run | Partition | Category | Codex model | Native P@5 | Codex P@5 | Native R@5 | Codex R@5 | Native NDCG@5 | Codex NDCG@5 |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in sorted(rows, key=lambda item: (str(item["partition"]), str(item["category"]), str(item["case_id"]))):
        lines.append(
            f"| `{row['case_id']}` | `{row['native_run']}` | {row['partition']} | `{row['category']}` | `{row['codex_model']}` | {f(row['native']['p@5'])} | {f(row['codex']['p@5'])} | {f(row['native']['r@5'])} | {f(row['codex']['r@5'])} | {f(row['native']['ndcg@5'])} | {f(row['codex']['ndcg@5'])} |"
        )
    lines.extend([
        "",
        "## Run Inventory",
        "",
        "| Testcase | Native run | Native status | Codex run | Codex model | Codex status |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for row in sorted(rows, key=lambda item: str(item["case_id"])):
        lines.append(
            f"| `{row['case_id']}` | `{row['native_run']}` | {row['native_coverage']}; sufficient={str(row['native_sufficient']).lower()} | `{row['codex_run']}` | `{row['codex_model']}` | {row['codex_coverage']}; sufficient={str(row['codex_sufficient']).lower()} |"
        )
    lines.extend([
        "",
        "## Interpretation Limits",
        "",
        "- Do not interpret the combined Codex value as one model configuration; use the model-specific cohort tables.",
        *([] if complete else ["- This report is incomplete because native execution stopped on embedding-credit exhaustion; no final-partition native case was reached."]),
        "- The seven-case final set is category-balanced but has one case per category, so category-level final estimates are individually fragile.",
        "- One selected valid run per case/system is used in this report. Extra successful executions—including indexing or diagnostic checks—do not replace the selected run and are not averaged into headline metrics. This does not estimate run-to-run variance.",
        "- Standard P@k penalizes deliberately short lists because missing ranks count as nonrelevant.",
        "- These metrics evaluate frozen file Oracles. Semantically plausible non-Oracle files receive no deterministic credit and should be assessed separately in qualitative error analysis.",
        "",
        "## Reproduction",
        "",
        "This report was generated by `testing/codeRepoQA/generate_retrieval_statistics.py` from the selected runs' `evaluator-comparison.json`, `run-metadata.json`, and `orchestration-result.json` artifacts. Full-precision per-case values and run selections are stored in the adjacent JSON file.",
        "",
        "The governing definitions are in [../RETRIEVAL_STATISTICS_PROTOCOL.md](../RETRIEVAL_STATISTICS_PROTOCOL.md).",
        "",
    ])

    output = {
        "schema_version": 1,
        "report": OUTPUT_STEM,
        "native_run_floor": NATIVE_RUN_FLOOR,
        "planned_case_count": 35,
        "paired_case_count": len(rows),
        "complete": complete,
        "missing_native_cases": missing_native,
        "invalid_native_attempts": invalid_native_attempts,
        "not_started_native_cases": not_started_native,
        "native_stop": None if complete else {"case_id": "microsoft-TypeScript-35468", "error": "HTTP 429 credit_balance_exhausted: You have no credits remaining"},
        "cohorts": {"codex_gpt_5_4_mini": len(historical), "codex_gpt_5_6_luna": len(luna), "development": len(development), "final": len(final)},
        "rows": rows,
        "codex_rows_all_35": codex_rows,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{OUTPUT_STEM}.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / f"{OUTPUT_STEM}.md").write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT_DIR / f"{OUTPUT_STEM}.md")


if __name__ == "__main__":
    main()
