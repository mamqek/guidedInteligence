# CodeRepoQA Explanation Corpus

This directory contains the selected issue corpus for retrieval/explanation evaluation.
It is separate from the large local raw corpora under `vue/`, `TypeScript/`, and
`pandas/`, which stay ignored and excluded from indexing.

## Corpus Shape

- `selection_manifest.json` lists every selected case, its primary group, source
  issue path, and selection rationale.
- `cases.md` is the human-readable grouped table of selected cases and source
  locations.
- `cases/<case_id>/issue.json` is a copied raw issue record. This is the
  immutable source fixture for the case.
- `cases/<case_id>/verification.json` is the evaluator-facing metadata. It
  contains hidden resolution artifacts, oracle fields, and measurement criteria.

The retrieval prompt must only receive the pre-resolution visible fields from
`issue.json`: title, creation time, and body. Comments, events, `fixed_by`,
linked PRs, commit metadata, and verification files are hidden evaluator data.

## Groups

The baseline corpus uses eight groups. The first seven are deterministic
implementation-oriented groups; `question_usage` is included because these cases
can still be evaluated by comparing the generated explanation to maintainer
guidance in the thread.

| Group | Intent | Current Count |
| --- | --- | ---: |
| `bug_regression` | Incorrect behavior, crash, missing behavior, or regression. | 5 |
| `feature_enhancement` | New capability or developer-experience improvement. | 5 |
| `performance_memory` | Runtime, memory, import-time, or filesystem performance. | 5 |
| `compatibility_versioning` | Browser, dependency, platform, or version compatibility. | 5 |
| `api_behavior_design` | Public API behavior, semantics, dtype/type behavior, or consistency. | 5 |
| `testing_build_tooling` | Test discovery, CI, compiler/watch/build tooling, or validation scripts. | 5 |
| `maintenance_refactor` | Cleanup, refactor, documentation maintenance, or internal hygiene. | 5 |
| `question_usage` | User question/support issue with useful maintainer explanation. | 3 |

Each retrieval-grounded group has five selected cases. `question_usage` remains at three and is excluded from ranking statistics.

## Selection Logic

Cases were selected from the local JSON corpora with these filters:

1. Prefer closed issues with a local resolution artifact: `fixed_by`, referenced
   commit events, `cite`, or same-repository `cited_by` links.
2. Prefer issues whose title/body are understandable before the fix, because the
   tool only sees pre-resolution inputs.
3. Prefer issues with enough hidden thread or PR/commit signal to build a later
   oracle for retrieval file overlap and explanation correctness.
4. Prefer diversity across Vue, TypeScript, and pandas where that does not lower
   quality.
5. Avoid duplicates, vague meta-tracking issues, and cases whose resolution is
   mostly social/process-only.

The selected raw issue JSON often stores `fixed_by` as a PR number, not a commit
SHA. `verification.json` records those PR numbers, event commits, and, where a
`fixed_by` PR exists, GitHub PR metadata and changed files.

## Verification Schema

Each `verification.json` has these evaluator-facing fields:

- `visible_prompt_policy`: fields allowed in the prompt and hidden fields that
  must not leak into retrieval.
- `resolution_artifacts`: local issue-thread links to PRs, commits, citations,
  and resolution status.
- `oracle.implementation_files`: production files that should be retrievable.
- `oracle.test_or_validation_files`: test, benchmark, CI, or validation files.
- `oracle.documentation_files`: docs/changelog files relevant to the fix.
- `oracle.symbols_or_apis`: APIs, symbols, commands, or concepts the explanation
  should mention.
- `oracle.subsystem`: expected subsystem label.
- `oracle.responsibility_summary`: what the relevant code is responsible for.
- `oracle.hidden_resolution_summary`: post-resolution truth used for evaluator
  comparison, never for retrieval.
- `oracle.issue_body_file_refs` and `oracle.thread_file_refs`: raw file-like
  references extracted from the visible issue body and hidden thread.

Most implementation-oriented cases have PR-derived oracle file lists. The
`question_usage` cases use explanation-thread oracles instead, so their
implementation-file overlap metric is secondary or not applicable.

## Measurement Contract

The evaluator should not run the project tests as the main success signal. This
tool explains and retrieves; it does not patch the target codebase.

The planned scoring table for each case should measure:

- Retrieval found at least one oracle implementation file.
- Relevant oracle files appear within top `k`, initially `k = 5, 10, 20`.
- Explanation identifies the correct subsystem and responsibility.
- Explanation agrees with the hidden resolution summary.
- Claims cite pre-resolution evidence.
- No post-resolution information leaked into retrieval or explanation.

For `question_usage`, implementation-file overlap may be secondary or absent.
Those cases should emphasize subsystem/responsibility agreement, hidden
resolution agreement, and citation/leakage checks.

## Later Automation

The intended later wiring is compatible with the existing `testing/codeRepoQA`
harness:

1. Load `selection_manifest.json`.
2. Materialize or reuse a pre-resolution repository snapshot for each case.
3. Build the retrieval index from that snapshot only.
4. Run the tool with the visible issue fields.
5. Compare retrieved evidence and explanation output against
   `verification.json`.
6. Reject any run that cites hidden comments, PR bodies, commit diffs, or files
   unavailable before the issue creation/pre-resolution snapshot.

The current corpus is ready for later harness wiring, with one caveat: the
PR-derived oracle lists should still be manually reviewed for noisy multi-issue
PRs before strict paper-grade scoring.
