# Retrieval handoff: qualification retention and owner-comparison source

Updated: 2026-08-27. Status: investigation and future experiment plan; no new retrieval implementation or runs in this handoff turn.

Follow-up authorization and execution: [positive proof / owner bodies / island audit](positive-proof-owner-body-island-experiments.md).
The no-implementation instructions below describe the original handoff turn; the linked execution ledger records
the user's subsequent authorization and is the current status source.

## 1. Read this before continuing

The latest user request is to answer questions and prepare a substantial handoff, **not to start implementations or experiments**. The user wants to move the work to another chat.

Three issues must remain separate:

1. Why qualified direct evidence can miss the final-selection input budget.
2. Whether qualification should reuse all unchanged judgments, as implemented, or specifically preserve previously established direct evidence, as newly proposed.
3. How to disclose useful owner body source **before owner comparison**, without grouping separate owners into larger evidence regions.

The user wants to try both targeted body repair and consistent bounded owner cards later. Their preferred representation includes the signature and a window around the original retrieved focus, with an explicit gap if those portions are far apart. No implementation of either exists yet.

### Workspace checkpoint

- Repository: `C:/Programming/guidedInteligence`.
- Branch: `codex/dormant-island-reconnection`.
- HEAD at handoff: `c6a40a60d83b5e8fec78b27f95646cd1a225ea7c`.
- The worktree contains substantial earlier tracked and untracked changes. **HEAD alone does not reproduce the measured current implementation.**
- The qualification cache and optional completion budget remain provisionally applied. The latest combined pair was not accepted as a stable overall-quality improvement.
- No commit, checkout, broad revert, new branch, new indexing, or new pipeline run was performed for this handoff.
- Preserve unrelated changes, including Codex corpus statistics. Do not apply archived experiment patches as if they were the current baseline. Do not restore entire dirty files from HEAD to switch an experiment.

Read the [incremental experiment protocol](../incremental-experiment-execution-protocol.md) and [open questions registry](retrieval-experiment-open-questions.md) before implementation. Detailed measurements belong in the [retrieval changelog](../retrieval-changelog.md); this document is the navigation and experiment handoff.

## 2. Current stages and terminology

The native pipeline is not an entirely deterministic retriever: it uses LLM-backed owner comparison, qualification, coverage and final selection. Its current controller scheduling is typed/deterministic, not the previously attempted LLM action planner.

The relevant sequence is:

1. Request analysis and per-obligation Qdrant retrieval.
2. Range deduplication, structural owner resolution and canonical snippet construction.
3. Ranked complete-file admission into the owner-comparison input; comparison sees compact owner views.
4. Grouped owner comparison selects owners for source disclosure; alternatives receive their lifecycle disposition.
5. Source disclosure and **round-zero qualification**, which produces actual semantic support judgments.
6. Coverage, bounded controller discovery, source disclosure and qualification of later snippets; run-local qualification reuse applies here and at round zero through the same stage contract.
7. Final candidate pool, deterministic mechanism-flow construction/ranking/budget admission, then final LLM evidence selection.

Initial retrieval and owner comparison are **not semantic qualification**. A retrieval association, anchor or owner-selection decision is not a `QualificationDecision` marking direct evidence. Round-zero qualification is a real qualification call, not the pre-qualification stages.

Use “snippet” in explanations. Code still uses `observation` in some contracts. Structural identity, visible source and semantic judgment are separate: resolving an owner does not guarantee that its body was shown.

## 3. Final input ranking: direct support helps, but does not reserve space

Implementation: `services/retrieval/workspace/pipeline/execution_flow/obligation_retrieval.py`, `_select_mechanism_flows` (line 2596 at handoff), `node_score` (2714), `root_hypothesis_score` (2984), dynamic ordering (3039).

The selected units are mechanism flows: connected snippet groups, including singleton flows. Direct snippets receive singleton hypotheses, but this does not guarantee admission. The algorithm re-ranks after each admitted flow.

The primary ordering is descending:

```text
root_hypothesis_score
  + 30 if the flow shares an already selected candidate
  + 20 if connected through source-path provenance
  + 15 if it has protected responsibility terms
```

