# Grouped Initial Owner Selection Experiment

## Status

Accepted through the authorized TypeScript pre-qualification boundary. The grouped contract is retained together
with the separately reversible 60,000-character quality-prefix file admission policy. Qdrant retrieval, CodeGraph
resolution, canonical owner identity, compact source views, the global 24-owner ceiling, qualification semantics,
controller behavior, and final selection are unchanged.

## Observed problem and saved boundary

Preferred-size quality-prefix runs `run-20260825T032456Z` and `run-20260825T032649Z` reduced comparison to 159 and
177 owners, but the unchanged flat response contract rejected semantically coherent selections. Run 1 selected four
distinct `builder.ts` owners; run 2 selected three `tsbuildPublic.ts` and three `builderState.ts` owners. The JSON
schema enforced only 24 globally, the prompt requested two per file, and runtime rejected larger same-file sets.

The saved literal comparison payloads and model configuration from those runs are the replay inputs. No synthetic
candidate list may replace them.

## Attempt 1: grouped primary and additional owners

### Contract

- Return one `selections` row for each selected file group.
- Each row contains one `primary_owner_id` and zero or more `additional_owner_ids` from that same group.
- Additional owners are permitted only for distinct causal steps, state mutations, diagnostics, contrasts, or other
  nonredundant obligation contributions.
- Prefer a useful owner from another file when its contribution is comparable.
- A file group may be omitted; the global allowance must not be filled merely because capacity remains.
- Runtime validates group membership, duplicate groups/owners, and at most 24 owners globally. It does not impose or
  clip a numerical per-file maximum.
- Trace primary/additional counts, selected owners per file, largest-file count/share, and selected file count.

### Expected effects

- Quality: preserve several genuinely distinct mechanisms from one central file without encouraging unstructured
  same-file accumulation.
- Cost: a small prompt/schema increase only; no extra LLM call.
- Reliability: eliminate split schema/prompt/runtime behavior and make same-file expansion explicit and auditable.

### Risks and rollback

- A broad file can still dominate the 24 global positions.
- The model can label redundant owners as additional selections without a machine-verifiable semantic distinction.
- Grouped output can increase schema complexity or provider failures.

Reject attempt 1 if either saved-payload replay fails schema/runtime validation, one file receives more than half of
all selections, third-and-later owners are materially redundant/noisy, central Builder/BuilderState/TsBuild/watch
mechanisms regress, or comparison cost grows materially. Do not hide concentration with deterministic clipping.

If both replays pass, restore the unchanged 60,000-character quality-prefix admission implementation and run the
actual TypeScript pre-qualification pipeline twice. The grouped contract remains step 1; prefix admission remains the
separately reversible step 2.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Grouped initial owner selection | 1 | 93 tests pass | 93 tests pass | Replay 20,720/22,306 tokens | Retained | Cross-case semantic stability |
| Combined with unchanged 60K quality prefix | 1 | `run-20260825T035631Z` | `run-20260825T035754Z` | 22,307/23,756 comparison tokens | Retained through pre-qualification | Downstream acceptance |

## Results

### Saved-payload replays

- The exact 159-owner payload selected 15 owners across six files. The largest group was four `builder.ts` owners,
  26.7% of the result. Its third-and-later owners were `isChangedSignagure` and
  `createBuilderProgram::getSemanticDiagnostics`, distinct signature/diagnostic mechanisms rather than repetitions.
- The exact 177-owner payload selected 15 owners across six files. Its largest groups contained three owners, 20% of
  the result. Third owners included `invalidateProjectAndScheduleBuilds`,
  `createBuilderProgram::getSemanticDiagnosticsOfNextAffectedFile`, and `updateSignaturesFromCache`.
- Both responses validated without a numerical per-file cap or deterministic clipping. One weak single-owner
  `emitFilesAndReportErrors` preview persisted, but it was not caused by grouped expansion.

### Combined actual-pipeline runs

- `run-20260825T035631Z`: 412 canonical snippets across 93 files; 172 owners across 14 files admitted at 59,457
  characters; 10 owners across six files selected; maximum two from one file; 22,307 comparison tokens. Qualification
  preparation used 29,513 characters for ten snippets across six files.
- `run-20260825T035754Z`: 448 canonical snippets across 112 files; 191 owners across 18 files admitted at 59,956
  characters; 15 owners across eight files selected; maximum three from one file and 20% largest-file share; 23,756
  comparison tokens. Qualification preparation used 34,982 characters for 15 snippets across eight files.
