# Retrieval Changelog

## 2026-07-12

### Changed: Adaptive Loop Support-Subquery Promotion

- Intended stage boundary:
  - keep Step2 as the planner that emits `support_subqueries`,
  - keep `adaptive_loop.py` responsible for promotion decisions,
  - fix `role_retrieval.py` so supporting-phase retrieval executes support-role queries instead of looking only at primary `llm_subqueries`.
- Expected quality impact:
  - promoted objectives such as `verification_repro -> tests` should now have a real chance to add evidence,
  - narrow defect runs should avoid the previous no-op promotion where a role was promoted but no tool calls were made,
  - the deterministic gate remains unchanged in this slice; objective-aware sufficiency is still a separate follow-up.
- Expected token impact:
  - promoted support rounds can now spend additional retrieval calls where previously they spent zero,
  - first-round token use is unchanged,
  - total tokens may increase when support evidence is actually retrieved, but the increase is tied to an explicit deferred-objective promotion.
- Known regression risks:
  - support subqueries may retrieve noisy test/config/doc artifacts if Step2 emits weak support queries,
  - support evidence may improve synthesis while the legacy deterministic gate still reports missing old required roles,
  - the no-op skip guard only skips roles with no executable planned query; it does not suppress an executed query that returns no useful evidence.
- Verification:
  - `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval tests.test_workspace_retrieval` passed 85 tests immediately after the change.
  - `npm.cmd run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json` failed before pipeline execution because npm invoked system `python`, which lacked `langgraph`.
  - subsequent direct `.venv\Scripts\python.exe` and `py -3.11` invocations became blocked by the Windows Python launcher/session state, so the real Vue rerun could not be completed in this turn.
- Follow-up runtime repair and real-run result:
  - repaired `.venv` by rebinding it from the stale WindowsApps Python target to `C:\Users\mukha\AppData\Local\Programs\Python\Python311\python.exe`,
  - changed Python-backed npm scripts to invoke `.venv\Scripts\python.exe` directly so the documented CodeRepoQA commands use the project environment,
  - reran the focused unit suite: `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval tests.test_workspace_retrieval` passed 85 tests,
  - real Vue run `run-20260712T164219Z`: `coverage_status=partial`, `sufficient=false`, `overlap_count=0`, `implementation_overlap_count=0`, 2 retrieved source files, 226 tool calls, retrieval LLM tokens `12,439`, no promoted roles because `owner_grounded=false`,
  - real Vue run `run-20260712T164506Z`: `coverage_status=partial`, `sufficient=false`, `overlap_count=0`, `implementation_overlap_count=0`, 2 retrieved source files, 237 tool calls, retrieval LLM tokens `12,509`, no promoted roles because `owner_grounded=false`.
- Quality conclusion:
  - the Python/npm environment is fixed,
  - the support-subquery promotion fix is unit-covered but was not exercised in the Vue real runs because the loop stopped in owner-recovery mode before promotion,
  - current adaptive-loop behavior is not acceptable on the Vue benchmark: two real runs missed the oracle owner file, so the next retrieval change should target owner-grounding/recovery before treating support promotion as validated.

## 2026-06-24

### Changed: Workspace Step2 Objective Metadata And Narrow-Defect Role Selection

- Intended stage boundary:
  - Step2 now classifies `primary_intent`, `specificity`, active/deferred objectives, preferred relations, stop contract, expansion policy, and deterministic prompt signal flags,
  - Stage consumes the Step2 metadata only through a gated compatibility bridge, `objective_role_selection_enabled`,
  - the first enabled behavior is intentionally limited to `defect_localization:narrow`; other intents remain metadata-only.
- Expected quality impact:
  - narrow defect reports should prioritize implementation-owner evidence before broad role coverage,
  - expected-vs-actual output should route to behavior/output evidence, while diagnostics should require concrete error/warning/exception/traceback text,
  - support artifacts remain available through the compatibility bridge until a real deferred-objective promotion loop exists.
- Expected token impact:
  - fewer initial required roles for narrow defects should reduce tool calls and retrieval LLM tokens,
  - support-role savings are not fully realized yet because deferred support roles are still available as a safety net.
- Known regression risks:
  - over-narrowing required roles can miss owner files when the current Stage lacks a promote-on-failure loop,
  - prompt text such as `renderVmWithOptions` can still trigger broad config-like flags through simple lexical matching,
  - the current objective-to-legacy-role mapping is transitional and can duplicate old role semantics.
- Real-run comparison:
  - baseline `vuejs-vue-10803` workspace run `run-20260623T112023Z`: `coverage_status=partial`, `sufficient=false`, implementation overlap `1`, owner file `src/platforms/web/server/modules/dom-props.js` at rank 2, 6 retrieved source files, 513 tool calls, 8 role subqueries, retrieval LLM tokens `24,239`, uncached prompt plus completion `23,215`.
  - accepted objective-role run `run-20260624T013101Z`: `coverage_status=partial`, `sufficient=false`, implementation overlap `1`, owner file at rank 3, 5 retrieved source files, 394 tool calls, 5 role subqueries, retrieval LLM tokens `16,856`, uncached prompt plus completion `15,832`.
  - intermediate `run-20260624T012539Z` regressed because wrong-output text activated `diagnostic_surface`; this was fixed by separating `has_diagnostic_surface` from `has_output_symptom`.
  - stricter support-deferral run `run-20260624T013551Z` reduced retrieval LLM tokens to `12,705` but missed the oracle owner file; that Stage change was reverted.
- Quality conclusion:
  - keep the gated narrow-defect role selection because it preserved baseline overlap and sufficiency status while reducing tool calls by 23% and retrieval LLM tokens by 30% on the Vue case,
  - do not remove initial support-role availability yet; deferred-objective promotion needs an explicit Stage loop and success gate first.
- Verification:
  - `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval` passed 13 tests.
  - `.venv\Scripts\python.exe -m py_compile services/retrieval/workspace/stage.py services/retrieval/workspace/step2/step2.py services/retrieval/workspace/step2/prompts.py tests/test_workspace_step2_objectives.py` passed.

## 2026-06-23

### Changed: Named Codex Prompt Profiles And Efficient Default

- Intended stage boundary:
  - move each Codex retrieval prompt and strict output schema out of Python into one self-contained profile directory under `services/retrieval/codex/profiles/`,
  - select the contract with `codex_prompt_profile` while keeping `codex` as one retrieval mode and leaving downstream explanation generation shared,
  - preserve schema-specific top-level and evidence fields generically so `services/retrieval/codex/provider.py` does not name or encode either profile's optional structure,
  - restore the original cheaper contract as the `efficient` default and retain the 2026-06-23 experiment as the opt-in `responsibility-complete` profile.
- Expected quality impact:
  - default Codex runs return to the previously measured compact evidence behavior,
  - the responsibility-complete owner/coverage metadata remains available for explicit quality experiments,
  - prompt experiments can now be compared without editing provider orchestration code.
- Expected token impact:
  - `efficient` matches the pre-experiment prompt and schema exactly and therefore restores the lower measured baseline behavior,
  - `responsibility-complete` retains the measured 100%-166% gross-token increase and 86%-126% retrieval-latency increase from the two-case experiment,
  - profile loading itself adds no model tokens.
- Known regression risks:
  - selecting the wrong profile in a centralized config can make benchmark results incomparable,
  - deleting or corrupting a profile file now fails Codex retrieval explicitly,
  - the efficient schema does not expose role, confidence, symbol, issue-analysis, or coverage-gap fields.
- Comparison and verification:
  - `efficient/prompt.md` reproduces the batch-002 `microsoft-TypeScript-45713` prompt after inserting the same issue packet,
  - `efficient/evidence.schema.json` is JSON-equivalent to that run's saved schema,
  - `responsibility-complete` preserves the exact prompt/schema contract used by `run-20260623T115317Z` and `run-20260623T115958Z`,
  - `.venv\Scripts\python.exe -m unittest tests.test_codex_provider tests.test_coderepoqa_retrieval tests.test_retrieval_server` passed 43 tests,
  - all profile and centralized config JSON files parsed successfully.
- Real efficient-profile verification:
  - `microsoft-TypeScript-45713` run `run-20260623T163652Z` loaded `efficient` from the new profile directory and recorded that name in run metadata and both Codex trace events,
  - retrieval completed in `164.836s`; full orchestration completed in `192.4s`,
  - `coverage_status=strong`, `sufficient=true`, with 5 evidence items across 3 files and 3 implementation-oracle overlaps at ranks 1-3,
  - gross tokens were `1,849,125` and uncached input plus output was `192,805`, illustrating normal Codex run-to-run cache variance even with the same prompt/schema contract.
- Usage:
  - existing `config:web:codex` and `coderepoqa:evaluate:codex` commands select `efficient`,
  - explicit `:efficient` and `:responsibility-complete` npm commands are available for web UI and testcase runs,
  - testcase run metadata and Codex retrieval traces now record `codex_prompt_profile`.

### Experiment: Responsibility-Complete Codex Evidence Prompt

- Intended stage boundary:
  - change only the Codex evidence-discovery prompt, its strict output schema, and direct schema-to-`EvidenceItem` metadata preservation,
  - leave workspace retrieval, orchestration, response generation, and understanding-check generation unchanged,
  - continue excluding verification data, oracle files, and post-resolution information from the Codex workspace and prompt.
- Expected quality impact:
  - rank likely implementation owners ahead of symptom surfaces and generic architectural files,
  - require a compact responsibility chain and make uncovered responsibilities explicit,
  - preserve symbol, role, relevance, and confidence metadata for downstream explanation generation and run inspection.
- Expected token impact:
  - the larger instructions and schema add a small fixed prompt/output cost,
  - the 2-6 evidence-item limit and anti-duplication rule should reduce broad file reading and repeated evidence,
  - success requires improved or stable oracle overlap without materially increasing gross or uncached Codex usage.
- Known regression risks:
  - responsibility-chain instructions may encourage unnecessary subsystem breadth,
  - strict role enums may force ambiguous evidence into an imperfect category,
  - implementation-owner bias may under-select tests that contain the only concrete reproduction,
  - prompt changes remain nondeterministic and require real-run comparison before broader adoption.
- Comparison plan:
  - rerun Codex mode for retrieval-grounded cases `microsoft-TypeScript-45713` and `microsoft-TypeScript-46770`,
  - compare against batch 002 Codex baselines using implementation overlap, top-k position, selected evidence count, elapsed time, gross tokens, and uncached tokens,
  - disable or revise the experiment if both cases regress in implementation overlap or if sufficiency becomes unstable.
- Real-run results:
  - `microsoft-TypeScript-45713` baseline `run-20260623T103650Z`: retrieval `203.619s`, full orchestration `228.129s`, `strong/sufficient=true`, 3 evidence items across 2 files, 2 implementation-oracle overlaps at ranks 1 and 2, gross tokens `1,537,434`, uncached tokens `79,258`.
  - `microsoft-TypeScript-45713` experiment `run-20260623T115317Z`: retrieval `378.561s`, full orchestration `401.190s`, `strong/sufficient=true`, 5 evidence items across 4 files, 3 implementation-oracle overlaps at ranks 1, 2, and 4, gross tokens `3,078,628`, uncached tokens `121,316`.
  - `microsoft-TypeScript-46770` baseline `run-20260623T105125Z`: retrieval `192.833s`, full orchestration `221.209s`, `strong/sufficient=true`, 6 evidence items across 3 files, one implementation-oracle overlap (`moduleNameResolver.ts`) at rank 3, gross tokens `1,463,271`, uncached tokens `93,671`.
  - `microsoft-TypeScript-46770` experiment `run-20260623T115958Z`: retrieval `435.558s`, full orchestration `473.295s`, `strong/sufficient=true`, 6 evidence items across 3 files, one implementation-oracle overlap (`moduleNameResolver.ts`) improved to rank 2, gross tokens `3,892,185`, uncached tokens `253,401`.