Ties use flow score, connection count, candidate count and deterministic root ID. These bonuses are cumulative. There is no lexicographic “direct evidence before every navigation snippet” rule.

```text
node_score =
    6 * direct-supported obligation count
  + inherited-supported obligation count
  + provenance tier
  + 1 if structurally identified
  + 2 * matched request-term count
  + 4 if state_owner
  + 5 if domain_owner
  + 2 if controller
  - 2 if observer
  - 4 if generic_utility
  + candidate score clamped to [0, 3]

root_hypothesis_score =
    node_score
  + 10 * direct-supported obligation count
  + 4 * covered-concept count
  - 8 if generic_utility
  - 2 if observer
```

Flow score is a separate, secondary ordering term. Role classification and connectivity are heuristics, not fresh semantic judgments about which snippet best explains the issue.

### Exact watchMode loss: run-20260827T153303Z

Trace: [retrieval-trace.jsonl](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T153303Z/retrieval-trace.jsonl:2308). Line 2308 contains the flow decision ledger; 2310 contains the budget summary; 2311 is the literal final request; 2312 is its response.

| Property | Excluded test | Last admitted flow root |
|---|---|---|
| Owner | `watchMode.ts::introduceError` | `Project::onInvalidatedResolution` |
| Qualification | Direct evidence | Direct evidence |
| Supported obligation | `explain_trigger` | `explain_trigger` |
| Node score | 11.7 | 18.7 |
| Root score | 21.7 | 28.7 |
| Relevant roles | `validation` | `state_owner`, `domain_owner` |
| Connectivity boost for this comparison | None | None |

The test's source is lines 504–508, **266 characters**, not a large test body. Its root score is derived from the logged node score: `11.7 + 10 * 1 = 21.7`. The Project root similarly scores `18.7 + 10 = 28.7`. Its role bonuses add nine points; one fewer matched request term subtracts two relative to the test, explaining the seven-point difference.

The crossing flow, `mechanism_flow_16`, added 1,581 accounted characters. Used flow-input space went from **43,788 to 45,369**, crossing the 45,000 threshold. The complete crossing flow stayed; later flows, including `introduceError`, were marked `rejected_after_input_budget_crossing`.

**All 16 admitted flow roots in this run were already qualified direct evidence.** Therefore a simple direct-first root ordering would not fix this particular loss. The issue is prioritization among direct flows and the input boundary, not merely navigation evidence taking all direct-evidence space.

This happens after controller discovery, while constructing the final LLM input. It is not the qualification-card budget. The configured final input is 50,000 characters; flow construction receives 45,000 after its 5,000-character reserve. Eligible explicit connections between retained endpoints are preserved by the earlier correction.

Potential later investigation: compare heuristic role/connectivity preference with distinct, visibly supported issue claims. Do not implement a new ranking rule or reserve a test slot in the body-disclosure experiment. Direct evidence can still be redundant or peripheral; direct classification alone does not establish that every such snippet must fit.

## 4. Current qualification cache versus the user's proposed protection

Implementation: `evidence_qualification.py`, `QualificationReuseCache` (47), with a run-local instance supplied by `retrieval_controller.py`. `qualification_first_retrieval.py` (686) assigns `qualified_direct_evidence` from a real qualification decision, not initial retrieval relevance.

### Implemented behavior

- Cache validated actual LLM judgments by snippet ID plus a semantic-input fingerprint.
- Reuse **all classifications**, including direct, navigation, insufficient and rejected judgments.
- Compare exact budget-fitted visible source, path/owner, disclosure mode/completeness and source identity/bounds, request, obligation definitions, artifact role and prompt/model context.
- Ignore retrieval recurrence, rank and query provenance as reasons to requalify. Resolve batch aliases before hashing.
- Ignore a moved retrieved focus when the card is full-mode and the full owner bounds and visible source are unchanged. A changed preview location still matters.
- Fit the existing batch first. Remove cache hits from the LLM request without redistributing their saved capacity to other cards.
- New semantic input causes a new LLM judgment and can downgrade a formerly direct snippet. This is **not an “ever direct” latch**.
- Cached judgments are reapplied with current candidate/provenance metadata. Hidden LLM continuity disables reuse because unrepresented conversation context would undermine the key.

### Proposed behavior and its difference

