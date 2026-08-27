# Qualification reuse and optional completion budget

Continuation: [qualification and owner-source handoff](retrieval-handoff-qualification-and-owner-source-plan.md)
records the final-flow ranking audit, the proposed positive-proof-retention alternative, and isolated future
owner-body experiments. That handoff is documentation only; it does not change this experiment's provisional status.

## Baseline and independent boundaries

Baseline: current append-crossing admission and connection-preservation correction, with
qualified structural leads and helper-flow admission retained. TypeScript runs
`run-20260827T142925Z` / `run-20260827T142935Z` were partial/false, retained three implementation
Oracles each, and used 113,718 / 97,572 retrieval tokens. No index, model, input budgets,
owner-comparison preview, scheduling, round count, or dormant-completion setting changes.

1. **Reuse semantic qualification.** In `run-20260827T124548Z`, helper
   `obs_03047c7d6afe13aa` received direct evidence in round 2 (trace 915) and navigation-only
   in round 3 (1342), despite identical 331-character disclosed source. Cache validated
   decisions within one controller run, keyed by the actual budget-fitted source and its
   owner/path/completeness context, request, obligation definitions, and prompt/model settings.
   Retrieval recurrence and query provenance are not semantic changes. Fit the original batch
   first, then omit cache hits without enlarging other cards. New source/context requires a
   real LLM decision. Record every hit/miss and the original decision round. This is not
   a deterministic substitute for an LLM: only previously validated real decisions are reused.
   Risk: stale judgments if a relevant input is omitted from the key; conservative context
   invalidation and focused changed-source/owner/obligation tests are required. Expected impact:
   fewer repeated decisions/tokens, stable classifications, unchanged candidate discovery.
2. **Optional API completion budget.** Failed final calls in `run-20260827T131714Z` and
   `run-20260827T131856Z` consumed all 4,000 completion tokens as reasoning and returned no JSON.
   Represent an unset generation budget as null and omit the API token-cap parameter. Preserve
   explicitly configured positive limits (including connection probes), schema validation,
   usage logs, timeouts, and retries. Provider/model limits still apply. Input/source limits
   are unchanged. Risk: increased completion cost/latency. Verify request serialization and
   replay one saved failed final request twice with only the cap removed, before integration.

## Verification and decision procedure

- Focused tests for both independent boundaries; deterministic recorded qualification replay
  twice, retaining the recorded first judgment rather than inventing a new semantic result.
- Two real saved-input final-selection calls with uncapped completion, recorded separately from
  actual-pipeline acceptance. Validate the existing response schema and selection contract.
- Two actual TypeScript runs via `coderepoqa:evaluate:workspace --skip-response-generation`.
  Keep final selection enabled; reuse existing indexes. Record all failures, stage usage,
  cache events, qualified/final helper outcomes, coverage, sufficiency, and Oracle overlap.
- Attribute cache preservation and token-cap exhaustion independently of upstream stochastic
  retrieval changes. Retain only measured improvements; questionable outcomes are reported for
  user review rather than silently reverting or changing other stages.

| Step | Attempt | Focused run 1 | Focused run 2 | Cost | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Qualification reuse | 2 | Recorded-body and moved-focus replay pass | Identical repeated audit; 2/4 live hits | 2,700 / 3,266 source chars not resent in final runs | Best-effort retained for review | Initial incorrect judgments are also retained |
| Optional completion cap | 1 | Saved final input: 10 valid selections | Same input: 11 valid selections | 18,024 / 18,631 total replay tokens | Focused reliability pass; retained | Overall retrieval quality remains mixed |
| Combined TypeScript acceptance | 2 | run-20260827T153030Z: partial/false, 3/4 Oracle files | run-20260827T153303Z: partial/false, 1/4 | 108,312 / 112,242 tokens | Not quality-accepted; retained provisionally for user review | Initial qualification, final budget and LLM omissions |