- Quality conclusion:
  - `45713` preserved the two core owner files and added the oracle watch-helper test path; its explicit coverage gaps correctly identified missing per-file aggregation state and a missing non-watch summary fixture.
  - `46770` moved beyond generic NodeNext architecture to the exact `loadModuleFromFile` branch that disables implicit extension lookup in ESM mode and added the closest repo-local test fixture.
  - retrieval quality therefore improved modestly without sufficiency regression, but retrieval latency increased by 86% and 126%, gross tokens increased by 100% and 166%, and uncached tokens increased by 53% and 171% respectively.
  - retain the prompt/schema as an experimental quality-oriented variant for now; it is not suitable as the default efficiency profile without a bounded-search follow-up.
- Verification:
  - `python -m py_compile services/retrieval/codex/provider.py tests/test_codex_provider.py`
  - `python -m unittest tests.test_codex_provider`
  - `.venv\Scripts\python.exe -m unittest tests.test_codex_provider tests.test_coderepoqa_retrieval` passed 11 tests.
  - both strict schemas were accepted by real `codex exec --output-schema` runs.

## 2026-06-22

### Added: Codex Evidence Provider Retrieval Mode

- Intended stage boundary:
  - add a workspace config switch, `retrieval.mode`, with `workspace` preserving the existing
    CGC/BM25/Qdrant path and `codex` delegating evidence discovery to `codex exec`,
  - keep Codex as an evidence provider only; response generation still consumes normal
    `EvidenceItem` records through the existing explanation framework,
  - run Codex in the currently selected workspace with read-only sandboxing and schema-constrained
    output.
- Expected quality impact:
  - avoids spending implementation effort on another code retrieval stack when Codex can already
    navigate the selected repository,
  - lets experiments focus on explanation structure, evidence transformation, and supportive data.
- Expected token impact:
  - local retrieval tokens from Step 2 and refinement are replaced by Codex usage,
  - Qdrant embedding/indexing work is skipped in `codex` mode,
  - total cost depends on the active Codex authentication path and selected model
    (`gpt-5.4-mini` by default).
- Known regression risks:
  - Codex evidence selection is less deterministic than the local retriever,
  - model availability depends on the active Codex/API entitlement,
  - broad prompts can make Codex inspect unrelated files or post-resolution corpus data,
  - line ranges returned by Codex can be stale if the workspace changes during a run.
- Comparison plan:
  - run the same CodeRepoQA prompt once with `retrieval.mode=workspace` and once with
    `retrieval.mode=codex`,
  - compare selected files, evidence line ranges, `coverage_status`, `sufficient`, response quality,
    and token/cost metadata,
  - record run IDs after the first real Codex-backed run.
- Verification so far:
  - `python -m py_compile services\retrieval\codex\provider.py services\retrieval\server.py services\retrieval\config.py`
  - `npm run web:build`
  - backend smoke check confirmed `codex` mode reports `index_status=codex_mode` and uses
    placeholder Qdrant/embedding config instead of local indexing.
- Measured Codex CLI run:
  - case: `microsoft-TypeScript-6307`,
  - model/auth: `gpt-5.4-mini` through the connected Codex subscription,
  - broad workspace attempt timed out before `turn.completed`, so no token total was recorded,
  - constrained run selected `issue.json` and `verification.json`; observed Codex usage from
    `turn.completed`: `90,193` input tokens, `59,392` cached input tokens, `3,606` output tokens,
    and `2,585` reasoning output tokens,
  - durable rerun that read the full issue JSON including comments recorded `182,189` input tokens,
    `153,088` cached input tokens, `2,675` output tokens, and `1,432` reasoning output tokens,
  - compared with the existing TypeScript 35468 workspace baseline average of `11,461` retrieval
    tokens, Codex agent retrieval is materially more token-expensive unless inputs are pre-filtered
    before handoff.

### Changed: CodeRepoQA Codex Retrieval Uses Sanitized Issue Packet

- Intended stage boundary:
  - keep CodeRepoQA prompt construction shared across retrieval modes via the visible-only
    `_user_prompt(title, initial_body)` packet,
  - select `workspace` or `codex` retrieval mode in the testcase runner config/CLI,
  - keep `verification.json`, oracle fields, raw `issue.json`, QA data, and run artifacts out of
    the Codex retrieval prompt and tell Codex not to inspect them,
  - keep Codex output schema-compatible with the existing `EvidenceItem` transformation.
- Expected quality impact:
  - Codex should behave more like the VS Code/codebase workflow: issue text plus source workspace,
    rather than raw corpus-file summarization,
  - evidence can plug into the existing explanation transformation without changing response
    generation.
- Expected token impact:
  - removes the raw issue JSON/comment metadata cost from Codex mode,
  - Codex still spends agent tokens on source search and file-window outputs,
  - targeted search/read rules should reduce generated/localization/baseline output volume.
- Known regression risks:
  - Codex may still run broad searches or read large files despite instructions,
  - source-only retrieval can miss verification-only test fixtures unless tests are explicitly
    needed and searched,
  - Codex usage numbers include full agent transcript/tool output and are not directly comparable
    to local retrieval LLM prompt totals; for pipeline-efficiency comparisons, use gross
    `input_tokens + output_tokens`, while cached/uncached splits are only billing or marginal-cost
    context.
- Real run comparison:
  - case: `microsoft-TypeScript-35468`, using the sanitized visible issue packet plus the selected
    TypeScript workspace; these are existing trace measurements, not a fresh rerun during this
    changelog edit,
  - `run-20260622T-codex-sanitized-02`: `coverage_status=strong`, `sufficient=true`, selected
    `watch.ts`, `program.ts`, `builderState.ts`, and `declarations.ts`; oracle overlap `1`
    implementation file (`builderState.ts`); usage `2,617,132` input, `2,523,648` cached input,
    `12,796` output, `6,720` reasoning output, `2,629,928` gross input plus output, and
    `106,280` uncached input plus output.
    Retrieval-stage elapsed time was `217.509s` (`3m38s`); full orchestration elapsed time was
    `240.151s` (`4m00s`).
  - `run-20260622T-codex-sanitized-03`: after adding explicit targeted-search/read and generated
    directory guards, `coverage_status=strong`, `sufficient=true`, selected `declarations.ts`,
    `builderState.ts`, `builder.ts`, `program.ts`, and `tsbuildPublic.ts`; oracle overlap `2`
    implementation files (`builderState.ts`, `builder.ts`); usage `1,210,174` input, `1,140,224`
    cached input, `11,630` output, `6,333` reasoning output, uncached input plus output
    `81,580`; gross input plus output for the direct retrieval-token comparison is `1,221,804`.
    Retrieval-stage elapsed time was `198.406s` (`3m18s`); full orchestration elapsed time was
    `225.423s` (`3m45s`).
- Quality notes:
  - the third run found the key builder files and produced an explanation with evidence refs and
    understanding checks,
  - the evidence is conceptually strong for the subsystem but still broader than the local retriever,
    which previously kept `builder.ts` at rank 5 while using far fewer retrieval tokens.
- Time notes:
  - Codex mode has no separate local index-build phase, but pays agent search/read time on each
    retrieval run,
  - use the exact per-run records above instead of comparing only the `3m18s-3m38s` span.

### Benchmark: Same-Case Workspace vs Codex Retrieval Records

- `microsoft-TypeScript-35468`:
  - Codex mode has no local index build.
  - Codex `run-20260622T-codex-sanitized-02`: retrieval/evidence discovery `217.509s`
    (`3m38s`), full orchestration `240.151s` (`4m00s`), gross input plus output `2,629,928`,
    uncached input plus output `106,280`.
  - Codex `run-20260622T-codex-sanitized-03`: retrieval/evidence discovery `198.406s`
    (`3m18s`), full orchestration `225.423s` (`3m45s`), gross input plus output `1,221,804`,
    uncached input plus output `81,580`.
  - Workspace `run-20260622T124352Z` with the existing index directory present: retrieval trace
    `149.854s` (`2m30s`), full orchestration `183.412s` (`3m03s`), retrieval LLM tokens `13,542`;
    trace events show CGC skipped the existing structural index, BM25 was reused, and workspace
    index reuse completed after `8.037s`.
  - Workspace first-run index prep for the same case remains separate: observed normal CGC indexing
    `1871.59s` (`31m12s`) and `SKIP_EXTERNAL_RESOLUTION=true` indexing `1070.79s` (`17m51s`);
    estimator output for the measured `207` graph-indexable file snapshot is normal `23m-42m` and
    skip-external `13m-24m`.
  - Short quality comparison: Codex run 03 had stronger oracle overlap (`2` implementation files)
    and `strong/sufficient=true`; the fresh workspace reuse run still found `builder.ts` in the top
    five but ended `partial/sufficient=false`, while prior workspace baselines were
    `strong/sufficient=true` with an average of `11,461` retrieval tokens.
- `microsoft-TypeScript-6307`:
  - Codex mode has no local index build.
  - Codex `run-20260622T130116Z`: retrieval/evidence discovery `90.071s` (`1m30s`), full
    orchestration `112.736s` (`1m53s`), gross input plus output `259,281`, uncached input plus
    output `28,369`.
  - Workspace first run `run-20260622T124840Z`: retrieval trace `548.390s` (`9m08s`), full
    orchestration `567.795s` (`9m28s`), retrieval LLM tokens `12,088`; observed index prep
    completed at `439.425s` (`7m19s`) from retrieval start.
  - Workspace prepared-index run `run-20260622T125817Z`: retrieval trace `127.620s` (`2m08s`), full
    orchestration `155.308s` (`2m35s`), retrieval LLM tokens `12,281`; trace events show index reuse
    completed after `2.740s`.
  - Short quality comparison: file overlap is not measurable for this question/usage case because
    its verification oracle intentionally lists no implementation, test, or documentation files;
    therefore both runs necessarily report `0` overlap. The workspace prepared run and Codex run
    both reported `strong/sufficient=true` based on their retrieved evidence, while quality should
    be judged here by agreement with the declaration-emit/public-API responsibility and hidden
    resolution rather than by file overlap.
- `microsoft-TypeScript-6`:
  - Codex mode has no local index build.
  - Codex `run-20260622T225727Z`: retrieval/evidence discovery `230.523s` (`3m51s`), full
    orchestration `270.608s` (`4m31s`), gross input plus output `1,784,170`, uncached input plus
    output `117,610`.
  - Workspace `run-20260622T230942Z`: retrieval trace `243.217s` (`4m03s`), full orchestration
    `276.302s` (`4m36s`), retrieval-stage LLM tokens `12,170` (`10,219` prompt, `1,951`
    completion, `2,304` cached prompt tokens). This comparison became valid only after fixing two
    local workspace regressions encountered during the rerun: the synthesis decision rename
    (`missing_areas` vs `missing_roles`) and a stale `_coverage_status(...)` call signature.
  - Short quality comparison: both runs ended `coverage_status=strong` and `sufficient=true`, and
    both reached implementation overlap `5`. Codex found a better pre-feature architecture path
    (`scanner.ts`, `utilities.ts`, `parser.ts`, `types.ts`, `checker.ts`), while workspace aligned
    more directly with the landed implementation oracle by surfacing `diagnosticMessages.json` and
    `declarationEmitter.ts` in the top five.
- Runner note:
  - `microsoft-TypeScript-6307` exposed a snapshot-resolution edge case where JSON null
    `commit_id` values became the string `"None"` and a missing historical event commit aborted the
    run; the runner now ignores null or locally unavailable event commits and falls back to the
    timestamp-based snapshot path.

### Changed: CGC 0.5.1 Upgrade And Complete-Index Guard