| Situation | Current cache | User's proposed positive protection |
|---|---|---|
| Same source/context, previously direct | Reuse direct judgment | Keep direct judgment |
| Same source/context, previously weak/rejected | Reuse weak judgment | Not protected by the positive-only rule; reconsideration policy still needed |
| Changed or shorter source view | Requalify; previous direct judgment can be replaced | Preserve previously established direct evidence |
| Initial retrieval/owner comparison relevance | No qualification judgment to cache | Still open to first qualification |
| Contradictory evidence or changed request/source | Requalify | An absolute never-downgrade rule would be unsafe |

The proposed rule is narrower about **which judgments** it protects, but potentially stronger about **how long** positive support survives. It is not the same as the current unchanged-input cache.

Recommended formulation for discussion, not yet implementation: retain the previously qualified **source view and its supported obligations** when rediscovery or a poorer crop would otherwise erase that proof. A new incomplete view must not inherit proof it does not show. Actual contradictory evidence, source revision or changed request must permit correction. Do not protect an entire file because one snippet was direct, and do not inherit support for every obligation.

Retaining proof and displaying it also need an explicit source-allocation policy: do not silently combine old and new bodies without accounting for their character cost. A prior positive can be mistaken, so unconditional permanent immunity would accumulate false positives.

If “pre-qualification” means initial retrieval/owner comparison, the requested distinction already holds. If it means round-zero qualification, excluding that round would be a separate new policy; round zero currently has the same semantic qualification contract as later rounds.

The current cache can preserve an erroneous first negative. Repeatedly asking the same question until a positive appears is not an acceptable substitute. Any reconsideration of unchanged weak judgments needs an explicit, bounded reason and a separately evaluated policy.

## 5. Recent implementation and experiment ledger

Detailed record: [qualification reuse and completion budget](qualification-reuse-and-completion-budget-experiment.md). All runs below are native TypeScript retrieval with explanation generation skipped and final selection enabled, except the explicitly failed invocation. Existing indexes were reused.

| Configuration | Run ID | Coverage / sufficient | Implementation Oracle files | Retrieval tokens | Notes |
|---|---|---|---:|---:|---|
| Baseline before reuse/uncapping | `run-20260827T142925Z` | partial / false | 3/4 | 113,718 | 14 final items, five files |
| Same baseline | `run-20260827T142935Z` | partial / false | 3/4 | 97,572 | 12 items, seven files |
| Reuse attempt 1 + optional cap | `run-20260827T152348Z` | partial / false | 3/4 | 102,630 | Two reused judgments |
| Same attempt | `run-20260827T152358Z` | partial / false | 3/4 | 107,688 | No hits; moved full-body focus caused an unnecessary miss |
| Reuse attempt 2 + optional cap | `run-20260827T153020Z` | Failed before qualification | Not a final result | 25,314 | Owner comparison assigned o145 to g12 instead of g13; unchanged validator rejected it |
| Same attempt, completed | `run-20260827T153030Z` | partial / false | 3/4 | 108,312 | Two hits; 14 items, six files |
| Same attempt, completed | `run-20260827T153303Z` | partial / false | 1/4 | 112,242 | Four hits; 11 items, five files |

The final pair totals **220,554** versus baseline **211,290** tokens, +9,264 (+4.4%). Qualification totals were 66,730 versus 67,109; coverage 65,000 versus 57,339; final selection 37,362 versus 33,688. The weaker run used the existing fourth-round extension; no round limit was changed. Upstream inventories differed, so these are measured outcomes, not an isolated causal estimate of cache or completion-cap cost.

The four implementation Oracle paths used by this benchmark's scoring are `src/compiler/builder.ts`, `src/compiler/builderState.ts`, `src/testRunner/unittests/tsbuild/watchMode.ts`, and `src/testRunner/unittests/tscWatch/helpers.ts`. This is evaluation-only information, never input to query construction, admission or ranking.

### What changed mechanically

