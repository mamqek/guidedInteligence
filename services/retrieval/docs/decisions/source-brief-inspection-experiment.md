# Source-grounded descriptions and coalesced owner inspections

## Final disposition: reverted at user request, 2026-08-28

All experiment runtime, prompt, test and replay-script changes were removed from the working tree.
Returned to `codex/dormant-island-reconnection` at `7c50ba2` (`before summaries`); deleted
`codex/source-brief-inspection`. Earlier focused owner cards, group-keyed selection and positive-proof
qualification reuse remain unchanged. The temporary qualification/coverage/final budget changes are removed.
Archived code is recoverable from stash `e0a4ed606195f93c7ad26d2eeb80f0056f633810`, not active code.

All actual runs and isolated replay artifacts are preserved. Actual experiment runs
`run-20260827T235551Z`, `run-20260827T235644Z`, `run-20260828T000632Z`, and `run-20260828T000640Z`
are marked with `experiment-annotation.json` in their original directories; completed run metadata also
carries the experiment cohort and `include_in_baseline_statistics: false`. Keep these separate from baseline
statistics. These are explicit labels, not a new automatic aggregation filter. The replay directory README
distinguishes experiment artifacts from the unchanged baseline pair. No trace or result was deleted.

Rollback verification: runtime/tests/configuration match `7c50ba2`; 81 qualification/controller tests and
11 qualification-reuse tests pass. All 20 original trace/result artifacts across the four runs have unchanged
SHA-256 hashes. Only completed run metadata was augmented with labels; no retrieval or indexing was rerun.

Baseline clarification: `QualificationDecision` already stores `reason`, `visible_support`,
`missing_information`, `local_follow_up`, and supported obligation IDs. They are retained in controller
decision state and traces. A fresh qualification payload does not include the prior decision/rationale;
the ordinary candidate/coverage payload retains the support label and obligations, not that full rationale.
Unchanged direct proof and verified shorter crops are protected by the existing positive-proof reuse cache.
Passing prior rationale into genuine reassessments would be a separate, unimplemented experiment.

## Authorization / baseline, 2026-08-28

Branch: codex/source-brief-inspection, from codex/dormant-island-reconnection; pre-existing work preserved.
Recorded base commit: `7c50ba2` (`before summaries`). No commits or branch merges made by this experiment.
Baseline actual runs 225224Z / 225234Z: partial/false, 3/2 implementation Oracles, 101,440/101,088 retrieval tokens.
Group-keyed owner selection and focused cards stay fixed. No initial query, ranking, admission, owner comparison,
index, model, explanation-generation or final-selector logic change. This starts at round-zero qualification.

The user authorizes complete-owner descriptions, description-based controller context, and model-requested source
inspection. Metadata contains the existing source identifiers and call inventory, not a generated explanation for
every identifier. Descriptions explain observed flow, not a speculative causal claim about the reported issue.

## Steps and boundaries

1. Complete-source briefing/qualification: a cohesive module obtains validated complete owner source from disclosure,
   includes structural call metadata, and uses the existing qualification classification contract plus description,
   line citations and explicit inspection answers. Source is batched at 100,000 total input characters, not cropped
   by the old 4,000-character card rule. Oversized owners are line-partitioned across batches, with every part logged;
   the owner is complete only after all parts succeed. No silent surrogate on model failure. Cache unchanged initial
   briefing per source revision; new inspection purposes explicitly invalidate semantic reuse, not source caching.
2. Coalesced queue: key by source-owner identity + exact source revision. One pending entry holds distinct question
   IDs, obligation IDs, question text and all requesting rounds. Repeated question merges provenance; another purpose
   is appended. Execution consumes one ordinary slot and all purposes are checked together. Completed questions are
   suppressed; changed source or genuinely different questions can execute again. No per-run two-inspection cap.
3. Coverage/action context: replace repeated source with file-grouped briefs, actual qualification support, metadata,
   prior outcomes and pending purposes. Extend the existing coverage call to propose up to two owner inspections.
   Those typed actions compete in the ordinary two-slot scheduler after novelty checks; special recovery queues stay
   unchanged. Pending work prevents premature no-gain termination but does not extend the normal round rules. At
   termination, outstanding questions remain explicitly unresolved. Descriptions never fabricate new candidates.
4. Integration: two real TypeScript runs, existing snapshots/indexes, explanation disabled and final selection on.
   Temporary qualification/coverage budget 100,000. Final flow threshold 100,000 (plus existing 5,000 overhead reserve).
   Final output still receives source through its existing candidate contract, not descriptions substituted as proof.

## Risks / attribution / acceptance

Complete initial source and larger final budget can independently change quality and cost. Save fixed source inputs
and run two isolated briefing/coverage calls before live tests. Measure source completeness, total source chars read,
brief/context chars, queue merges, suppressed repeats, pending/executed purposes, individually answered questions,
actual source examined, qualification changes, final evidence, coverage/sufficient and all LLM tokens. Test a pending
round-1 question joined by a different round-2 question; one action, both answers. Test duplicates, owner aliases,
changed revisions, multiple owners batched, invalid citations/IDs, oversized owners, queue contention and final-round
pending state. No claim of a live coalescing benefit when it is exercised only by fixtures.