- Intended stage boundary:
  - keep CGC as the production structural backend after removing the experimental SCIP spike,
  - require a completed CGC marker before treating a repo-local Kuzu DB as reusable,
  - clean `cgc-kuzu`, `cgc-kuzu.wal`, and the completion marker when CodeRepoQA rebuilds indexes or CGC indexing fails.
- Expected quality impact:
  - avoids silently reusing timeout-created partial CGC databases,
  - makes failed structural indexing loud instead of letting later retrieval behave unpredictably.
- Expected token impact:
  - no retrieval-token increase on prepared indexes,
  - failed or missing CGC indexes now stop before expensive downstream retrieval instead of producing partial evidence from stale graph state.
- Known regression risks:
  - existing CGC databases created before this marker change must be rebuilt once,
  - clean full CGC indexing can still exceed the interactive timeout on moderately sized TypeScript snapshots.
- Measurement:
  - upgraded `codegraphcontext` from `0.4.11` to `0.5.1`,
  - active TypeScript snapshot with narrowed excludes still timed out after `600s` on clean CGC indexing:
    `run-20260622T000846Z`,
  - `SKIP_EXTERNAL_RESOLUTION=true` also timed out after `600s` with a clean Kuzu DB:
    `run-20260622T002314Z`,
  - a reuse run after a timeout-created partial DB completed but was not acceptable as a deterministic success:
    `run-20260622T003406Z`, `coverage_status=partial`, `sufficient=false`, oracle
    `src/compiler/builder.ts` at rank `5`.
- No-timeout follow-up measurement:
  - normal CGC completed indexing in `1871.59s` on the `microsoft-TypeScript-35468` snapshot after
    narrowed excludes:
    `run-20260622T012442Z`, retrieval `coverage_status=strong`, `sufficient=true`,
    oracle `src/compiler/builder.ts` at rank `5`, but explanation generation failed after retrieval
    because the model returned no valid understanding checks,
  - `SKIP_EXTERNAL_RESOLUTION=true` completed indexing in `1070.79s`:
    `run-20260622T020134Z`, retrieval `coverage_status=strong`, `sufficient=true`,
    oracle `src/compiler/builder.ts` at rank `5`, response generation succeeded,
  - this makes `SKIP_EXTERNAL_RESOLUTION` useful for elapsed time on this case, but still too slow
    for interactive indexing at about `18m`.
- Retrieval elapsed-time note:
  - the full CodeRepoQA retrieval trace for `run-20260622T012442Z` lasted `2099.987s`
    (`35m00s`) because it includes normal CGC indexing plus retrieval,
  - the full CodeRepoQA retrieval trace for `run-20260622T020134Z` lasted `1252.904s`
    (`20m53s`) because it includes `SKIP_EXTERNAL_RESOLUTION=true` CGC indexing plus retrieval,
  - these timings should not be compared as steady-state retrieval latency after an index is
    already prepared; they are first-run/index-build timings.
- Follow-up behavior:
  - index readiness now reports the CGC structural index as missing/stale unless `cgc-kuzu.complete.json` exists,
  - index estimates now include separate CGC structural time/risk fields in addition to BM25/Qdrant chunk estimates,
  - the CGC estimate is calibrated from the no-timeout TypeScript 35468 measurements and reports both
    normal CGC and `SKIP_EXTERNAL_RESOLUTION=true` ranges; for the measured `207` graph-indexable
    file snapshot it estimates normal `23m-42m` and skip-external `13m-24m`, covering the observed
    `31m` and `18m` runs.
- Workspace retrieval indexing estimate:
  - keep index preparation separate from retrieval-token comparisons: normal CGC indexing is
    estimated at `23m-42m` for the `microsoft-TypeScript-35468` snapshot after exclusions (`207`
    graph-indexable files), while `SKIP_EXTERNAL_RESOLUTION=true` is estimated at `13m-24m`,
  - observed index-build times were `1871.59s` (`31m12s`) and `1070.79s` (`17m51s`) respectively,
  - after the index exists, workspace retrieval should be measured separately from this upfront
    structural indexing cost.

## 2026-06-21

### Changed: CGC Ignore Handling For CodeRepoQA

- Intended stage boundary:
  - keep CodeRepoQA exclusions flowing through the same `.cgcignore` path used by normal workspace indexing,
  - apply repo-specific excludes before CGC graph indexing, BM25, and Qdrant indexing.
- Expected quality impact:
  - less noise from TypeScript fixture and generated-test folders,
  - more trustworthy CodeRepoQA runs because the test harness and UI use the same exclusion mechanism after config is passed in.
- Expected token impact:
  - lower indexing and retrieval token pressure for large repos by removing irrelevant candidate files before indexing.
- Known regression risks:
  - over-broad repo-specific excludes can hide useful test-only evidence,
  - the local CGC package patch is inside `.venv` and must be reapplied if the environment is rebuilt from scratch.
- Comparison method:
  - verify CGC discovery excludes configured subfolders on the active TypeScript snapshot,
  - verify an isolated CGC CLI index does not persist symbols from an ignored path.

### Verification: CGC Ignore Handling For CodeRepoQA

- Removed stale CGC DB directories/files from the main workspace, global CGC context, and testcase indexes.
- Confirmed only one `codegraphcontext` install is active: `.venv`, version `0.4.11`; no global Python import was found.
- Patched local CGC parser to strip a UTF-8 BOM before parsing `.cgcignore` patterns.
- Isolated CGC CLI proof:
  - `src/keep.ts` remained searchable,
  - `tests/cases/drop.ts` was not searchable after `.cgcignore` contained `tests/cases/`.
- Active TypeScript CodeRepoQA snapshot discovery:
  - first pass graph-indexable files: `537`,
  - final narrowed graph-indexable files: `207`,
  - final BM25/Qdrant document count: `13,378`,
  - `tests`, `lib`, `loc`, `scripts`, `src/testRunner`, `src/harness`, `src/lib`, and `src/loc`
    absent from CGC discovery.
- Clean rebuild attempts:
  - `run-20260621T152947Z`: failed on CGC timeout after `180s`,
  - `run-20260621T153424Z`: failed on CGC timeout after `600s`,
  - `run-20260621T154611Z`: failed on CGC timeout after `600s` with the narrowed exclude set.
- CGC timeout caveat:
  - despite the timeout, the produced repo-local Kuzu DB was queryable and found
    `createBuilderProgram` in `src/compiler/builder.ts`,
  - follow-up reuse run `run-20260621T155705Z` skipped the existing CGC DB, rebuilt BM25 and Qdrant,
    and completed retrieval with `coverage_status=strong`, `sufficient=true`.
- Successful reuse-run scorecard:
  - retrieved source files: `6`,
  - oracle overlap: `src/compiler/builder.ts` at rank `5`,
  - Qdrant collection:
    `guided_intelligence_retrieval_role_scoped__microsoft_typescript_35468__a27de1ce`,
  - Qdrant points: `13,378`.
- Automated tests:
  - `python -m py_compile services/retrieval/cgcignore.py services/retrieval/tools/cgc.py services/retrieval/server.py services/retrieval/workspace.py testing/codeRepoQA/run_case.py`
  - `python -m unittest tests.test_retrieval_server tests.test_workspace_retrieval`
  - 97 tests passed.
  - Later `python -m py_compile testing/codeRepoQA/run_case.py` passed after tightening TypeScript
    excludes and raising the CodeRepoQA CGC timeout to `600s`.

## 2026-06-20

### Added: Bounded LangGraph Connected-Source Context Stage

- Intended stage boundary:
  - run after deterministic prompt evidence and before Step 2 repository-context construction,
  - use enabled provider/source-key connector handles rather than source-category grouping,
  - let selected connected context refine code terms, files, symbols, and subqueries,
  - require explicit selected document IDs before connected text can become final evidence.
- Expected quality impact:
  - improve code retrieval for product-language prompts by translating live issue, PR, note, and
    management-tool context into compact code-retrieval signals,
  - reject irrelevant or stale provider text before it can steer code retrieval,
  - preserve code evidence as the authority for code-behavior claims.
- Expected token impact:
  - no added tokens when no connected source is selected,
  - approximately 2,000-2,600 graph tokens when live sources are queried in the measured TypeScript
    case,
  - selected connected excerpts can increase later Step 2 input in addition to graph tokens.
- Known regression risks:
  - broad provider searches can add latency and tokens even when all results are rejected,
  - provider AND-search behavior can miss relevant human text whose title has little prompt overlap,
  - stale or terminology-only text can misdirect code retrieval unless relevance, contribution,
    currentness, and confidence gates all hold,
  - graph LLM timeouts fail the stage explicitly rather than silently changing behavior.
- Comparison method:
  - two real no-source baselines,
  - irrelevant, helpful single-source, stale/conflicting, and combined-source TypeScript runs,
  - natural conversational fixtures in Obsidian, a GitHub issue, and a GitHub pull request,
  - compare run IDs, `coverage_status`, `sufficient`, retrieval tokens, graph tokens, connected IDs,
    and final code paths.

### Verification: Bounded LangGraph Connected-Source Context Stage

- Automated tests:
  - `python -m unittest tests.test_connected_context tests.test_mcp_connected_sources tests.test_retrieval_server tests.test_workspace_retrieval tests.test_coderepoqa_retrieval`
  - 129 tests passed.
- UI regression build:
  - `npm run web:build`
  - passed; this change has no new UI surface.
- No-source baselines:
  - `run-20260620T194600Z-87c934b6`: `strong`, `sufficient=true`, 11,452 retrieval tokens,
  - `run-20260620T195057Z-0c1b15b4`: `strong`, `sufficient=true`, 11,470 retrieval tokens,
  - no connected graph LLM calls or connected events in either run.
- Rejection checks:
  - `run-20260620T195721Z-8ad9b1a0`: irrelevant sources selected nothing; `strong`,
    `sufficient=true`, 14,011 retrieval tokens, 2,151 graph tokens,
  - `run-20260620T204228Z-b6abc84f`: stale/conflicting sources selected nothing; `strong`,
    `sufficient=true`, 13,995 retrieval tokens, 2,510 graph tokens.
- Helpful-source checks:
  - Obsidian `run-20260620T200036Z-2b26f442`: selected one note; 14,538 retrieval tokens,
  - GitHub issue `run-20260620T201944Z-aedc6d1e`: selected one issue; 14,533 retrieval tokens,
  - GitHub PR `run-20260620T202607Z-7e793a03`: selected one PR; 14,848 retrieval tokens,
  - combined final `run-20260620T205158Z-4d193726`: all three documents informed context, while
    the two-evidence cap retained the issue and PR; 15,439 retrieval tokens and 2,600 graph tokens.
- Failed experiments retained for diagnosis:
  - `run-20260620T195407Z-6ee8d055` exposed terminology-only over-selection and caused the
    contribution/code-signal gate,
  - `run-20260620T200440Z-0c8a63bc` failed explicitly on graph LLM timeout; retry succeeded,
  - `run-20260620T202931Z-607b47f1` exposed stale-context over-selection and caused the
    currentness/confidence gate.
- Quality conclusion:
  - all successful runs remained `coverage_status=strong` and `sufficient=true`,
  - all kept the same five final code paths: checker, diagnostics, emitter, parser, and types,
  - useful context improved query-plan specificity but not code-file recall for this explicit prompt,
  - a single useful source cost about 27% more retrieval tokens than baseline; combined sources cost
    about 35% more,
  - retain the bounded stage, but add an adaptive pre-query need gate before broadening evaluation.

## 2026-06-18

### Added: Protocol Relationship Graph Helper