### Isolated evidence

The recorded-judgment audit is in `testing/codeRepoQA/qualified-file-lead-replays/qualification-reuse-1.json`
and `qualification-reuse-2.json`; both hash to
`645886F46F2DDAA3BE0E55D09DC277082D179579D39D3307D8B812FC12CA959F`.
Of 35 judgments, three have unchanged per-snippet semantic inputs. Reuse would preserve
`getReferencedByPaths` as direct evidence, but also preserve
`getFilesAffectedByUpdatedShapeWhenNonModuleEmit` as insufficient and
`getSemanticDiagnosticsOfNextAffectedFile` as navigation-only. Their recorded later judgments
were navigation-only and direct evidence respectively. This is consistency, not selective
protection of positive judgments; the quality of the first judgment remains an independent risk.

The real API replays are `uncapped-final-1.jsonl` / `uncapped-final-2.jsonl` in the same directory.
Each asserts that the saved request is unchanged except for omission of `max_completion_tokens`.
Both returned `finish_reason=stop` and passed the saved response-schema and candidate-ID checks.
Completion use was 3,967 (888 reasoning) / 4,574 (1,114 reasoning). The second response exceeds
the former 4,000 ceiling. The first does not, so its improvement cannot be attributed solely
to needing more tokens. The original run failed twice at 4,000 reasoning tokens with empty JSON.
The replays do not reconstruct controller behavior or count as end-to-end acceptance.

Implementation leaves the generation budget explicitly null in the workspace profile/current
configuration, preserves null through server and benchmark loading, and makes the UI's empty
field mean provider default. Explicit numerical caps, including 64-token connection probes,
remain supported. No changes to 4,000-character source cards or final input budgets.

## Attempt 1 live audit and narrowly corrected attempt 2

Attempt 1 completed both actual runs: 152348Z = partial/false, three implementation Oracles,
14 items / five files, 102,630 tokens; 152358Z = partial/false, three Oracles, 14 items / five
files, 107,688 tokens. First run reused two decisions: getSemanticDiagnostics navigation-only
(trace 899) and getFilesAffectedBy direct evidence (1252), subsequently final rank 8.
Its final response needed 4,296 completion tokens (1631), beyond the old cap. Second run
had no reuse; getReferencedByPaths was qualified once (827), reaching rank 10 independently
of reuse. Its final response used 3,974 completion tokens (1449). All requests were uncapped.

Eight repeated snippets had genuinely changed source text. One additional miss in 152358Z
was overly conservative: watchMode.ts 688–716 had the same complete 1,910-character source
and full bounds, but its retrieved hit window changed to 703–711 (requests 470 / 1140).
Attempt 2 normalizes only the hit window for full-body cards with stable full bounds.
Exact text, owner identity/location, mode, truncation, obligations, and prompt/model remain
part of the key. Preview locations remain significant. Focused tests cover both cases;
two further actual acceptance runs verify this final variant. The initial two runs remain
recorded and are not relabelled as final-variant acceptance.

Attempt 2 saved-input replays (`qualification-reuse-v2-1.json` / `qualification-reuse-v2-2.json`)
both identify exactly this additional reusable watchMode range. Its recorded judgment was
navigation-only in both rounds, so avoiding that call is not itself a demonstrated quality gain.
Final-variant run `run-20260827T153020Z` failed at the existing owner/group validator before
qualification: response trace 57 placed `o145` in `g12`, but the request lists it in `g13`.
This maps to IOC-1. It consumed 25,314 retrieval tokens (23,518 comparison). No cache execution,
final result, or Oracle comparison exists for it. Comparison rules were not changed.
`run-20260827T153030Z` and replacement `run-20260827T153303Z` subsequently completed; results below.

### Verification surface