- Qualification reuse prevents identical-view reclassification, including the previously observed 331-character `getReferencedByPaths` body switching from direct in round 2 to navigation in round 3 (`run-20260827T124548Z`, trace 915 versus 1342).
- Attempt 2 also handles identical full-body cards whose original retrieval focus moved. It does not ignore meaningful source changes.
- The blanket 4,000-completion-token generation restriction is omitted when the configured value is null. Explicit numeric limits remain supported. Schema validation, retries, timeouts and usage tracing remain; provider/model limits still apply.
- Source/input budgets were not removed. In particular, qualification's 4,000-character card limit is not a completion-token limit.
- Owner-body acquisition and the compact owner-comparison renderer were **not** changed by these repairs.

### Saved-input evidence

- `testing/codeRepoQA/qualified-file-lead-replays/qualification-reuse-1.json` and `qualification-reuse-2.json`: identical recorded-judgment audits, three reusable judgments among 35. They preserve the direct helper but also preserve earlier weak judgments. These are not new LLM decisions or full acceptance runs.
- `qualification-reuse-v2-1.json` and `qualification-reuse-v2-2.json`: repeated moved-full-focus audit.
- `uncapped-final-1.jsonl` and `uncapped-final-2.jsonl`: two real LLM calls using the saved failed final input from `run-20260827T131714Z`, changing only omission of `max_completion_tokens`. Both returned valid selections with `finish_reason=stop`, using 3,967 and 4,574 completion tokens. The first fits the former cap, so its success cannot be attributed solely to additional headroom.
- Original failed final calls in `run-20260827T131714Z` and `run-20260827T131856Z` exhausted 4,000 reasoning tokens and returned empty output, including retries.
- Consolidated live audit: `testing/codeRepoQA/qualified-file-lead-replays/qualification-reuse-final-acceptance.json`.
- All five actual invocations cost 456,186 tokens; isolated real final replays add 36,655; total measured verification cost 492,841. Previously completed verification: 264 focused Python tests and UI build passed; 13 existing UI type errors were also present in the HEAD-file comparison. No tests were rerun to create this handoff.

### Exact losses in the weaker final run

All references in this paragraph are to `run-20260827T153303Z/retrieval-trace.jsonl` under the TypeScript case's runs directory.

- Raw dense/sparse results: lines 20/25/30/35/40/45; range resolution 51; canonical pool 52; file admission 53. Both `builderState.ts` and `watchMode.ts` were retrieved, resolved and admitted. Do not describe either as absent from retrieval.
- `builderState.ts`: four canonical snippets; three selected by comparison (58/60). `updateShapeSignature` was navigation-only at its first qualification (112), not subsequently downgraded by reuse. `updateSignaturesFromCache` and `updateExportedFilesMapFromCache` were direct, reached the final candidate pool (2306) and literal final LLM input (2311), but were not selected (2312). There is no explicit model rejection reason for each omitted item; do not invent one.
- `watchMode.ts`: 38 canonical snippets, four selected by comparison. `introduceError` was direct and later reused as direct (566). Other selected test views were insufficient, navigation-only or rejected. The surviving direct test reached the final pool, then missed the flow budget (2308), as detailed above. It was not rejected by the final LLM because its source was not sent.
- Controller actions investigated watchMode, watchers, tsbuild, watchPublic and verified leads. They did not qualify a fuller `updateShapeSignature` view. Reuse also preserved other candidates, so indirect effects on scheduling or competition are not ruled out by showing that these missing snippets were not downgraded.

Conclusion: the completion repair has focused response-reliability evidence; reuse has consistency evidence. **Neither establishes a stable overall retrieval-quality improvement.** Both remain provisionally applied for user review, not silently accepted or reverted.

## 6. Earlier relevant decisions: retained, rejected, pending

This is a navigation index, not a claim that every historical experiment is newly re-audited here.