- Intended stage boundary:
  - run after required-role recovery and before deterministic coverage/evidence selection,
  - keep relationship discovery in `services/retrieval/pipeline/protocol_graph.py`, separate from `workspace.py`,
  - extract concrete frontend API literals from accepted frontend candidates such as `requestJson<T>("/index/estimate")`, `fetch("/...")`, and `axios.get("/...")`,
  - rank extracted route literals against the target bucket query so issue-specific routes are tried before generic endpoints,
  - scan likely backend route/handler files for matching route string literals,
  - extract high-signal prompt/message literals such as `Error parsing expression` or `expects a method`,
  - scan likely diagnostics/parser/validator files for exact message fragments,
  - promote normal source-code `RetrievalCandidate` records with `retrieval_path=protocol_route_bridge` or `retrieval_path=protocol_message_bridge`.
- Expected quality impact:
  - improve UI-to-backend owner discovery when retrieval finds a frontend API wrapper but misses the server handler,
  - make string/protocol relationships visible even when CGC cannot infer the relationship from dynamic request wrappers or diagnostic string construction,
  - improve recovery for issue prompts whose exact error/warning text appears in parser, directive, checker, validator, or diagnostic files,
  - keep promotions explainable through exact literal/fragment matches instead of semantic guesswork.
- Expected token impact:
  - no extra LLM prompt tokens directly from the helper because it is deterministic,
  - possible indirect token increase when promoted relationship candidates give late synthesis/response generation more evidence to assess,
  - no embedding-token change because this uses local file scans over already-indexed workspace files.
- Known regression risks:
  - exact string matching will not resolve template-only routes or routes assembled entirely from variables,
  - diagnostic messages assembled from several string fragments can still be missed unless one stable fragment appears in the prompt,
  - broad API wrapper snippets can expose many routes; route ranking mitigates this but may still promote a nearby route group span,
  - message-literal scans are intentionally limited to diagnostics/parser/validator-like source paths to avoid turning every matching string into owner evidence.
- Comparison method:
  - focused unit coverage for typed frontend calls, backend route promotion, and prompt-message literal promotion,
  - real workspace pipeline runs against this repo with a UI `requestJson<IndexEstimate>("/index/estimate")` prompt,
  - real CodeRepoQA runs against TypeScript and Vue cases,
  - compare run IDs, coverage, sufficiency, selected evidence, protocol bridge events, tool calls, and observed OpenAI usage totals from trace `usage` fields.

### Verification: Protocol Relationship Graph Helper

- Focused tests:
  - `python -m unittest tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_protocol_relationship_bridge_promotes_matching_backend_handler tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_protocol_graph_discovers_ranked_route_relationship_candidate tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_protocol_graph_discovers_prompt_message_literal_candidate`
  - passed.
- Compile check:
  - `python -m py_compile services\retrieval\workspace.py services\retrieval\pipeline\protocol_graph.py tests\test_workspace_retrieval.py`
  - passed.
- Broader test note:
  - `python -m unittest tests.test_workspace_retrieval` still has an unrelated pre-existing failure in `test_role_retarget_queries_add_role_specific_entrypoint_terms`; expected query string contains `parser syntax tokens ...`, current output contains `input parsing request handling ...`.
- Real run comparison:
  - Before typed-route support:
    - run ID: `run-20260618T113308Z-route-bridge`
    - `coverage_status=partial`, `sufficient=False`
    - selected refs did not include `services/retrieval/server.py`
    - selected count: 7, tool calls: 289
    - observed OpenAI usage from traces: 11,683 prompt + 3,268 completion = 14,951 total tokens
  - After typed-route extraction, before route ranking:
    - run ID: `run-20260618T113646Z-route-bridge-v2`
    - `coverage_status=partial`, `sufficient=False`
    - promoted `repo-pre:services/retrieval/server.py:L825-L852`
    - route list started with generic `/health`, while the promoted span still contained `/index/estimate`
    - selected count: 4, tool calls: 478
    - observed OpenAI usage from traces: 19,677 prompt + 4,262 completion = 23,939 total tokens
  - Final route-ranked run:
    - run ID: `run-20260618T114148Z-route-bridge-v3`
    - `coverage_status=partial`, `sufficient=False`
    - bridge event promoted `repo-pre:services/retrieval/server.py:L825-L864`
    - ranked routes started with `/index/estimate`, then `/index/prepare`
    - final response evidence included `ui/src/api.ts`, `services/retrieval/server.py`, and `ui/src/App.tsx`
    - selected count: 5, tool calls: 485
    - observed OpenAI usage from traces: 17,643 prompt + 4,147 completion = 21,790 total tokens
  - Final extracted-helper run:
    - run ID: `run-20260618T172205Z-protocol-graph-final`
    - `coverage_status=partial`, `sufficient=False`
    - protocol event promoted `repo-pre:services/retrieval/server.py:L825-L864`
    - routes started with `/index/estimate`, then `/index/prepare`
    - selected count: 5, tool calls: 314
    - observed OpenAI usage from traces: 18,319 prompt + 4,298 completion = 22,617 total tokens
- TypeScript CodeRepoQA measurement:
  - run ID: `run-20260618T180628Z-protocol-graph-final`
  - `coverage_status=partial`, `sufficient=False`
  - selected refs included `src/compiler/types.ts`, `scanner.ts`, `parser.ts`, `diagnosticMessages.json`, and `emitter.ts`
  - protocol helper detected abstract-related missing diagnostic terms such as `cannot invoke abstract members through super`, but promoted no refs because those diagnostics do not exist in the pre-fix snapshot
  - selected count: 10, tool calls: 260
  - observed OpenAI usage from traces: 17,968 prompt + 4,583 completion = 22,551 total tokens
- Vue CodeRepoQA measurement:
  - initial protocol-message run ID: `run-20260618T184200Z-protocol-graph-final`
    - detected terms including `Error parsing expression` and `expects a method`, but promoted no refs because exact refs were already present or recovered elsewhere by that point,
    - final refs were weak for the desired parser/diagnostic owner mix in that run.
  - after allowing message edges to reuse a path already accepted under another role:
    - run ID: `run-20260618T185039Z-protocol-message-final`
    - `coverage_status=partial`, `sufficient=False`
    - final refs included `src/exp-parser.js:L29-L108`, `src/exp-parser.js:L73-L152`, and `src/directive.js:L81-L160`
    - diagnostics bucket was weak with `src/exp-parser.js:L73-L152` and `src/directive.js:L121-L200`
    - protocol event still promoted no new refs in this run because normal recovery already had the diagnostic owner refs before the bridge, but the focused unit test proves the message edge can promote the same pattern when missing
    - selected count: 10, tool calls: 307
    - observed OpenAI usage from traces: 17,919 prompt + 4,716 completion = 22,635 total tokens
- Quality notes:
  - route edges fixed the specific self-repo miss: backend route evidence now survives to final evidence for the UI route prompt,
  - TypeScript shows the helper does not hallucinate nonexistent abstract diagnostics; this is a useful no-promotion result,
  - Vue shows the next useful edge family is diagnostic/message ownership and possibly expression grammar/data-shape relationships; the current message edge is safe but did not materially improve the final run when normal recovery already found `exp-parser.js`,
  - sufficiency stayed false in all measured runs because missing/weak roles remain outside what exact protocol-string edges can solve alone,
  - this should remain an enrichment/helper stage, not a replacement for CGC/Qdrant/role validation.

## 2026-06-15

### Added: MCP Connected Source Adapter

- Intended stage boundary:
  - add MCP as a query-time connected-source adapter before Step 2 planning,
  - normalize MCP tool results into existing `ConnectedSourceDocument` records,
  - pass bounded connected-source snippets into Step 2 planning,
  - allow policy-approved, prioritized connected documents to become final evidence with `retrieval_path=connected_source`,
  - keep source-code/document retrieval on the existing CGC + Qdrant path,
  - keep MCP sources disabled unless `WorkspaceRetrievalConfig.mcp_connected_sources` is explicitly configured,
  - map MCP results into existing source categories such as `issue_tracker`, `pull_request`, and `notebooklm` rather than adding a generic evidence category.
- Expected quality impact:
  - make issue/PR-like external context visible to the planner through a common connector layer,
  - preserve existing code retrieval quality when no MCP source is configured,
  - improve source extensibility for GitHub and future sources without coupling retrieval to one provider.
- Expected token impact:
  - no retrieval token change when no MCP source is configured,
  - small planner prompt increase when MCP documents are returned because connected-source IDs, titles, metadata, and bounded snippets become visible before Step 2,
  - no Qdrant embedding/token impact because MCP documents are not indexed in this first pass.
- Known regression risks:
  - MCP result normalization is schema-flexible but shallow, so provider-specific fields may need adapter-specific mappings later,
  - query-time MCP calls can add latency or fail independently of local retrieval,
  - connected documents can now become evidence, but they do not satisfy code-owner coverage gates; this avoids letting external discussion replace required source-code evidence.
- Comparison method:
  - focused unit tests use a fake stdio MCP server to verify JSON-RPC tool calls, normalization, source-policy filtering, registry queryability, and trace logging,
  - broader real pipeline token comparison is not meaningful yet because the adapter is disabled by default and no real GitHub MCP source is configured for the benchmark runs.

### Verification: MCP Connected Source Adapter

- Focused tests:
  - `python -m unittest tests.test_mcp_connected_sources`
  - passed with fake stdio MCP source returning an issue-like result.
- Compile check:
  - `python -m py_compile services\retrieval\config.py services\retrieval\workspace.py services\retrieval\step2\step2.py services\retrieval\mcp\stdio_client.py services\retrieval\mcp\adapters.py tests\test_mcp_connected_sources.py`
  - passed.
- Real retrieval-token measurement:
  - not run for this slice because no MCP source is configured by default, so existing benchmark pipeline behavior and retrieval token totals should remain unchanged.
  - when a real GitHub MCP source is configured, the next comparison should record the run ID, `coverage_status`, `sufficient`, retrieval token totals, returned MCP source refs, and any final-evidence changes.

## Sources Used During This Retrieval Rework

- OrcaLoca: An LLM Agent Framework for Software Issue Localization  
  https://arxiv.org/abs/2502.00350  
  Used for action decomposition, priority scheduling, and pruning after broader exploration.
- CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching  
  https://arxiv.org/abs/2503.22424  
  Used for broad file-level exploration followed by deeper function/snippet analysis with graph-guided search.
- Question Decomposition for Retrieval-Augmented Generation  
  https://arxiv.org/abs/2507.00355  
  Used for per-subquery retrieval, then merge/rerank instead of a single flat candidate pool.
- LocAgent: Graph-Guided LLM Agents for Code Localization  
  https://aclanthology.org/2025.acl-long.426/  
  Used for graph-guided multi-granularity code localization ideas.
- GraphLocator: Graph-guided Causal Reasoning for Issue Localization  
  https://arxiv.org/abs/2512.22469  
  Used for graph-guided expansion from symptom/support files toward likely owner files.
- RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation  
  https://aclanthology.org/2023.emnlp-main.151/  
  Used for the idea that first-pass retrieved code should seed a second retrieval pass with code-native terms.
- On The Importance of Reasoning for Context Retrieval in Repository-Level Code Editing  
  https://arxiv.org/abs/2406.04464  
  Used for the decision to keep deterministic/tool-based sufficiency checks instead of trusting LLM judgment alone.
- SweRank: Software Issue Localization with Code Ranking  
  https://arxiv.org/abs/2505.07849  
  Used for retrieve-then-rerank framing instead of trusting first-pass retrieval alone.
- SaraCoder: Orchestrating Semantic and Structural Cues for Profit-Oriented Repository-Level Code Completion  
  https://arxiv.org/abs/2508.10068  
  Used for diversity-aware reranking so redundant nearby files do not monopolize results.
- GraphER: An Efficient Graph-Based Enrichment and Reranking Method for Retrieval-Augmented Generation  
  https://arxiv.org/abs/2603.24925  
  Used for the idea that graph structure is most helpful as reranking/enrichment after candidate generation.