At most three variants per step. Inspect relevant snippets, not Oracle counts alone. Do not accept merely for token
savings; a large cost increase or quality regression requires reporting and disabling/reverting this experiment only.
Questionable intermediate behavior is reported before reversion. Baseline source snapshots are stored outside the repo
for exact rollback without touching the earlier dirty work. No catch-all legacy fallback beside the replacement.

## Ledger

| Step | Attempt | Focused checks | Actual runs | Decision |
|---|---:|---|---|---|
| Complete source briefs | 2 | Two valid real source/description replays | Two complete retries | Mechanically verified, not quality-accepted |
| Coalesced inspection queue | 1 | Coalescing, revision, suppression and batching tests | Delayed inspections observed | Cross-round same-owner merge remains fixture-only |
| Brief coverage/action context | 2 | Two lean-context replays and a late-context replay | Two complete retries | Provisional; higher cost, no final-quality gain |

Attempt 1 real boundary replays `testing/codeRepoQA/source-brief-replays/boundary-1.jsonl` and
`boundary-2.jsonl` both stopped on invalid source citations. A description cited an owner's trailing
blank line outside the actual submitted part. No selection was silently repaired. Attempt 2 scopes
each part's citation integer bounds in its own strict decision schema. Source and semantic policy unchanged.

Attempt 2 complete-source checks `boundary-v2-1.jsonl` / `boundary-v2-2.jsonl` passed:
14 owners, all 42,588 source characters, 11/12 direct decisions. Qualification tokens 36,759/36,646.
Coverage initially cost 24,996/24,761 tokens with verbose call dictionaries. The coverage-only representation
now uses lossless ordered `call_columns`/`call_rows`; raw structural tool results remain in the trace.
Replays of the same validated descriptions (`inspection-1.jsonl` / `inspection-2.jsonl`) passed:
coverage 19,445/19,265 tokens; 2/0 model-requested inspections, respectively. The first two owners were
examined together for 6,566 tokens and their questions received separate answers. Zero proposed actions is
valid, not a hidden deterministic replacement. Ten focused tests and 81 existing qualification/controller
tests pass. Cross-round coalescing is fixture-proven; not yet observed in a live pipeline.

Integration attempt 1: actual `run-20260827T235551Z` / `run-20260827T235644Z` reached round 3,
then failed the 100k coverage-context guard: 114,261 / 105,071 characters. No final selection or valid
quality score. Existing index reused, explanation not generated. The memory carried full qualification
reason/visible-support narratives alongside the grounded descriptions. Coverage attempt 2 omits those
duplicate narratives only from repeated coverage context; original QualificationDecision and trace remain
unchanged. Classification, supported obligation IDs, missing claims, local follow-up, descriptions/citations
and complete call metadata are still passed. No budget increase and no file/snippet removal.

Lean-context checks passed twice on saved round-zero descriptions, with two requested inspections batched
and separately answered in each replay: 17,947/17,949 coverage tokens, 6,219/6,627 inspection tokens.
The larger failed run's late briefs also passed a focused replay (`lean-late-context.jsonl`), at 97,648 input
characters with replay ID aliases and no historical pending context. That is not an exact runtime-size replay:
runtime candidate IDs and prior outcomes cost more. Serialize payload JSON without insignificant separator
whitespace for extra headroom (no source/metadata removal); count that literal serialization for the budget.
Integration retry retains all scope/limits and does not treat the failed pair as acceptance.

## Completed comparison, 2026-08-28

| Measurement | run-20260828T000632Z | run-20260828T000640Z |
|---|---:|---:|
| Initial admitted files / compared owners | 4 / 75 | 5 / 108 |
| Initial comparison input characters | 64,693 | 75,796 |
| Round-zero snippets / direct snippets | 12 / 9 | 13 / 10 |
| Round-zero source characters read | 48,117 | 48,527 |
| Unique briefed snippets after controller | 27 | 27 |
| Total source characters sent for briefing/inspection | 72,009 | 80,157 |
| Source qualification calls / coverage calls | 5 / 4 | 5 / 4 |
| Full-owner inspections executed | 2 | 1 |
| Pending inspections at stop | 2 | 3 |
| Unchanged descriptions/judgments reused | 4 | 8 |
| Largest coverage input, characters | 94,383 | 87,394 |
| Final serialized payload characters | 50,757 | 59,114 |
| Final candidate snippets / selected evidence | 12 / 11 | 16 / 13 |
| Final flows / connections excluded by budget | 0 / 0 | 0 / 0 |
| Oracle files retained | 3 | 1 |
| coverage_status / sufficient | partial / false | partial / false |
| Retrieval tokens | 184,492 | 179,634 |

Both reused the existing 83,401-point index, kept dormant completion disabled, and generated no explanation.
Sources and decisions are in [run 1 trace](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000632Z/retrieval-trace.jsonl)
and [run 2 trace](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000640Z/retrieval-trace.jsonl).
Machine-readable audit: `testing/codeRepoQA/source-brief-replays/acceptance-audit.json`; regeneration is supported
by `testing/codeRepoQA/analyze_source_briefs.py`. Earlier failures: `failed-first-pair.json`.