| Area | Recorded disposition / relevance | Detailed record |
|---|---|---|
| Grouped global owner comparison | Retained; file groups contain distinct owner candidates | [Grouped selection](grouped-initial-owner-selection-experiment.md) |
| Larger evidence regions | Rejected experiment; not part of the proposed body repair | [Region experiment](initial-evidence-region-experiment.md) |
| Owner shortlist | Tested and reverted; do not add a ten-owner cap during body repair | [Shortlist](owner-comparison-shortlist-experiment.md) |
| Conceptual query stabilization | Retained baseline; keep fixed during body tests | [Concept stability](request-analysis-concept-stability-experiment.md) |
| Semantic obligation support | Qualified visible support replaces copied retrieval associations; only known request obligations are eligible | [Obligation scope](../qualification-obligation-scope-experiment.md) |
| Structural memoization and pre-slot novelty | Retained; do not bypass during later discovery | [Controller reliability](controller-discovery-reliability-experiment-plan.md) |
| Assignment-defined owners | Retained; language-routed source-owner identities and callable inspection matter to body cards | [AST recovery](ast-owner-recovery-compatibility.md) |
| Broadened deferred recovery / dynamic callable registration | Earlier rejected experiments; not automatically active because code/docs mention them | [Controller reliability](controller-discovery-reliability-experiment-plan.md) |
| Qualified structural file leads | Reapplied with scheduler integration; exact target hints do not inherit semantic support | [File leads](qualified-structural-file-lead-experiment.md) |
| Qualified connected helpers in final flows | Provisionally retained exception to the no-new-causal-role filter | [Helper and packing experiments](helper-flow-and-file-packing-experiments.md) |
| Skip oversized files and continue | Rejected; replaced by append-crossing ranked-prefix admission | [Append crossing](append-crossing-input-budget-experiment.md) |
| Explicit final connections after crossing | Earlier accidental omission corrected; preserve this behavior | [Append crossing](append-crossing-input-budget-experiment.md) |
| Completeness-driven agent inspection | Previous experiment reverted; old temporary-source plan is not an active implementation recipe | `../temporary-source-visibility-and-agent-inspection-plan.md` |
| Preserve uncovered retrieved source / branch-contrast state | Deferred ideas; not included in owner-body repair | [Controller reliability](controller-discovery-reliability-experiment-plan.md) |

Open-question mapping: IOC-1 for owner comparison scale/source quality and group contract failures; QFL-1 for structural lead and final survival; QOS-1 for qualification support; FPK-1 for packing/final input; HAP-1 for prior agent-planner history.

## 7. Owner-body failure to repair

Pandas `run-20260827T125119Z`, comparison input trace 65:

```text
Qdrant range:       1434–1473
resolved _binop:    1466–1511
current view:      1466–1473 (intersection)
comparison text:   compacted to a signature-only preview
```

`discovery_observations.py` intersects the raw retrieved range with the owner range and slices the already available text. It does not fetch the missing body. `initial_owner_comparison.py::_compact_source_view` (481) then selects a tiny preview, with an 80-character target rather than a useful-body guarantee. Full owner disclosure occurs after comparison, too late for rejected owners.

Both boundaries matter: acquiring body text without changing the renderer can still produce the same signature-only request. Conversely, expanding the renderer cannot display body text that was never fetched.

A minimum string length is not a sufficient fix: docstrings, comments and long signatures can satisfy it. One-line executable owners are legitimate and must not be rejected simply for being short. This experiment changes representation, not owner identity or evidence qualification.

## 8. Proposed common bounded owner-card contract

This section defines the intended shared representation for later A/B experiments; numerical per-card budget is **not decided yet**.

- One existing canonical owner remains one candidate. No sibling clusters, enclosing-owner replacement or evidence regions.
- Complete small owners when they fit the chosen card budget.
- Large owners: signature plus a bounded body window centered on the original owner-aligned retrieved focus.
- If signature and focus cannot fit as one consecutive range, use two explicitly line-labelled segments and an omission marker. Do not spend the budget filling the intervening gap or pretend the segments are adjacent.
- If the retrieved focus is only a signature/docstring, choose an actual body window using the language-routed adapter. The original retrieval range stays in provenance; newly read body source is not falsely labelled as a Qdrant hit.
- Preserve complete source lines when possible, distinguish partial blocks and truncation, deduplicate overlapping segments, and prevent crossing into unrelated owners. Long signatures and single lines exceeding the budget need an explicit tested clipping policy.
- Multiple retrieved focuses for one owner need a deterministic bounded window policy. Record omitted focuses instead of silently creating new candidates.
- Use existing language routing and source-owner support for JavaScript/TypeScript and Python. Do not substitute a universal regex for body recognition. Unavailable or unsupported source must be explicit, not silently replaced by fabricated body text.
- Reuse file reads within the run and validate source against the indexed snapshot.
- Admission cost must be computed from **the same rendered cards that the LLM receives**, including signatures, gaps, ranges and metadata. Do not admit using 80-character estimates then inflate the request afterwards.
- Acquisition and rendering belong to the owner-comparison stage or a cohesive source-card module, not a new body-selection algorithm embedded in controller orchestration.