- Both runs retained `builder.ts`, `builderState.ts`, `tsbuildPublic.ts`, and watch/project-reference evidence. The
  second run exercised three selections from both Builder and BuilderState without takeover or runtime rejection.
- Lifecycle partitions were complete: `412 = 10 selected + 162 dormant + 240 deferred` and
  `448 = 15 selected + 176 dormant + 257 deferred`.
- Both runs stopped before the round-zero qualification LLM. These results accept the initial boundary only; they do
  not establish controller or final-evidence quality.

## Full-pipeline acceptance checkpoint

Two actual runs kept final evidence selection enabled and skipped only explanation generation:

- `run-20260825T043113Z`: 446 canonical snippets across 94 files; 187 owners across 11 files admitted at 59,277
  characters; 16 owners across seven files selected initially; 21 final candidates and 12 final evidence items across
  six files. It finished `partial/false`, used 101,747 retrieval LLM tokens, and retained three substantive Oracle
  implementation files: Builder, BuilderState, and WatchMode.
- `run-20260825T044117Z`: 356 canonical snippets across 67 files; 149 owners across ten files admitted at 51,590
  characters; eight owners across five files selected initially; 13 final candidates and ten final evidence items
  across six files. It finished `partial/false`, used 93,656 tokens, and retained the same three substantive Oracle
  files. The scorecard's fourth overlap, `tscWatch/helpers.ts`, is only a structural file trace whose own text says it
  does not prove behavior inside the file; it is not counted as complete source evidence here.
- Earlier downstream checkpoint `run-20260825T000741Z` retained two substantive Oracle implementation files and used
  114,240 tokens. Both new runs therefore improved substantive overlap from two to three while reducing total
  retrieval tokens by 10.9% and 18.0%.
- The controller did not erase the initial improvement. Run 1 promoted 15 of 16 initial snippets and all 15 entered
  the final candidate pool; run 2 promoted all eight, all entered the pool, and all remained represented in final
  evidence. Controller actions also added useful Builder/BuilderState/TsBuild continuations.
- Final coverage remained `partial/false`. Missing evidence is the concrete watcher-to-project-pending handoff, the
  `Session`/wildcard-re-export-to-consumer path, the direct-import/non-watch contrast, and the actual quiet diagnostic
  result. Both controllers stopped at the configured three-round budget; run 2 still had two pending verified leads
  after reaching its verified-lead execution cap.
- One intervening attempt, `run-20260825T043613Z`, failed explicitly during obligation evidence consolidation after
  both the original LLM response and its retry returned empty/non-JSON content. It is reliability evidence, not a
  retrieval-quality comparison.

Decision: retain the grouped selection and 60K prefix for this case. The two completed downstream runs show a
repeatable substantive-overlap improvement and lower total cost, but do not resolve cross-case acceptance or the
remaining controller coverage gaps.

## Cross-repository full-run checkpoint

Four additional actual runs kept final evidence selection enabled and skipped only explanation generation:

- Pandas `pandas-dev-pandas-10068`:
  - `run-20260825T062635Z` completed `partial/false`, selected four evidence items across three files, and retained
    the sole implementation Oracle `pandas/core/series.py` at rank 1 through exact `Series::_binop`. It admitted 69
    comparison owners across seven files at 23,920 characters and used 70,047 retrieval LLM tokens, including 9,135
    initial-comparison tokens.
  - `run-20260825T063006Z` completed `partial/false`, selected three evidence items across two files, and again
    retained `pandas/core/series.py` at rank 1 through exact `Series::_binop`. It admitted 86 owners across seven files
    at 27,446 characters and used 53,030 tokens, including 11,007 initial-comparison tokens.
- Vue `vuejs-vue-242`:
  - `run-20260825T063303Z` completed `partial/false`, selected six evidence items across five files, and retained the
    sole implementation Oracle `src/exp-parser.js` at rank 1 through `makeGetter`. All 179 canonical owners across 48
    files fit at 51,972 characters; total usage was 71,024 tokens, including 20,994 comparison tokens.
  - `run-20260825T063619Z` completed `partial/false`, selected seven evidence items across five files, and again
    retained `src/exp-parser.js::makeGetter`, this time at rank 4. All 189 canonical owners across 34 files fit at
    52,658 characters; total usage was 56,161 tokens, including 22,597 comparison tokens.

Both cases therefore retained their exact sole implementation Oracle in both repeats. This expands mechanical and
final-selection acceptance beyond TypeScript, but all four runs remained `partial/false`; stable endpoint retrieval
does not by itself complete the requested causal explanation.