264 focused Python tests pass, including unchanged source/provenance, moved full-body hit
windows, changed preview locations, changed source/owner/obligations/model, changed source
allocation, batch-alias independence, invalid-output rejection and continuity exclusion.
The UI build passes. Type checking reports 13 existing errors; a read-only compiler check
substituting the HEAD versions of the two edited UI files produces the identical 13 errors.
No unrelated UI errors were repaired. The build also warns about the system Node version;
actual retrieval runs explicitly use the bundled structural-tool Node runtime.

## Final-variant live evidence and decision

`run-20260827T153030Z` completes partial/false with three implementation Oracles, 14 items,
six files, and 108,312 retrieval tokens. Stage totals: context 1,719; owner comparison 24,580;
qualification 31,601; coverage 31,056; final selection 19,356. Final response trace 1834 is valid
and uses 4,129 completion tokens, including 961 reasoning, with no explicit cap or retry.

- Trace 991 reuses watchPresentFileSystemEntry's 2,014-character navigation-only judgment.
  Trace 1425 reuses getFilesAffectedByUpdatedShapeWhenNonModuleEmit's 686-character direct
  judgment. Those 2,700 source characters are not resent for qualification. This saves two
  per-snippet decisions, not two whole LLM calls; four qualification calls still execute.
- The latter snippet reaches the final LLM in mechanism_flow_7, then is unselected. It was
  not lost to the input budget or downgraded by qualification. Reuse does not force final
  selection. The cached sys.ts navigation snippet reaches final rank 13 under unchanged
  downstream flow selection; its metadata still identifies qualified_navigation_evidence.
- getReferencedByPaths reaches final rank 6, but is not a cache hit in this run; do not credit
  its recovery to reuse. The direct-cache-hit example from attempt 1, getFilesAffectedBy at
  rank 8, likewise proves preservation without proving what a new stochastic judgment would
  have done.
- Seven changed semantic inputs correctly require new qualification; exact changes and
  response usage are in `qualification-reuse-v2-first.json`.

`run-20260827T153303Z` completes partial/false with **one of four** implementation-Oracle
files, 11 items / five files, and 112,242 tokens. Stage totals: context 1,776; comparison
23,387; qualification 35,129; coverage 33,944; final 18,006. It uses the existing fourth-round
extension (stop trace 2305), not a changed round limit. All 13 LLM requests omit the cap;
final response 2312 succeeds in 3,500 completion tokens, including 789 reasoning.

Reuse records: introduceError 266 chars (566, round 1, direct); getNextInvalidatedProject
2,259 chars (1430, round 3, direct, final rank 6); invokeCallbackAndUpdateWatcher 601 chars
(1432, round 3, direct, rank 11); C::callback 140 chars (1892, round 4, insufficient).
This avoids four repeated snippet judgments / 3,266 source characters, but not entire calls.
Five changed inputs are reassessed. No unchanged cached item is resent in the same round.

### Exact loss audit for the weak result

- **builderState.ts was retrieved and admitted, not ranked out.** Raw channels contain four
  dense plus one sparse hit at 35, and another sparse hit at 45. Range resolution/canonicalization
  are at 51–52. Admission 53 includes four canonical snippets, best rank 3 / score 0.45;
  comparison 58–60 selects updateSignaturesFromCache, updateShapeSignature and
  updateExportedFilesMapFromCache. Qualification 112 marks the two cache-application helpers
  direct, but updateShapeSignature navigation-only because the displayed excerpt omits its
  computation. It is never a cache hit and never receives a later qualification. Both direct
  helpers survive the final pool (2306) and final LLM input (2311), in flows 14 and 11; the
  final model omits them (2312). No per-item rejection reason is returned for those omissions.