### Exact behavior and loss boundaries

- Full-source examination works, without the old 4k crop. Run 1 examines `getNextAffectedFile` (3,131 chars,
  [line 933](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000632Z/retrieval-trace.jsonl:933))
  and `forEachReferencingModulesOfExportOfAffectedFile` (2,763 chars,
  [line 1307](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000632Z/retrieval-trace.jsonl:1307)).
  Both answers explicitly distinguish the visible local callback/map behavior from unproven downstream or
  wildcard-specific behavior. Neither establishes the requested missing chain.
- Run 2 examines all 9,107 characters of `getUpToDateStatusWorker`
  ([line 421](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000640Z/retrieval-trace.jsonl:421)).
  The answer establishes the requested timestamp/pseudo-up-to-date conditions; this owner reaches final rank 6.
  It was already direct before inspection. This is a useful verification, not newly discovered source or proof
  that inspection caused its final retention. No inspection-induced support-level downgrade occurred.
- Pending work survived scheduling, including a round-zero request executed in round three. At the unchanged
  three-round stopping boundary, run 1 retains two requests
  ([line 1649](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000632Z/retrieval-trace.jsonl:1649));
  run 2 retains three
  ([line 1297](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000640Z/retrieval-trace.jsonl:1297)).
  They were not silently discarded or counted as answered. No live run naturally requested two distinct questions
  for the same pending owner. That coalescing contract is proven by focused tests only. Exact normalized duplicates
  are deterministically suppressed; paraphrase equivalence still depends on the model respecting prior outcomes.
- Run 1: `builderState.ts` has eight raw dense hits, eight submitted ranges/eight resolved-owner occurrences,
  seven canonical snippets, global file rank 10, and is excluded at initial file admission (trace lines 35, 51, 54).
  The unchanged qualified-call recovery later follows `BuilderState.getReferencedByPaths` from `builder.ts:509`
  ([line 499](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000632Z/retrieval-trace.jsonl:499)).
  Its complete helper qualifies direct at line 539 and reaches final rank 7. This is existing recovery, not a
  newly invented discovery capability of descriptions.
- Run 2: `builder.ts` has 14 dense and three sparse hit occurrences; `builderState.ts` has nine dense and three sparse.
  CodeGraph receives 12/10 unique ranges and returns 11/10 owner occurrences respectively (trace lines 20–51).
  Both survive canonicalization (10/9 snippets), but global file ranks 8/6 fall outside the five admitted files
  ([line 54](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000640Z/retrieval-trace.jsonl:54)).
  Neither reaches owner comparison, briefing, qualification, later recovery, or final selection. This earlier,
  unchanged admission boundary—not a description/inspection rejection—explains the missing builder files.
- Both final selectors rank `verifyTransitiveReferences` first as an `issue_anchor` and assign broader obligations.
  Yet qualification explicitly says the complete 20,990-character owner lacks the wildcard export / changed Session
  interface scenario: [run 1 line 119](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000632Z/retrieval-trace.jsonl:119),
  [run 2 line 126](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000640Z/retrieval-trace.jsonl:126).
  Source supports generic watch/project-reference behavior, not the specific reproduced outcome. Final choices at
  [run 1 line 1656](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000632Z/retrieval-trace.jsonl:1656)
  and [run 2 line 1304](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T000640Z/retrieval-trace.jsonl:1304)
  overstate that role. The unchanged final request has no `missing_information` field and receives source, not these
  descriptions/qualification warnings. This is a remaining downstream interpretation boundary; it was not changed.

### Cost and decision

The completed pair costs 364,126 retrieval tokens versus baseline 202,528: **+79.8%**, with 3/1 versus 3/2 Oracle
files and partial/false throughout. Different upstream inventories prohibit attributing the Oracle-count difference
to descriptions alone. No final-quality improvement is demonstrated.

The growth is primarily repeated coverage context (83,958/75,161 tokens versus baseline 29,875/31,112) and
full-source qualification/inspection (61,564/59,160 versus 31,943/28,426). Final selection costs only
18,847/20,963 versus 18,730/17,691. Raising the final budget is not the main token driver. Even without raw
snippets, the accumulated descriptions, missing claims and complete call inventory remain large.

Validation: 108 focused/relevant unit tests pass (10 new, 81 qualification/controller, six action-policy,
11 qualification-reuse); strict citation and action validation retained. Experiment cost ledger: 303,020 focused
replay tokens + 324,752 failed-live tokens + 364,126 completed-live tokens = **991,898 measured retrieval/stage
tokens**. This total does not include separate request-analysis accounting; explanation generation was skipped.

**Decision: reverted at user request after review; not accepted as a quality improvement.** The experiment branch
has been deleted and baseline runtime restored. Records remain for separate historical analysis. Nothing is
merged into the baseline runtime. Do not silently raise limits or change final-selection semantics to claim success.
Further evaluation should separate repeated-metadata cost, inspection scheduling/novelty, and the final selector's
loss of qualification caveats. Initial file admission remains a separate problem.