Illustrative layout, not repository evidence:

```text
Owner signature [lines S–T]
<signature source>

... lines T+1–U-1 omitted ...

Retrieved-focus body window [lines U–V]
<body source>
```

Use concrete numeric line ranges in actual cards. A single contiguous view needs no artificial gap. Character budget includes both segments and presentation overhead.

## 9. Experiment sequence for the next chat

### Step 0 — Freeze the baseline and qualification-policy decision

Inspect the dirty worktree and this ledger before editing. Confirm whether to use the currently provisional unchanged-input cache as the fixed baseline, or first test a separately specified positive-proof-retention policy. Do not change qualification policy halfway through body-card comparisons.

If positive-proof retention is authorized, evaluate it as its own step: source/obligation-specific proof, changed-focus handling, actual contradiction invalidation, weak-judgment reconsideration rules and explicit trace reasons. Compare against the current cache on the same saved inputs before actual acceptance runs. A permanent file-level “once direct, always direct” rule is not the proposed implementation.

No final-flow ranking adjustment, query change, owner-count limit or budget increase is bundled into this step or the following body experiments.

### Step 1 — Characterize existing literal owner views and choose a fixed budget

Use saved Pandas and TypeScript canonical pools and comparison payloads. Measure signature-only/docstring-only views, body-bearing views, source characters, group sizes and total exact serialization cost. Inspect `_binop` and both useful and noisy TypeScript examples; do not optimize runtime logic for those names or hidden Oracles.

Choose a justified reusable per-card budget from these measurements before paid calls. Log the value and compare both variants under the same budget and unchanged global admission settings. Existing input thresholds remain fixed; larger cards can change which files fit and that is part of the measured tradeoff.

### Step 2 — Variant A: targeted body repair

Repair only views that otherwise expose declaration/documentation without useful body source. Keep other views unchanged. Preserve the repaired body in the renderer.

Expected benefit: remove the most severe signature-only failures with limited payload growth. Risk: a nonempty but uninformative body fragment passes the detector and remains inadequate. Detecting syntax is not deciding semantic relevance.

Focused tests and repeated saved-input boundary runs come first. Inspect literal rendered source, selection changes and group attribution before full acceptance. Then two actual TypeScript runs, explanation skipped, final selection enabled. Keep a Pandas saved-input `_binop` check as essential cross-language evidence; any additional live Pandas run is separately recorded, not substituted for the TypeScript pair.

### Step 3 — Variant B: consistent bounded owner cards

Compare against **the same frozen pre-body-repair baseline**, not merely A plus another change. Use the common signature/focus/body contract for all resolved owners.

Expected benefit: consistent representation, including incomplete but nonempty views missed by A. Risk: more characters and source reads; fewer admitted files; generic bodies could dilute relevant local focus. Do not automatically admit a repaired owner or assign it semantic support.

Repeat the same focused fixtures and saved-input comparisons, then two actual TypeScript acceptance runs. If neither variant is stable, report failure rather than changing unrelated ranks or increasing budgets to force a good result.

### Step 4 — Compare, inspect and stop for a decision

Compare A, B and the frozen baseline at each boundary. Prefer measured useful body visibility and semantic selection, not merely more bytes or a lucky Oracle score. Record all failed invocations and retries. For questionable tradeoffs, explain them to the user before reverting, as requested. Do not proceed automatically to final-flow ranking, residual-source preservation, hierarchical comparison or a new agent planner.

Use at most three implementation variants per independently testable step. Fix mechanical defects before paid runs; do not keep rerunning a sound variant until favorable final results appear.

## 10. Required tests, measurements and attribution

Focused fixtures:

- Small complete owner; large late-focus owner; signature far from focus; docstring-only hit; executable one-line owner.
- Long signature or single over-budget line; nested/sibling owners; multiple hits for one owner; duplicate/overlapping segments.
- JavaScript/TypeScript assignment-defined source owners and Python owners; source unavailable; unresolved ranges.
- Stable canonical IDs and original retrieval provenance; exact serialization cost; no hidden 80-character re-compaction.
- For any qualification-policy experiment: unchanged positives/negatives, poorer later crop, genuine new body, changed obligations/request/source, contradictory evidence and correct source-view retention.