- Qdrant Documentation  
  https://qdrant.tech/documentation/  
  Used for collection setup, metadata filtering, and search behavior.
- Qdrant Hybrid Search / Query API  
  https://qdrant.tech/articles/hybrid-search/  
  Used for dense+sparse hybrid retrieval design.
- Qdrant Hybrid Search Tutorial  
  https://qdrant.tech/documentation/tutorials/hybrid-search-fastembed/  
  Used for practical hybrid search structure and fusion concepts.
- FAISS official repository  
  https://github.com/facebookresearch/faiss  
  Used during evaluation of local dense retrieval vs Qdrant-backed hybrid retrieval.
- Analytics Vidhya, "Choosing the Right Vector Database for RAG and AI Applications"  
  https://www.analyticsvidhya.com/blog/2026/06/vector-database-comparison/  
  Used for the distinction between fast vector search, filtering, and the cost/quality trade-offs of vector database infrastructure.
- Outcome School, "How does a Reranker work?"  
  https://outcomeschool.com/blog/how-does-a-reranker-work  
  Used for the retrieve-then-rerank framing: broad retrieval first, then a more precise relevance pass over a smaller candidate set.
- Pinecone, "Rerankers and Two-Stage Retrieval"  
  https://www.pinecone.io/learn/series/rag/rerankers/  
  Used for the two-stage retrieval principle: retrieve broadly with a cheaper first-stage system, then rerank only a narrowed candidate set.
- MongoDB, "What are Rerankers?"  
  https://www.mongodb.com/resources/basics/artificial-intelligence/reranking-models  
  Used for the explicit cost warning that rerankers process query-document pairs at query time, so candidate count directly drives latency and token cost.

## 2026-06-13

### Changed

- Added an owner-artifact planning split to Step 2:
  - `surface_context_terms` describe the visible API/directive/error surface,
  - `owner_artifact_terms` describe the deeper rule/parser/validator/emitter/resolver artifact,
  - `owner_subqueries` are preferred for owner search,
  - `support_subqueries` remain bridge/context searches.
- Added generic owner-artifact normalization:
  - phrases like `expression parsing` and `Error parsing expression` can derive `expression parser`,
  - owner path matching now tolerates compact/stemmed file names such as `exp-parser.js` for `expression parser`.
- Added JS/TS relationship expansion:
  - explicit `import`, `export ... from`, `require(...)`, and triple-slash references are scanned,
  - extensionless local references resolve to source files using the importing file's extension first, then common TS/JS/JSON extensions.
- Added a final evidence handoff guard:
  - line-level refs accepted by the latest synthesis decision can be materialized into final evidence when they were accepted by the assessor but missed by bucket selection.

### Verification

- Corrected Vue baseline before this owner-artifact pass:
  - `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T221251Z`
  - oracle files: `src/exp-parser.js`, `test/unit/specs/exp-parser.js`
  - retrieved files: `src/directives/on.js`, `src/text-parser.js`, `src/directive.js`, `src/compiler.js`
  - `overlap_count=0`
  - `coverage_status=partial`
  - `sufficient=False`
  - retrieval tokens: `55638`
- Intermediate Vue owner-artifact runs:
  - `run-20260613T083214Z`: `overlap_count=0`, retrieval tokens `62950`
  - `run-20260613T083720Z`: `overlap_count=0`, retrieval tokens `67826`
  - `run-20260613T084210Z`: internally accepted `src/exp-parser.js:L73-L152`, but final evidence still dropped it; retrieval tokens `51306`
- Final Vue run after accepted-line-ref evidence handoff:
  - `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T084723Z`
  - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`, `src/exp-parser.js`, `src/directives/index.js`
  - `overlap_files=["src/exp-parser.js"]`
  - `overlap_count=1`
  - `coverage_status=partial`
  - `sufficient=False`
  - retrieval tokens: `71087`
- TypeScript guard run:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T085108Z`
  - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
  - `overlap_count=0`
  - `coverage_status=partial`
  - `sufficient=False`
  - retrieval tokens: `54862`

### Conclusion

- The owner-artifact split plus relationship expansion is directionally useful: the corrected Vue case now reaches and returns the true owner file `src/exp-parser.js`.
- It is not sufficient yet: Vue remains `partial / sufficient=False`, and token cost increased versus the corrected baseline.
- The next fix should reduce surface-role noise after owner-artifact evidence appears, especially noisy `model.js`/`emitter.js` evidence that competes with `exp-parser.js`.

### Changed: Lower-Cost Role Retrieval Restructure

- Intended stage boundary:
  - keep the Step 2 retrieval plan LLM,
  - replace per-role helper-query LLM calls with deterministic role/query packages,
  - replace owner-declaration selector LLM calls with deterministic declaration and lexical span refinement,
  - keep one compact late assessor as the only LLM gate after candidate gathering,
  - let accepted full-file owner artifacts trigger path-scoped local recovery rather than broad follow-up search.
- Expected quality impact:
  - preserve owner-file discovery for Vue (`src/exp-parser.js`),
  - preserve the previously strong TypeScript abstract-class result,
  - reduce noisy surface evidence by making late synthesis see snippets rather than redundant file artifacts.
- Expected token impact:
  - remove helper-query and owner-declaration selector prompt volume,
  - reduce late-assessor prompt size with a compact retrieval intent,
  - target retrieval usage closer to focused manual inspection than the previous 55k-71k runs.
- Known regression risks:
  - deterministic declaration selection can miss cases where only an LLM recognizes the owner declaration,
  - late-assessor decisions can still over-prioritize surface roles,
  - Vue sufficiency remains unstable when diagnostic evidence is found but labeled secondary.
- Comparison method:
  - reran the real `testing\codeRepoQA\run_case.py run-case` pipeline for Vue issue 242 and TypeScript issue 6 after each behavior slice,
  - compared `coverage_status`, `sufficient`, retrieved source files, retrieval LLM call counts, and total retrieval tokens from actual trace usage.

### Verification: Lower-Cost Role Retrieval Restructure

- Deterministic helper-query package:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T093028Z-det-helper`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `23 / 39162`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T093317Z-det-helper`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `14 / 46296`
- Snippet-grounded synthesis input:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T093931Z-det-helper-grounded-synth`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `22 / 38473`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T094427Z-det-helper-grounded-synth`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `6 / 23575`
- Path-scoped late recovery for accepted file/artifact candidates:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T102835Z-det-helper-file-recovery`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/emitter.js`, `src/exp-parser.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `17 / 43343`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T103438Z-det-helper-file-recovery`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `6 / 23745`
- Compact late-assessor intent:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T104358Z-compact-assessor`
    - retrieved files: `src/directives/model.js`, `src/exp-parser.js`, `src/emitter.js`, `src/text-parser.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `12 / 25634`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T105041Z-compact-assessor`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `7 / 22162`
- Deterministic-only declaration selection:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T111911Z-det-decls`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 16444`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T113138Z-det-decls`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14709`
- Clearing `file_candidate` metadata from materialized spans:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T210112Z-span-metadata-fix`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/exp-parser.js`, `src/emitter.js`, `src/directive.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 15780`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T210938Z-span-metadata-fix`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 14389`
- Assessor-accepted required-role snippets can satisfy the deterministic gate:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T211351Z-assessor-strong-gate`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/exp-parser.js`, `src/emitter.js`, `src/deps-parser.js`, `src/directive.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `4 / 25504`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T211914Z-assessor-strong-gate`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14284`
- Rejected experiment: pre-assessment materialization of accepted full-file candidates into local spans:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T215553Z-assessment-spans`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`, `src/compiler.js`, `src/directive.js`, `src/exp-parser.js`, `src/filters.js`, `src/deps-parser.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `4 / 26030`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T215857Z-assessment-spans`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14421`
  - conclusion: this experiment was reverted because it made Vue noisier without improving sufficiency.

### Conclusion: Lower-Cost Role Retrieval Restructure

- Kept the low-cost structure through the assessor-strong-gate slice.
- Compared to the high-token 2026-06-13 baseline:
  - Vue: `71087 -> 25504` retrieval tokens while still returning `src/exp-parser.js`; quality remains `partial / sufficient=False`.
  - TypeScript: `54862 -> 14284` retrieval tokens and improves to `strong / sufficient=True`.
- The remaining Vue issue is not broad retrieval volume; the owner file is present. The remaining failure is ranking/sufficiency judgment around the exact directive validation and diagnostics evidence.

### Changed: Compact Late Assessor With Deterministic Pre-Gate

- Intended stage boundary:
  - keep planner LLM unchanged,
  - allow the existing deterministic coverage gate to synthesize an accepted decision before calling the late assessor when all required roles are already locally strong,
  - reduce late-assessor payload size when the assessor is still needed,
  - preserve accepted full-file owner artifacts by allowing them to materialize into local spans even when the assessor also lists the file artifact as rejected.
- Expected quality impact:
  - preserve TypeScript `strong / sufficient=True`,
  - preserve Vue return of `src/exp-parser.js`,
  - avoid treating contradictory accepted/rejected file-level assessor output as a reason to drop concrete diagnostic spans.
- Expected token impact:
  - skip late-assessor calls in cases already proven by deterministic coverage,
  - reduce every remaining late-assessor prompt by sending fewer helper queries, refs, and shorter snippet previews.
- Known regression risks:
  - too-small assessor previews can hide the exact line that lets the assessor accept a role,
  - accepting file-level artifacts for span expansion can add secondary evidence that the assessor did not fully endorse,
  - the deterministic pre-gate may not fire often until earlier local role statuses become stronger before late assessment.
- Comparison method:
  - reran the real `run-case` pipeline once on Vue issue 242 and TypeScript issue 6 for each slice,
  - compared coverage, sufficiency, retrieved files, LLM calls, and retrieval tokens from trace usage.

### Verification: Compact Late Assessor With Deterministic Pre-Gate

- Deterministic pre-gate only:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T090131Z-det-pre-gate`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/exp-parser.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 16149`
    - `late_assessor_skipped` did not fire; token reduction came from the run path requiring fewer assessor passes than the previous kept Vue run.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T090347Z-det-pre-gate`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14553`
    - `late_assessor_skipped` did not fire.
- Compact assessor payload only:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T090855Z-compact-assessor-payload`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `4 / 20640`
    - regression: `src/exp-parser.js` was lost from final retrieved files.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T091127Z-compact-assessor-payload`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 12115`
  - conclusion: compact payload alone was not kept without the accepted-file span fix because Vue lost owner diagnostic evidence.
- Compact assessor payload plus accepted-file span recovery:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T091458Z-accepted-file-span-compact`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/exp-parser.js`, `src/emitter.js`, `src/directive.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 13790`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T091654Z-accepted-file-span-compact`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 12075`

### Conclusion: Compact Late Assessor With Deterministic Pre-Gate

- Kept compact late-assessor payload plus accepted-file span recovery.
- Compared to the previous kept assessor-strong-gate slice:
  - Vue: `25504 -> 13790` retrieval tokens while preserving `src/exp-parser.js`; quality remains `partial / sufficient=False`.
  - TypeScript: `14284 -> 12075` retrieval tokens while preserving `strong / sufficient=True`.
- Compared to the high-token 2026-06-13 baseline:
  - Vue: `71087 -> 13790`.
  - TypeScript: `54862 -> 12075`.
- The deterministic pre-gate is present but did not fire in these two benchmark runs; the measured win came from smaller assessor payloads and preserving line-span recovery for accepted file artifacts.

### Changed: Required Evidence Guard For Final Explanations

- Intended stage boundary:
  - keep retrieval and final explanation generation separate,
  - identify high-priority final-answer evidence from selected evidence using generic local predicates,
  - pass those anchors to the explanation generator as `required_evidence`,
  - validate visible Markdown citation coverage after generation and append a short grounded note only when a required anchor is still not visibly cited.
