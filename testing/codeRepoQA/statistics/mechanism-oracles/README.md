# Required-evidence reference

This directory contains the fixed, pre-resolution required-evidence reference
used for snippet-level analysis of the final September CodeRepoQA campaign. The definitions
are separate from the thesis manuscript and from run outputs so that later
scoring can be repeated without redefining the expected mechanism.

## Authority and scope

Each case is defined from two sources:

1. the fixing pull request or commit recorded in the testcase's `verification.json`; and
2. source as it exists in the testcase's pre-resolution snapshot under
   `<test-root>/<case>/s/<snapshot>/`.

Post-resolution pull-request patches may identify the responsibility that was
changed, but post-resolution text is never copied into the required-evidence reference and
must never be scored as retrieved evidence.

The campaign inventory is
`testing/codeRepoQA/statistics/runs/2026-09-16-five-mode-four-runs.json`.
Curated definitions live in `build_oracle.py`; it generates the canonical
`source-transition-oracle.json` and the human-readable review document.  Do
not edit either generated file directly.

## Data model

Every case records:

- `mechanism_summary`: the behavior or maintenance outcome that retrieved
  evidence must explain;
- `oracle_kind`: whether the case concerns a causal code path, an API or type
  surface, configuration, documentation, or scoped absence;
- `evidence_units`: exact pre-resolution ranges that expose individual steps;
- `connected_required_evidence`: whether two or more required snippets are
  connected by a source-level call, state, data, or configuration path;
- `transitions`: descriptions used to justify that case classification rather
  than a separate run-level score;
- `required_file_count`: the number of distinct files containing required
  pre-resolution evidence; and
- `completeness_rule`: the rule later run scoring must apply.

An evidence unit is not satisfied merely because its file is selected.  The
selected snippet must expose the behaviour-bearing anchors and responsibility
described by the unit. When several anchors are present, a leading declaration
may identify the symbol without becoming an additional behavioural
requirement; all remaining anchors must still be exposed. Connections classify
cases for aggregate comparison; retrieval is not required to label a
relationship explicitly.

`scoped_absence` units are used only when the pre-resolution defect is the
absence of a declaration, entry point, or configuration.  They require enough
selected context to establish the relevant scope; a nearby snippet is not
automatically proof of absence.

## Workflow and versioning

1. Curate or revise the case definitions in `build_oracle.py` using only the
   hidden resolution metadata and the pre-resolution snapshot.
2. Run `python testing/codeRepoQA/statistics/mechanism-oracles/build_oracle.py`
   to regenerate both deliverables.
3. Run `python testing/codeRepoQA/statistics/mechanism-oracles/validate_oracle.py`
   to verify campaign membership, snapshot paths, ranges, anchors, and IDs.
4. Freeze a reviewed Oracle by changing its review status and recording the
   JSON file's SHA-256 in the subsequent scoring
   output.
5. Score all selected-evidence artifacts against that frozen version.  Store
   run-level judgements separately; never add outcome-dependent exceptions to
   this Oracle.
6. If an Oracle changes, increment `oracle_revision`, state the reason, and
   rerun every affected score.

Run the complete audit with:

```powershell
python testing/codeRepoQA/statistics/mechanism-oracles/build_oracle.py
python testing/codeRepoQA/statistics/mechanism-oracles/validate_oracle.py
python testing/codeRepoQA/statistics/mechanism-oracles/review_reference.py
python testing/codeRepoQA/statistics/mechanism-oracles/score_runs.py
```

The scorer writes three generated artifacts:

- `corpus-required-evidence-audit.json`, the authoritative 700-run result;
- `corpus-required-evidence-audit.md`, the compact aggregate report; and
- `appendix-required-evidence-audit.md`, the complete 35-case run ledger.

`required-evidence-reference-review.md` records the second-pass resolution and
source review and isolates definitions that still require an explicit
researcher scope decision.

The standardised *initial comparison* boundary is the reduction from prepared
ranges or structural owners to round-zero snippets admitted for qualification.
The run ledger also records the total number of files returned by final
selection, the number of required-evidence files represented, and the number
of implementation-Oracle files represented. These counts distinguish a result
set that is too small to contain the reference from one that has sufficient
capacity but selects the wrong files or incomplete ranges.

The readable `source-transition-oracle.md` is generated from the same JSON and
is intended for human review.  The JSON remains authoritative.