- **watchMode.ts was also retrieved and admitted.** Raw channels at 20/25/30/35/40/45 contain
  115 dense and four sparse hit occurrences. Resolution/canonicalization 51–52 produce 38
  canonical snippets; admission 53 includes the file. Comparison chooses introduceError,
  verifyTransitiveReferences, verifyProjectChanges and changeCore. Qualification 112 gives
  introduceError direct support, the two test excerpts insufficient/navigation respectively,
  and rejects changeCore. Within-file round-1 discovery yields navigation snippets (573).
  The cached introduceError judgment remains direct and survives the final candidate pool,
  but its flow is rejected_after_input_budget_crossing in ledger 2308, so no watchMode snippet
  reaches the final LLM. This is not a cache downgrade or a final-model rejection of that test.
- Controller rounds investigate watchMode, watcher dispatch, watch utilities, tsbuild and
  watchPublic. No new builderState owner or fuller updateShapeSignature card is qualified.
  These unchanged discovery/source-allocation/final-selection boundaries remain limitations.
  Two cached utility/scheduling snippets do reach final evidence, so indirect changes in the
  evolving candidate pool cannot be ruled out. The audit does not establish causal neutrality
  of reuse merely because the missing files themselves were not downgraded by it.

### Comparison and disposition

The final pair uses 220,554 tokens versus the baseline pair's 211,290 (+9,264 / 4.4%).
Qualification totals are 66,730 versus 67,109; coverage totals are 65,000 versus 57,339,
with an extra controller/coverage round in the weak run. Final-selection totals are 37,362
versus 33,688. Different upstream inventories, selected owners and round counts prevent
attributing these deltas solely to the output cap or cache. The experiment shows neither
an overall quality gain nor a reliable end-to-end token reduction.

Keep the output-cap correction for its demonstrated response-completion benefit. Qualification
reuse satisfies the requested consistency rule, but the combined final pair is **not accepted
as a stable quality improvement**. Leave both changes provisionally applied for user review,
as explicitly requested for questionable results; do not silently revert or tune other stages.
No owner-body disclosure, final budget, qualification prompt or ranking change was implemented.

Full final audit: `testing/codeRepoQA/qualified-file-lead-replays/qualification-reuse-final-acceptance.json`.
All five actual invocations are accounted for: four completed (two per variant) and one
owner-comparison failure. Actual-run tokens total 456,186; isolated real final replays add
36,655, for 492,841 measured verification tokens. Saved judgment audits spend no LLM tokens.

## Owner-body options (unchanged; analysis only)

The `_binop` owner was resolved, but comparison saw only the retrieved-range/owner intersection,
then an 80-character preview. Full owner source was disclosed only after selection. A minimum
character count would not guarantee executable body content (headers/docstrings can satisfy it).
Options to assess after these experiments: targeted body repair for signature-only cards;
consistent bounded owner-body cards for every owner; or a separate body-inspection pass.
Any later implementation must preserve the actual body in the comparison renderer and measure
the effect of larger cards on complete-file admission. No evidence-region grouping is proposed.

1. **Targeted repair:** detect owner cards with only declaration/documentation text using the
   language-routed AST adapter; read a bounded body window for those owners. Lowest payload
   growth, but a technically nonempty yet irrelevant body fragment can still escape repair.
2. **Consistent bounded owner cards:** keep owner signature, retrieved focus and an actual body
   window. Show complete small owners; retain explicit gaps/line ranges for large ones. Read
   each file once and calculate admission cost from the same rendered cards actually sent to
   comparison. More consistent evidence, but larger payloads can admit fewer files. Prefer
   testing this against the exact saved `_binop` and TypeScript comparisons before live runs.
3. **Two-pass comparison/inspection:** a compact first pass requests fuller bodies. Adds an LLM
   round trip and can still discard a useful owner before seeing its body; not the preferred
   first experiment.

Whichever option is tested, change the 80-character renderer alongside body acquisition;
fetching full text then rendering only a signature would leave the failure intact. Do not merge
owners into regions, automatically promote body-repaired owners, or interpret a minimum string
length as sufficient evidence. Quality checks must include the selected owner, retained files,
literal body lines, comparison tokens, and dormant disposition—not just additional source bytes.