- Expected quality impact:
  - keep the beginner-friendly narrative style of `explanation_markdown_v2`,
  - prevent exact diagnostic or direct error-path evidence from being retrieved but omitted from the final answer,
  - avoid redundant repair sections when an overlapping same-file citation already covers the required evidence.
- Expected token impact:
  - small response-generation prompt increase from the added `required_evidence` payload,
  - no intended retrieval token increase.
- Known regression risks:
  - if a required anchor is too broad, the visible repair section can make an otherwise smooth answer feel bolted on,
  - overlapping citation detection handles line ranges, but not semantic equivalence across different files.
- Comparison method:
  - reran the real `run-case` pipeline once on Vue issue 242 and TypeScript issue 6,
  - inspected final `response_payload.content` and `used_evidence_refs`,
  - confirmed Vue visibly cites `src/exp-parser.js` and TypeScript remains coherent without an unnecessary repair section.

### Verification: Required Evidence Guard For Final Explanations

- First required-evidence response guard:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T183314Z-required-evidence-response`
    - `coverage_status=partial`, `sufficient=False`
    - final `used_evidence_refs` included `repo-pre:src/exp-parser.js:L73-L152`
    - final answer mentioned `exp-parser.js`, but visible citation handling still needed tightening.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T183520Z-required-evidence-response`
    - `coverage_status=strong`, `sufficient=True`
    - regression: an unnecessary `Evidence Not To Miss` repair section was appended for an overlapping diagnostics range.
- Visible citation coverage guard:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T183857Z-visible-required-evidence`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 13193`
    - final `used_evidence_refs`: `repo-pre:src/exp-parser.js:L73-L152`, `repo-pre:src/directive.js:L81-L160`
    - final answer visibly cites `src/exp-parser.js:L73-L152`, preserving the strongest diagnostic anchor.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T184102Z-visible-required-evidence`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 12005`
    - final answer remains a coherent beginner-friendly overview and no longer appends a redundant repair section.

### Conclusion: Required Evidence Guard For Final Explanations

- Kept the visible required-evidence guard.
- The Vue answer now uses and visibly cites `src/exp-parser.js:L73-L152`, which contains the reported `Error parsing expression` path.
- TypeScript remains `strong / sufficient=True` and keeps a normal narrative explanation without a forced addendum.

## 2026-06-12

### Changed

- Fixed CodeRepoQA verification for cases whose fixing commit is present in issue `events` but not in `fixed_by`.
  - `testing/codeRepoQA/run_case.py` now:
    - still prefers `fixed_by` when present,
    - keeps timestamp-based snapshot resolution when that snapshot is an ancestor of the referenced event commit,
    - falls back to the referenced event commit's parent when no coherent timestamp snapshot exists,
    - builds oracle files from that event commit only when the resolver used `event_commit_parent`.
  - This preserves the TypeScript snapshot path while correcting the Vue issue 242 snapshot/oracle.
- Replaced per-candidate snippet refinement with grouped `(role, file)` refinement in:
  - `services/retrieval/pipeline/refinement.py`
  - `services/retrieval/workspace.py`
- The snippet stage now:
  - accumulates file-local evidence across follow-up hits,
  - builds one compact declaration shortlist per grouped role/file pass,
  - runs owner-declaration selection once per grouped pass,
  - expands declaration and lexical spans locally before validation.
- Tightened grouped declaration extraction and scoring:
  - only real declaration-shaped lines are considered in `.ts/.js` files,
  - `.json` files no longer fabricate declaration candidates,
  - role-shaped names are favored more strongly during grouped shortlist scoring,
  - raw support snippets are no longer carried through unless they stay close to shortlisted declarations.

### Added

- Added `services/retrieval/docs/decisions/grouped_role_file_refinement_pipeline.md` to document:
  - the token/quality problem in the old snippet stage,
  - the grouped role-file refinement design,
  - how iterative mutation is preserved without repeated full declaration prompts.

### Verification

- TypeScript grouped-refinement verification run:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T020815Z`
  - model: `gpt-4.1-mini-2025-04-14`
  - retrieval result: `coverage_status=strong`, `sufficient=True`, `evidence_count=9`
  - retrieval LLM calls: `13`
  - owner-declaration selector calls: `5`
  - retrieval tokens:
    - `prompt_tokens=30270`
    - `completion_tokens=2046`
    - `total_tokens=32316`
  - compared to the previous current version (`run-20260611T142742Z`):
    - `total_tokens=62007 -> 32316`
    - token delta: `-29691`
- TypeScript grouped-refinement repeat runs after the stabilization pass:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T172412Z`
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T172630Z`
  - both runs: `coverage_status=strong`, `sufficient=True`, `evidence_count=9`
  - retrieval tokens:
    - `29148`
    - `29004`
  - owner-declaration selector calls:
    - `3`
    - `3`
  - compared to the previous current version (`run-20260611T142742Z`):
    - token deltas: `-32859`, `-33003`
- Experiment: deterministic path-only owner resolution before grouped snippet refinement.
  - attempted shape:
    - rerank required-role buckets by scored owner paths before `_refine_selected_role_buckets(...)`,
    - pick `1-2` owner files per role from the evaluated path pool,
    - seed grouped snippet refinement only from those routed owner files.
  - Vue comparison:
    - baseline: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T190155Z`
    - experimental: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T190622Z`
    - result:
      - `coverage_status` stayed `partial`
      - `sufficient` stayed `False`
      - retrieval tokens dropped: `66463 -> 57830`
      - owner-routing fired for all five required roles, but still misrouted role ownership
  - TypeScript regression check:
    - experimental run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T191029Z`
    - result:
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens dropped further to `27045`
  - conclusion:
    - cheap path-only owner routing is not safe enough to keep,
    - it can lower token cost, but without function/declaration-level ownership evidence it redirects stable cases onto the wrong files,

    - the live hook was reverted.
- Experiment: declaration-level owner boost during responsibility reranking.
  - attempted shape:
    - extract real declarations from evaluated candidate files,
    - score declaration names and previews against the role and issue terms,
    - add a responsibility-rerank bonus instead of hard-filtering files,
    - let grouped snippet refinement continue from the newly ordered bucket.
  - Vue comparisons:
    - baseline: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T190155Z`
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens: `66463`
    - first declaration-boost run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T210721Z`
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens: `66808`
    - tightened declaration-boost run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T211138Z`
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens: `68764`
  - conclusion:
    - declaration-level evidence is the right kind of signal, but a deterministic boost alone is too noisy,
    - body-term matches still over-promote adjacent helpers such as DOM/component utilities,
    - token cost rose without improving sufficiency,
    - the live behavior was disabled.
- Corrected Vue verification rerun after the event-commit oracle fix:
  - run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T221251Z`
  - resolution:
    - `strategy=event_commit_parent`
    - `repo_pre_commit=bab4829f0079f0fd6f95eb1700c2e277429495e8`
    - event commit: `e422d959452332862a3ea9d70c58bccc475daccb`
  - oracle files:
    - `src/exp-parser.js`
    - `test/unit/specs/exp-parser.js`
  - retrieved source files:
    - `src/directives/on.js`
    - `src/text-parser.js`
    - `src/directive.js`
    - `src/compiler.js`
  - result:
    - `coverage_status=partial`
    - `sufficient=False`
    - `overlap_count=0`
    - retrieval tokens: `55638`
  - conclusion:
    - previous Vue analysis used the wrong snapshot/oracle,
    - the real Vue failure is missing `src/exp-parser.js` as final evidence,
    - previous codegen/html-parser owner-routing experiments should not be retried as-is.
- TypeScript guard rerun after the verification fix:
  - run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T221554Z`
  - resolution stayed timestamp-based:
    - `strategy=latest_commit_before_created_at`
    - `repo_pre_commit=455364cf5a2e4f9cece69599475677bb41e2ac36`
  - oracle stayed comment-derived rather than event-commit-derived:
    - `event_commit=False`
    - `oracle_file_count=4`
  - result:
    - `coverage_status=partial`
    - `sufficient=False`
    - retrieval tokens: `53796`
  - conclusion:
    - the verification fix did not move the TypeScript snapshot/oracle onto the event commit,
    - the retrieval result itself remains run-unstable and should be treated separately from this verification fix.

## 2026-06-11

### Added

- Added `services/retrieval/corrected_retrieval_pipeline.md` as a cleaned-up description of the intended retrieval shape: owner-first, snippet-grounded, support-later.
- Added `services/retrieval/corrected_retrieval_pipeline_mapping.md` to map that corrected pipeline back onto the current code paths and current stage boundaries.
- Added LLM-assisted owner-declaration selection inside winning files:
  - `services/retrieval/workspace_llm.py::select_owner_declarations_with_llm(...)`
  - `services/retrieval/pipeline/snippet_level.py::declaration_candidates_for_llm(...)`
  - `services/retrieval/workspace.py::_select_owner_declaration_candidate(...)`

### Changed

- Tightened required-role refinement to behave more like the intended owner-first pipeline instead of broadening all roles equally from the start:
  - required roles are now ranked into focused owner candidates first,
  - supporting expansion is deferred until focused owner grounding is confirmed,
  - weak required buckets are recovered before broad support expansion continues.
- Changed late snippet recovery to search inside accepted owner files first before spending the initial refinement budget on broad global snippet recovery.
- Preserved direct owner snippet candidates during file preparation instead of collapsing them back into file-only state before later refinement.
- Refined owner-file local span selection so deterministic lexical windows now compete with an LLM-picked declaration candidate inside the same file, instead of relying only on broad window scoring.
- Removed one incorrect special case where `validation_checking` reference expansion was allowed to draw from all prepared buckets rather than its own bucket.
- Reduced hardcoded retrieval bias in role-completion scoring:
  - removed the local compiler-shaped keyword/path tables from `services/retrieval/role_completion/scoring.py`,
  - switched that scorer to shared role semantics from `services/retrieval/role_specs.py` instead of per-file TypeScript-specific string lists.
- Improved in-file scoring to weight prompt-specific terms more heavily than generic role vocabulary when choosing a span inside a selected owner file.

### Verification

- Final verified TypeScript case run after the owner-first/snippet-grounding changes:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260610T232007Z`
  - `coverage_status=strong`
  - `sufficient=True`
  - `evidence_count=8`
- Final required-role evidence in that run:
  - `representation`: `src/compiler/types.ts:L754-L833`, `src/compiler/types.ts:L676-L755`
  - `input_parsing`: `src/compiler/parser.ts:L2174-L2253`
  - `validation_checking`: `src/compiler/checker.ts:L4340-L4419`
  - `diagnostics`: `src/compiler/diagnosticMessages.json:L961-L1040`, `src/compiler/diagnosticMessages.json:L993-L1072`
  - `behavior_output`: `src/compiler/emitter.ts:L529-L608`, `src/compiler/emitter.ts:L518-L597`
- Token usage from the successful retrieval trace with direct OpenAI `gpt-4.1-mini`:
  - `prompt_tokens=34030`
  - `completion_tokens=3368`
  - `total_tokens=37398`

### Cost Tracking

- Current TypeScript retrieval baseline before the new cost-cutting experiments:
  - run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T084358Z`
  - model: `gpt-4.1-mini-2025-04-14`
  - retrieval result: `coverage_status=strong`, `sufficient=True`, `evidence_count=9`
  - retrieval LLM calls: `72`
  - retrieval tokens:
    - `prompt_tokens=249155`
    - `completion_tokens=6394`
    - `total_tokens=255549`

### Experiment Log

- Experiment 1: cache repeated owner-declaration selections within a single retrieval run.
  - code change:
    - `services/retrieval/workspace.py`
    - added a strict per-run cache for `_select_owner_declaration_candidate(...)`, keyed by the exact LLM selector payload
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T092300Z`
  - measured effect:
    - retrieval LLM calls: `72 -> 57`
    - retrieval tokens: `255549 -> 204113`
    - token delta: `-51436` total retrieval tokens
    - cache hits observed: `32`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `behavior_output` widened from `src/compiler/emitter.ts:L518-L597` to `src/compiler/emitter.ts:L2024-L2103`
    - the cache saved cost, but it also locked repeated in-file declaration picks early enough that later retries no longer had a chance to recover to the tighter snippet choices