Per run and per relevant owner, log:

1. Original retrieved ranges and canonical owner bounds/identity.
2. Old/new literal view segments, executable body presence, omission reasons, source reads and cache hits.
3. Candidate and file counts before/after admission; exact group/request characters and first excluded file.
4. Comparison input/output, selected owners and dormant alternatives, group/schema failures.
5. Qualified support and obligations, source view used, cache hits/misses and their causes.
6. Controller actions, recovered owners and whether the changed representation actually affected discovery.
7. Final candidate pool, flow/filter/budget decisions, literal final request and model selections.
8. `coverage_status`, `sufficient`, implementation/supporting Oracle metrics, stage and total tokens, latency and failure cost.

For any loss, audit raw dense/sparse results → canonicalization → file admission → comparison → qualification → controller → final input → final model. A comparison rejection and a final-input omission are different causes. Different upstream inventories in live runs prevent strong causal claims; use identical saved-input comparisons to isolate representation/admission effects.

Do not equate two equal Oracle counts with stability of source quality, or a lower token count with success. Preserve evidence of failed and negative experiments.

## 11. Entry points and commands for future work

Files to inspect:

- `services/retrieval/workspace/pipeline/execution_flow/discovery_observations.py`: retrieved-range/owner intersection and initial visible text.
- `initial_owner_comparison.py` in the same directory: compact rendering, grouped payload and schema.
- `initial_file_admission.py`: file ordering and exact admission cost integration.
- `source_disclosure.py`: existing owner-source reads/cards; reuse relevant mechanisms, not its later-stage timing.
- `evidence_qualification.py`: semantic cache and budget-fitted input.
- `qualification_first_retrieval.py`: decision-to-candidate semantics.
- `retrieval_controller.py`, `actions/scheduler.py`, `verified_leads.py`: integration only; keep stage algorithms separate.
- `obligation_retrieval.py`: final flow scoring/admission and final request construction.
- `services/retrieval/workspace/source_ast/`, `services/retrieval/codegraph/source_ast.mjs`: language-routed owner/body information.

Actual TypeScript acceptance command, **for the future experiment, not run in this handoff**:

```powershell
$env:PATH = 'C:\Programming\guidedInteligence\node_modules\@colbymchenry\codegraph-win32-x64;' + $env:PATH
npm run coderepoqa:evaluate:workspace -- --issue-json C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/raw/issue.json --skip-response-generation
```

Run twice per accepted implementation variant. Do not add `--skip-final-evidence-selection` to an acceptance run. Diagnostic smoke runs with that flag are labelled separately and cannot establish final quality.

Reusable profile: `configs/testing/workspace.json`; `rebuild_index=false`, `dormant_island_completion_enabled=false`. Do not rebuild existing valid indexes. Current native generation uses GPT-5.6 Luna; the profile's `codex_model` field is not the model used by native generation. Inspect active generation settings without printing secrets. Keep model, prompt, index scope, controller bounds and unrelated settings fixed.

Existing focused suite, to run only when implementing/testing the next step:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_qualification_reuse tests.test_json_completion tests.test_retrieval_server tests.test_qualification_first_retrieval tests.test_initial_owner_comparison tests.test_obligation_retrieval tests.test_qualified_structural_file_leads tests.test_retrieval_action_policies tests.test_source_ast_router -q
```

Extend focused tests for the selected body contract; do not present existing tests as validation of unimplemented behavior.

### Suggested continuation prompt

“Read `services/retrieval/docs/decisions/retrieval-handoff-qualification-and-owner-source-plan.md`, the referenced current decision note, and the experiment protocol. Preserve the dirty worktree. First confirm the qualification-policy baseline and proposed bounded owner-card budget. Then follow the separately authorized experiment sequence, comparing targeted repair and consistent cards against the same baseline, with literal source inspection and two real TypeScript acceptance runs per variant. Do not reindex or change unrelated retrieval settings. Report questionable tradeoffs before reverting.”
