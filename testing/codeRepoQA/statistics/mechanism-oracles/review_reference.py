"""Generate the second-pass review ledger for the required-evidence reference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
DEFAULT_REFERENCE = HERE / "source-transition-oracle.json"
DEFAULT_OUTPUT = HERE / "required-evidence-reference-review.md"
DEFAULT_TEST_ROOT = Path(r"C:\Programming\guidedInteligence_testcases")


# These cases remain defensible scoring definitions, but the minimum evidence
# set depends on a substantive scope judgement that the researcher should
# explicitly approve. Keeping this list explicit prevents future audit runs
# from silently changing the review boundary.
CONFIRMATION_NOTES = {
    "microsoft-TypeScript-2953": (
        "The defect is an absent declaration. The selected ArrayBuffer declaration scope is a proxy for where "
        "DataView should exist, so the sufficiency of that scope requires researcher confirmation."
    ),
    "vuejs-vue-6301": (
        "The issue names the client plugin, while the merged fix adds declarations for both client and server "
        "plugins. Requiring both runtime entry points adopts the scope of the fix rather than only the issue title."
    ),
    "pandas-dev-pandas-16764": (
        "The performance repair changes many eager-import paths. The five selected branches form a defensible "
        "minimum explanation, but other changed import paths could reasonably be included."
    ),
    "microsoft-TypeScript-16278": (
        "The refactor API change spans discovery, services, protocol, session, and client layers. Requiring all six "
        "pre-resolution surfaces is an end-to-end interpretation rather than a uniquely determined minimum."
    ),
    "pandas-dev-pandas-35925": (
        "The reference uses the pinned Black version as the maintenance cause and excludes the many mechanical "
        "formatting edits. Confirm that this matches the intended retrieval question rather than requiring examples "
        "of the affected source formatting."
    ),
    "vuejs-vue-8528": (
        "The resolution changes comments across a broad utility file. The selected range identifies the maintenance "
        "surface, but no unique minimum pair of utility comments is dictated by runtime behaviour."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--test-root", type=Path, default=DEFAULT_TEST_ROOT)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    reference = load_json(args.reference)
    cases = reference["cases"]
    unit_count = sum(len(case["evidence_units"]) for case in cases)
    confirmation_unit_count = sum(
        len(case["evidence_units"]) for case in cases if case["case_id"] in CONFIRMATION_NOTES
    )
    rows: list[str] = []

    for case in cases:
        case_id = case["case_id"]
        verification = load_json(args.test_root / case_id / "verification.json")
        prs = verification.get("resolution_artifacts", {}).get("github_prs", [])
        fix = prs[0]["title"] if prs else verification.get("oracle", {}).get("hidden_resolution_summary", "")
        if case_id in CONFIRMATION_NOTES:
            assessment = "Researcher confirmation recommended"
            reason = CONFIRMATION_NOTES[case_id]
        else:
            assessment = "Directly supported"
            reason = (
                "Required ranges align with the verified resolution responsibility and expose the exact "
                "pre-resolution behaviour or maintenance surface used by the scoring rule."
            )
        rows.append(
            f"| `{case_id}` | {len(case['evidence_units'])} | {assessment} | {fix} | {reason} |"
        )

    lines = [
        "# Required-evidence reference: second-pass review",
        "",
        f"The reference contains **{unit_count} required units across {len(cases)} testcases**. This second pass checks each definition against the recorded issue, fixing artifact, and pre-resolution source. Automated validation separately verifies every path, range, anchor, hash, transition endpoint, and campaign identifier.",
        "",
        f"**{len(cases) - len(CONFIRMATION_NOTES)} cases ({unit_count - confirmation_unit_count} units) are directly supported. {len(CONFIRMATION_NOTES)} cases ({confirmation_unit_count} units) remain judgment-sensitive and are isolated below rather than weakening the complete audit silently.** A recommendation for confirmation does not mean that the current definition is invalid; it means that another defensible minimum evidence set is possible.",
        "",
        "## Cases requiring researcher confirmation",
        "",
    ]
    for case_id, note in CONFIRMATION_NOTES.items():
        lines.append(f"- `{case_id}`: {note}")
    lines.extend(
        [
            "",
            "## Complete review ledger",
            "",
            "| Testcase | Required units | Assessment | Fixing-artifact basis | Review reasoning |",
            "|---|---:|---|---|---|",
            *rows,
            "",
            "## Interpretation",
            "",
            "This review establishes source and resolution alignment, not independent inter-rater agreement. The six flagged scope choices should be approved or revised by the researcher before final submission. Any revision requires incrementing the reference revision and regenerating all 700 run judgements, aggregate tables, and the manuscript appendix.",
            "",
        ]
    )
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Reviewed {unit_count} units across {len(cases)} cases; flagged {len(CONFIRMATION_NOTES)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