- Experiment 2: skip the second late LLM bucket assessment when post-recovery deterministic coverage looked sufficient.
  - code change:
    - `services/retrieval/workspace.py`
    - tried short-circuiting the second `_synthesize_role_buckets(...)` call after weak-role recovery
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T093522Z`
  - measured effect:
    - retrieval LLM role-bucket assessments: `2 -> 3`
    - retrieval tokens: `255549 -> 260590`
    - token delta: `+5041` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - conclusion:
    - this shortcut did not trigger on the intended path because post-recovery deterministic coverage still was not satisfied
    - the run instead drifted into an extra late assessment and ended worse, so this experiment was reverted
- Experiment 3: exact helper-query reuse inside a single run.
  - code change:
    - `services/retrieval/workspace.py`
    - tried caching `generate_role_helper_queries_with_llm(...)` results by exact `(role, query, retrieval-plan payload)` identity
  - verification run:
    - first attempt failed with an OpenAI read timeout and correctly surfaced the runtime error with no fallback
    - successful retry: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T095113Z`
  - measured effect:
    - helper-query cache hits observed: `0`
    - helper-query LLM calls stayed at `5`
    - retrieval result on the retry was `coverage_status=partial`, `sufficient=False`
  - conclusion:
    - on this case, helper-query generation already happens only once per required role, so exact reuse does not activate
    - this experiment does not reduce cost on the current TypeScript path and was reverted
- Experiment 4: shrink owner-declaration LLM shortlist from `18` candidates to `12`.
  - code change:
    - `services/retrieval/pipeline/snippet_level.py`
    - reduced `declaration_candidates_for_llm(..., limit=18)` to `limit=12`
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T100117Z`
  - measured effect:
    - owner-declaration candidate payload: `18 -> 12` per call
    - owner-declaration LLM calls: `64 -> 96`
    - owner-declaration retrieval tokens: `232642 -> 248175`
    - total retrieval tokens: `255549 -> 271705`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `input_parsing` shifted from `src/compiler/parser.ts:L2174-L2253` to `src/compiler/parser.ts:L1928-L2007`
    - `diagnostics` shifted from `src/compiler/diagnosticMessages.json:L969-L1048` and `L989-L1068`
      to `L958-L1037` and `L966-L1045`
  - conclusion:
    - shrinking the shortlist reduced per-call payload but changed the retrieval path enough to trigger more owner-declaration selection calls overall
    - net cost increased and result quality fell, so this experiment was reverted
- Experiment 5: remove explanation text from owner-declaration selection responses and return ids only.
  - code change:
    - `services/retrieval/workspace_llm.py`
    - changed `workspace_owner_declaration_selection` schema from `{id, reason}` to `{id}` only
  - verification run:
    - first attempt failed with an OpenAI read timeout and correctly surfaced the runtime error with no fallback
    - successful retry: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T102023Z`
  - measured effect:
    - owner-declaration completion tokens: `4743 -> 1440`
    - owner-declaration total tokens: `232642 -> 284715`
    - owner-declaration calls: `64 -> 80`
    - total retrieval tokens: `255549 -> 307215`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` disappeared from final evidence
    - `representation` drifted to `src/compiler/types.ts:L754-L833`
    - `behavior_output` drifted to `src/compiler/emitter.ts:L2077-L2156` and `L2024-L2103`
  - conclusion:
    - even though completion text became cheaper, changing the response contract altered model behavior enough to increase owner-selection retries and worsen final evidence
    - this experiment was reverted
- Experiment 6: skip owner-declaration LLM selection for `behavior_output` and rely on lexical in-file refinement only.
  - code change:
    - `services/retrieval/workspace.py`
    - bypassed `_select_owner_declaration_candidate(...)` for `behavior_output` only
  - motivation:
    - in the strong baseline run, `behavior_output` was the only role where the top lexical declaration matched the LLM first choice in all `16/16` observed calls
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T102907Z`
  - measured effect:
    - skipped owner-selection calls: `16`
    - but owner-declaration LLM calls overall still rose: `64 -> 144`
    - owner-declaration total tokens: `232642 -> 365835`
    - total retrieval tokens: `255549 -> 403528`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `representation` drifted to `src/compiler/types.ts:L754-L833` and `L715-L794`
    - `behavior_output` drifted to broader emitter spans `src/compiler/emitter.ts:L2077-L2156` and `L2026-L2105`
  - conclusion:
    - local lexical agreement on a single role was not enough; removing LLM selection there changed later recovery behavior and made the whole run much more expensive
    - this experiment was reverted

### Structural Conclusion After Experiments 1-6

- The dominant cost remains `workspace_owner_declaration_selection`.
- The repeated experiments show that this stage is path-sensitive: even small local contract or gating changes cause different later refinement loops and often increase total owner-selection calls instead of reducing them.
- A final baseline analysis before further edits showed:
  - exact duplicate owner-selection request shapes do exist, but caching them earlier already harmed recovery quality
  - lexical top-1 agreement with the LLM is weak for most roles:
    - `behavior_output`: lexical top-1 matched the LLM first choice in `16/16` calls
    - `diagnostics`: `10/16`
    - `input_parsing`: `0/16`
    - `representation`: `0/16`
  - lexical and LLM spans almost never coincide directly in the strong run, so a broader lexical prefilter is not justified as a safe micro-optimization
- Practical conclusion:
  - no further small local token-cutting tweak is currently justified by the measured signal
  - the next meaningful reduction in cost requires a larger redesign of repeated owner-file refinement rounds rather than another isolated patch around the current selector

### Structural Redesign Direction

- The measured system flaw is that the current pipeline invokes the expensive owner-declaration selector as a repeated per-candidate operation.
- This violates the two-stage retrieval pattern from the reranking references:
  - the cheap first stage should gather and narrow candidates,
  - the expensive relevance model should run only after candidates are grouped and reduced,
  - reranker cost grows with query-candidate pairs, so repeated per-candidate reranking is the wrong cost shape.
- The redesign target should be:
  - group candidates by `(role, owner_file)` before owner-declaration selection,
  - produce one compact declaration candidate set per role/file,
  - run the LLM selector once per role/file/round rather than once per retrieved candidate,
  - feed selected declaration spans back into the existing role bucket scoring,
  - preserve a deterministic lexical fallback only as first-stage narrowing, not as a replacement for ambiguous reranking.
- This is larger than the previous micro-experiments because it changes where the reranking boundary lives: from candidate-level reranking to grouped role/file reranking.

- Experiment 7: lexical-first owner refinement for high-confidence `input_parsing`.
  - code change:
    - `services/retrieval/workspace.py`
    - moved local lexical span selection before owner-declaration LLM selection
    - skipped the owner-declaration LLM only when `role == "input_parsing"` and lexical score was at least `50.0`
  - motivation:
    - in the strong baseline trace, all `input_parsing` local spans scored above `50`
    - the lexical parser span matched the final accepted parser evidence better than the declaration selector's preferred parser declarations
  - verification run:
    - first attempt failed with an OpenAI read timeout and correctly surfaced the runtime error with no fallback
    - successful retry: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T111834Z`
  - measured effect:
    - skipped owner-selection calls: `32`
    - owner-declaration total tokens: `232642 -> 215234`
    - total retrieval tokens: `255549 -> 239345`
    - token delta: `-16204` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `behavior_output` drifted to broader emitter spans `src/compiler/emitter.ts:L2077-L2156` and `L2087-L2166`
  - conclusion:
    - this was the first redesign slice that reduced total retrieval cost materially
    - it still failed the quality gate, showing that local role-specific lexical gating cannot be applied independently without changing later recovery behavior
    - this experiment was reverted
- Experiment 8: scoped owner-declaration selector cache inside one follow-up batch.
  - code change:
    - `services/retrieval/workspace.py`
    - added a cache local to `_run_role_followup_pipeline(...)`, keyed by the exact owner-declaration selector payload
    - the cache reset on every follow-up batch and did not apply to the whole retrieval run
  - motivation:
    - this tested the structural reranking idea from the references more conservatively than Experiment 1:
      - avoid repeated expensive selector calls only inside one grouped follow-up pass
      - do not freeze choices across later recovery rounds
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T113147Z`
  - measured effect:
    - scoped selector cache hits observed: `15`
    - retrieval LLM calls: `72 -> 57`
    - owner-declaration selector calls: `64 -> 49`
    - owner-declaration total tokens: `232642 -> 179249`
    - total retrieval tokens: `255549 -> 201980`
    - token delta: `-53569` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - final evidence count dropped from `9` to `8`
    - one diagnostics evidence item disappeared
  - conclusion:
    - even a follow-up-local exact cache materially reduces token cost
    - it still changes the final accepted evidence enough to fail sufficiency
    - repeated selector calls are not merely duplicate waste in the current design; they also act as stochastic recovery opportunities
    - this experiment was reverted
- Experiment 9: reuse the first owner-declaration selection for the same file for the rest of the retrieval run.
  - code change:
    - `services/retrieval/pipeline/refinement.py`
    - `services/retrieval/workspace.py`
  - motivation:
    - stop asking the owner-declaration selector more than once for the same file, regardless of later refinement retries
    - test the stronger claim that repeated declaration choice on the same file is pure waste
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T142742Z`
  - measured effect:
    - retrieval LLM calls: `72 -> 20`
    - owner-declaration selector calls: `64 -> 8`
    - owner-declaration same-file cache hits observed: `184`
    - owner-declaration same-file cache misses observed: `8`
    - retrieval tokens:
      - `prompt_tokens=249155 -> 58437`
      - `completion_tokens=6394 -> 3570`
      - `total_tokens=255549 -> 62007`
    - token delta: `-193542` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `input_parsing` drifted to weaker spans in both `scanner.ts` and `parser.ts`
    - `behavior_output` drifted from `src/compiler/emitter.ts:L518-L597` to broader emitter spans `L1216-L1295` and `L2054-L2133`
  - conclusion:
    - same-file declaration re-selection is not behaving like redundant waste in the current pipeline
    - freezing the first declaration choice per file collapses token cost dramatically, but it also removes later recovery behavior and fails the quality gate
    - this experiment should not be kept in the current retrieval shape

## 2026-06-08

### Added

- Added a grouped retrieval pipeline package under `services/retrieval/pipeline/`:
  - `constants.py`,
  - `models.py`,
  - `file_level.py`,
  - `snippet_level.py`.

### Changed

- Split shared retrieval state models out of `workspace.py` into `services/retrieval/pipeline/models.py`.
- Split file-level retrieval helpers out of `workspace.py` into `services/retrieval/pipeline/file_level.py`.
- Split snippet-level refinement and snippet-quality helpers out of `workspace.py` into `services/retrieval/pipeline/snippet_level.py`.
- Reduced `services/retrieval/workspace.py` from `4112` lines to `3020` lines by moving the reusable helper families into the new package.
- Renamed the old post-owner `retarget/rescue` method family to cleaner follow-up terminology:
  - `_retarget_role_buckets(...)` -> `_refine_selected_role_buckets(...)`,
  - `_retarget_role_bucket(...)` -> `_refine_selected_role_bucket(...)`,
  - `_retarget_role_rescue_specs(...)` -> `_build_snippet_followup_specs(...)`,
  - `_late_role_rescue_specs(...)` -> `_build_late_recovery_followup_specs(...)`,
  - `_run_role_rescue_pipeline(...)` -> `_run_role_followup_pipeline(...)`.
- Renamed follow-up trace events from `role_rescue_*` to `role_followup_*` to match the new naming.

### Verification

- `python -m py_compile services\retrieval\workspace.py services\retrieval\pipeline\models.py services\retrieval\pipeline\file_level.py services\retrieval\pipeline\snippet_level.py services\retrieval\responsibility.py` passed after the split.
- TypeScript verification run `run-20260608T-pipeline-split-3` completed with `coverage_status=strong` and `sufficient=True`.
- Required-role evidence remained architecture-faithful after the file split:
  - `representation`: `src/compiler/types.ts:L220-L299`,
  - `input_parsing`: `src/compiler/parser.ts:L2319-L2398`,
  - `validation_checking`: `src/compiler/checker.ts:L4984-L5063`,
  - `diagnostics`: `src/compiler/diagnosticMessages.json:L399-L478`,
  - `behavior_output`: `src/compiler/emitter.ts:L1281-L1360`.

## 2026-06-07

### Added

- Added `services/retrieval/file_first_role_resolution_pipeline.md` to document the intended file-first retrieval pipeline.
- Added explicit loop safeguards for repeatable file-role resolution:
  - max one file-resolution round in v1,
  - bounded path-diverse alternates,
  - no repeated assignment states,
  - monotonic-progress requirement,
  - failed-file memory,
  - single-pass conflict repair,
  - role-owner gating before snippet selection,
  - no broad snippet retry before file-role re-resolution.
- Added retry scenarios for:
  - next-best file fallback,
  - cross-role reassignment,
  - weak-role re-resolution,
  - redundancy correction,
  - owner-over-helper retry,
  - snippet-failure-triggered retry,
  - graph-neighborhood retry,
  - role-conflict retry.
- Added trace events for bounded file-role resolution rounds:
  - `file_role_resolution_round_started`,
  - `file_role_resolution_round_completed`.

### Changed

- Refactored first-pass source retrieval to treat Qdrant chunks as file-entry signals rather than immediate snippet evidence.
- Collapsed Qdrant chunk hits into file candidates before responsibility scoring and role ownership selection.
- Reintroduced snippet retargeting only after file-level owner selection, keeping snippet selection downstream of file-role resolution.
- Added role-owner path gating so owner files block adjacent/helper files from satisfying the wrong role:
  - `checker.ts` blocks emitter/parser-style evidence for `validation_checking`,
  - `emitter.ts` blocks parser/service-style evidence for `behavior_output`,
  - `parser.ts` blocks emitter/service-style evidence for `input_parsing`.
- Added cross-role owner-path downvotes in `profile_candidate(...)` so files that look like another role's owner are less likely to satisfy the current role.
- Made role rescue pass focused retarget queries into local in-file refinement, not only into Qdrant snippet search.
- Dropped redundant `FILE` candidates from late feedback, final coverage checks, and final evidence when concrete snippets exist for the same role/path.
- Tightened role-specific snippet targeting around semantic declaration bodies:
  - `NodeFlags` / AST node representation in `types.ts`,
  - modifier parsing in `parser.ts`,
  - `checkClassDeclaration` in `checker.ts`,
  - class/member emission in `emitter.ts`.

### Verification

- `python -m py_compile services\retrieval\workspace.py services\retrieval\responsibility.py` passed after the refactor.
- TypeScript run `run-20260607T-file-first-8` completed with `coverage_status=strong` and `sufficient=True`.
- Final required-role evidence in that run:
  - `representation`: `src/compiler/types.ts:L220-L299`,
  - `input_parsing`: `src/compiler/parser.ts:L2319-L2398`,
  - `validation_checking`: `src/compiler/checker.ts:L4984-L5063`,
  - `diagnostics`: `src/compiler/diagnosticMessages.json:L397-L476`,
  - `behavior_output`: `src/compiler/emitter.ts:L1281-L1360`.
- The previous recurring misalignment was removed in the final run:
  - no `parser.ts` evidence satisfied `behavior_output`,
  - no `emitter.ts` evidence satisfied `validation_checking`,
  - `checker.ts` was selected for `validation_checking`,
  - required final evidence no longer contained `FILE` placeholders.

## 2026-06-06

### Added

- Added Qdrant search-result breakdown logging so retrieval traces can distinguish:
  - sparse-only top hits,
  - dense-only top hits,
  - final hybrid top hits.
- Added snapshot-scoped testcase setup and reuse flow for multi-repo evaluation cases beyond the original TypeScript benchmark.

### Changed

- Switched Qdrant cache flushing to persist partial embedding progress more aggressively during long UVA embedding runs.
- Extended evaluation and inspection workflow to compare cross-repo behavior on:
  - TypeScript abstract class support,
  - Vue directive validation,
  - pandas datetime64 integration.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed after the Qdrant breakdown change.
- Breakdown inspection confirmed that some missing-owner files, especially `checker.ts`, were often absent even before hybrid fusion, not merely lost during reranking.

## 2026-06-05

### Added

- Added late weak-role rescue seeding that prioritizes:
  - late follow-up queries first,
  - strong cross-role anchors second,
  - generic fallback snippet queries last.
- Added a reusable `role rescue` pipeline that unifies:
  - in-file retargeting,
  - late weak-role recovery.
- Added role-rescue trace events such as:
  - `role_rescue_started`,
  - `role_rescue_candidates_retrieved`,
  - `role_rescue_candidate_verified`,
  - `role_rescue_completed`.

### Changed

- Late weak-role rescue now performs broad Qdrant search for late follow-up and anchor-derived rescue queries instead of centering recovery on weak current candidates.
- CGC is now used as a verifier around shortlisted rescue candidates rather than as a broad rescue-search driver.
- Late weak-role recovery now avoids expensive CGC expansion for obviously weak supporting buckets and focuses only on stronger required-role anchors.
- Weak-role replacement became stricter so enforcement-heavy rescue hits can replace binder/types-style provisional snippets more decisively.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed after the rescue-pipeline refactor.
- TypeScript rescue traces showed improved parser retargeting, but `validation_checking` still struggled to pivot from adjacent files to `checker.ts`.

## 2026-06-04

### Added

- Added mandatory local Qdrant-backed hybrid retrieval as the active source-code backend.
- Added UVA-proxy embedding support with `text-embedding-3-large`.
- Added local Qdrant Docker setup and operational docs in:
  - `docker-compose.qdrant.yml`,
  - `services/retrieval/qdrant_hybrid_design.md`.
- Added hard-required indexing control through `RETRIEVAL_ENABLE_INDEXING`.
- Added local embedding cache persistence, chunk-signature reuse, and Qdrant sync-manifest reuse across runs.
- Added bounded embedding concurrency and embedding batch-size controls for the UVA embedding endpoint.
- Added declaration-aware chunking to reduce oversize embedding inputs and improve coherence of retrievable spans.
- Added role-status-aware retrieval state:
  - `retrieved_candidates`,
  - `accepted_candidates`,
  - `satisfying_refs`,
  - `role_status`.
- Added late-assessment-driven downgrade so accepted snippets no longer automatically imply that a role is satisfied.
- Added one bounded Qdrant recovery pass for weak required roles.

### Changed

- Replaced the old BM25-first active retrieval backend with Qdrant hybrid retrieval while keeping CGC as a separate structural layer.
- Reused existing CGC and Qdrant index state when chunk signatures matched instead of rebuilding every run.
- Reduced fresh indexing cost by:
  - skipping obvious garbage/generated content,
  - reusing cached embeddings,
  - using bounded in-flight embedding requests,
  - tuning embedding batch sizes empirically against the UVA proxy.
- Final evidence selection now uses `satisfying_refs` rather than every accepted candidate.
- Noise snippets from late LLM assessment are explicitly excluded from satisfying a role.

### Removed

- Removed fallback logic from the active retrieval path: Qdrant became a hard requirement for source-code retrieval.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed repeatedly during the Qdrant migration and role-status alignment work.
- Empirical embedding throughput checks showed that larger batches materially improved cold-index speed on the UVA endpoint, while warm-cache/index-reuse runs became practical.
- Multi-repo evaluation was exercised on:
  - TypeScript,
  - Vue,
  - pandas,
  with cached index reuse and role-aware traces.

## 2026-06-07

### Added

- Added general local in-file refinement after file selection. The scorer uses the selected file path, retrieval role, role query, helper queries, retrieval terms, prompt evidence, and declaration anchors to choose a better span inside large files.
- Added `local_in_file_refinement` as a retrieval path for spans selected by deterministic in-file scoring.
- Added salient excerpt generation for late LLM assessment so long spans are compacted around relevant declarations instead of blindly truncating from the first line.
- Added `RETRIEVAL_LLM_CONTINUITY_ENABLED` in `.env` and `.env.example`.
- Added experimental process-local LLM continuity for Chat Completions-compatible APIs. When enabled, the next LLM call receives only the previous compact JSON retrieval result as orientation, not full file content.
- Added role-scoped handling for trusted Obsidian file hints. Note-derived file hints are now kept in retrieval-plan metadata and applied only to matching roles, instead of being promoted to global confirmed file hints.
- Added focused regression coverage for:
  - continuity env parsing,
  - local in-file refinement preferring role-specific declaration spans,
  - Obsidian checker hints helping `validation_checking` without globally narrowing unrelated roles,
  - existing CodeRepoQA retrieval expectations.

### Changed

- Direct owner file fallback now delegates span choice to the same general in-file scorer before falling back to the older broad window logic.
- In-file refinement now lets deterministic local file scoring compete with Qdrant in-file snippet refinement.
- Late assessment sees declaration-centered excerpts for retrieved candidates, improving judgment on spans where the useful function starts after a few setup lines.
- Obsidian is now treated as an additive source of truth. If notes only point to `src/compiler/checker.ts`, parser/emitter/diagnostic role retrieval still runs against the normal code pipeline.

### Removed

- No retrieval subsystem was removed. The older broad direct-owner window selection remains as fallback only; it is no longer the primary span choice when the local in-file scorer can identify a stronger window.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed.
- Role-scoped Obsidian regression tests passed:
  - `python -m unittest tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_obsidian_source_truth_guides_retrieval_to_checker tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_obsidian_file_hints_are_role_scoped_not_global_narrowing`
- Full retrieval test set passed after the role-scoped hint change:
  - `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval`
- Obsidian role-scoped TypeScript case run:
  - default Qdrant collection was stale on this machine (`1128` points for a `20653` document BM25 index), so verification used a fresh temporary collection.
  - two attempts hit upstream LLM proxy HTTP 500s during late synthesis; retry succeeded at `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260607T-obsidian-role-scoped-fresh-env-retry2`.
  - retrieval plan had `confirmed_file_hints: []` and metadata `trusted_local_note_file_hints: ["src/compiler/checker.ts"]`.
  - role buckets were not globally narrowed: `input_parsing` retrieved parser spans and `behavior_output` retrieved emitter/tc spans.
  - final selected evidence was still partial: representation (`types.ts`), validation checking (`checker.ts`), and diagnostics (`diagnosticMessages.json`) were selected; input parsing and behavior output remained missing after late assessment.
- Continuity-off TypeScript case run:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260607T-continuity-off-refined-salient`
  - selected `src/compiler/checker.ts:L4979-L5058`
  - retrieval path `local_in_file_refinement`
  - late assessment marked the snippet `core` for `validation_checking`.
- Continuity-on TypeScript case run:
  - first final attempt hit an upstream proxy HTTP 500 from the LLM provider.
  - retry succeeded at `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260607T-continuity-on-refined-salient-retry`
  - selected `src/compiler/checker.ts:L4992-L5071`
  - retrieval path `local_in_file_refinement`
  - late assessment marked the snippet `core` for `validation_checking`.
- Final `.env` state has `RETRIEVAL_LLM_CONTINUITY_ENABLED=false`.
