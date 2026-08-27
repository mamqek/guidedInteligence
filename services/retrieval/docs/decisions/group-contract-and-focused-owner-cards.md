# Group-keyed comparison and focused owner cards (2026-08-28)

## Scope and fixed baseline

User authorized two separate changes: repair owner/group output consistency, then test signature + retrieved
focus + limited surrounding context. Summary-led file reasoning is design analysis only; no summary stage,
island admission, final-selection removal, or scheduler changes are authorized here.

Preserve the dirty working tree. Prior provisional consistent cards: 1,024 rendered characters per owner,
full source whenever it fits; saved TypeScript admission 17 -> 6 files, 174 -> 95 candidates, 72,921 input
characters. Actual 214614Z / 214625Z retained two implementation Oracles each, partial/false, 102,159 / 86,236
retrieval tokens. Source indexes and snapshots are reused; no indexing or explanation generation.

## G — Group-keyed contract, attempt 1

Boundary: initial owner comparison input group metadata, output schema, validation and matching prompt only.
Each group is a required property whose value is null (not selected) or a primary/additional owner selection.
Its enums contain only that group's owner IDs. Input groups name their source path directly. Existing global
24-owner cap, uniqueness, primary/additional meaning, lifecycle and admission policy remain unchanged.
No compatibility fallback and no post-hoc correction of invalid model IDs.

Expected effect: prevent the cross-file selections in targeted replay 1 (o59 under g2 instead of g3) and
replay 2 (o70/o72 under g7 instead of g3). Schema size and null group outputs change token use; independently
measure this on the exact saved targeted comparison payload, twice, without source preparation or admission.
Tests cover wrong-group IDs, missing/unknown groups, duplicate IDs, empty selection and global overflow.
Failures remain explicit. Maximum three implementation variants; no source-card tuning during this step.

## F — Focused owner cards, attempt 1

Freeze G. Replace the consistent renderer's whole-owner shortcut with bounded focused rendering for all owners.
Initial policy: up to four signature lines + up to eight retrieved body lines + two adjacent context lines per side, at most
16 source lines and 1,024 rendered characters. Distant segments have explicit line labels and omission markers.
The character ceiling is unchanged to isolate the new focus/line policy. Signature/docstring-only retrieval
uses the first actual body lines. No expansion merely to fill unused space. These are experimental defaults,
not inferred optimal thresholds. Preserve all canonical IDs, provenance, file order and qualification settings.

Expected effect: body visibility with smaller average cards and more admitted files. Risks: a critical return or
handoff outside the window, multiline syntax cropped, metadata still dominating, many owners per file still
expensive. Source views remain partial when omitted; no claim that a visible body line proves semantic relevance.

Verify Python/JavaScript, tiny and short-but-unfocused owners, late focus, docstrings, long signatures/lines,
omission labels and both hard bounds. Replay unchanged saved TypeScript input and inspect literal owner cards,
then two real owner-comparison calls. If coherent, run two full TypeScript actual-pipeline acceptance cases with
final selection enabled and explanation disabled. No hidden Oracle informs rendering or ordering.

Compare fixed-input cost/admission first; live run variation is not a causal estimate. Audit builder/builderState,
watch tests and misleading broad files through raw retrieval, resolution, admission, comparison, qualification,
controller and final selection. Record tokens, coverage/sufficient, final Oracle overlap and exact source effects.
Do not retain solely for token reduction. Questionable outcomes remain explicit for user review; demonstrated
quality regression requires disabling/reverting only this step, preserving G and unrelated changes.

## Ledger

| Step | Attempt | Focused checks / runs | Actual acceptance | Decision |
|---|---:|---|---|---|
| G | 1 | 18 tests; group-keyed-1/2 real replays valid (15/16 selected) | 225224Z / 225234Z both valid | Contract correction retained |
| F | 1 | Focused-llm-1/2 valid, 22/17 selected; combined focused suite 134 tests | 225224Z / 225234Z, 3/2 Oracles, partial/false | Provisional, not quality-accepted |

G replays keep the same 139 owners/eight files and exact source views as targeted-llm-1. Input increases
63,119 -> 65,821 characters from schema/path/prompt changes alone. Tokens 21,895 / 22,036 (prompt 20,717 each);
no wrong-group choices, no repaired IDs. Full logs: testing/codeRepoQA/owner-source-replays/group-keyed-1/2.jsonl.
This proves the focused contract, not downstream relevance; those choices still vary. Test invocation uses unittest
(pytest is not installed); no dependency was added for the testing convenience.

F isolated comparison: unchanged 95 owners/six files; 69,982 characters versus 74,924 for old consistent cards
with G applied to the identical six-file payload (-4,942). Historical B with the old schema was 72,921, not an
isolated rendering comparison. Prompt tokens 19,564 each; total tokens 20,338 / 20,679. Both select build/watch
mechanisms and also broad Project/test owners; validity is not semantic acceptance. File admission did not improve
on this saved inventory. With G but old compact cards, recomputed admission is 14 files/156 owners rather than
the historical 17/174: schema overhead alone affects prefix admission, and must not be attributed to F.

Pandas saved-source check: 205 owners/five files still admitted, 125,724 characters including the complete crossing
file. _binop now shows signature and lines 1485-1494 (type check/alignment), versus signature only originally.
But the smaller focus omits the operation/result/name-finalization tail; this is explicitly incomplete evidence,
not proof that _binop will be recognized. No new Pandas LLM or full pipeline run is claimed.

First actual attempts 225115Z / 225121Z failed before retrieval because the ambient Node 20.11.1 lacks node:sqlite.
They are infrastructure failures, not acceptance runs. No index rebuild was requested. Retry uses the existing
CodeGraph-bundled Node 24.16.0 via process-local PATH only, with identical npm profile/model/settings. No package
installation or persistent environment change. The first Pandas offline command used an incorrect case directory;
it failed before work and was corrected to pandas-dev-pandas-10068.

## Completed actual acceptance

Main artifact: `testing/codeRepoQA/owner-source-replays/focused-acceptance.json`, generated by
`testing/codeRepoQA/audit_owner_body_runs.py` from the full real logs. Run folders are under
`C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/`.

| Run | Canonical files admitted | Comparison owners / selected | Comparison input chars | Comparison tokens | All retrieval tokens | Implementation Oracle files | Result |
|---|---:|---|---:|---:|---:|---:|---|
| run-20260827T225224Z | 4 | 84 / 14 | 67,182 | 19,185 | 101,440 | 3 | partial / false |
| run-20260827T225234Z | 4 | 95 / 21 | 77,482 | 22,168 | 101,088 | 2 | partial / false |

Both traces: source preparation 53, file admission 54, literal comparison request 57, validated selections 59.
Both reuse index a27de1ce with 83,401 points and rebuilt=false (line 9). Structural sync opens the existing graph;
there was no reindex request. Dormant completion remains disabled, three normal controller rounds, no explanation.
Final focused suite: 134 tests across initial comparison, source cards, qualification/cache, AST routing, JSON
completion and qualification-first integration. No new third-party dependencies.

Exact behavior and losses:

- 225224Z admits tsbuildPublic, watchMode, builderState, builder. Its 63 prepared admitted cards contain 41,559
  rendered source characters; maximum 16 source lines / 1,015 characters. builderState had seven dense/three sparse
  hits, eight canonical owners and best retrieval rank 1. updateShapeSignature, updateExportedModules and
  updateExportedFilesMapFromCache are selected and qualify direct (89). updateShapeSignature reaches final rank 9;
  the controller later recovers getFilesAffectedByUpdatedShapeWhenModuleEmit, final rank 8. This run's initial
  builderState rank was already stronger than in the second run; do not attribute that to formatting.
- 225234Z admits watch, builder, tsbuildPublic, watchMode. Its 74 prepared admitted cards contain 49,620 characters;
  maximum 16 lines / 1,015 characters. builderState had six dense/three sparse hits, six canonical owners and best
  retrieval rank 3. They are resolved/canonicalized (51/52), excluded at file admission (54), never compared or
  qualified, and absent from final evidence. No controller recovery. This is still FPK-1, not final-model rejection.
- invalidateProjectAndScheduleBuilds was bodyless in its old compact view; both focused cards expose its complete
  five-line / 339-character scheduling body. It qualifies direct and reaches final ranks 2/4. B already disclosed
  this same body; this demonstrates F preserved the benefit, not a new F-specific discovery.
- Second run also selects previously bodyless createSolutionAndWatchModeOfProject (684-character comparison card)
  and startWatching (787); both qualify direct and reach ranks 1/2. createWatchCompilerHostOfFilesAndCompilerOptions
  exposes more source but qualifies navigation-only and is not selected finally. More body is not automatic support.
- Generic watchMode owners remain navigation: verifyTransitiveReferences in both runs, verifyIncrementalErrors in
  the first and verifyProjectChanges in the second. Final output includes navigation test context (first run's range,
  second run's verifyProjectChanges); Oracle-file overlap does not prove an issue-specific test chain was completed.
- Final candidate pools 23/28 (1373/1773). Final flow input accounts 49,809/45,662 chars (1375/1775), preserving
  all 14/11 eligible connections. First run excludes one flow; second excludes none. Final selection finishes in both.

Total live retrieval tokens 202,528, versus prior B's 188,395 (+14,133 / 7.5%). Initial comparison totals are 41,353;
qualification 60,369; coverage 60,987; final consolidation 36,421; connected-source context 3,398. There is no observed
overall token reduction. Different live upstream inventories/controller choices prevent causal attribution of those
totals to F. Fixed-input rendering savings of 4,942 characters are the isolated effect, and did not admit another file.

Decision: keep G as the verified contract correction (including its measured schema-cost tradeoff). Leave F
provisional for user review, replacing the previous provisional B renderer; no stable overall quality improvement
is established, and the modest saving does not solve whole-file admission. No additional variants, shortlist,
summary implementation, island policy, budget increase or automatic final-selection removal was introduced.
Paid focused calls consumed 43,931 G + 41,017 F = 84,948 tokens. With successful live runs, measured retrieval/stage
tokens total 287,476; the two infrastructure failures have zero retrieval LLM responses and are not acceptance runs.

## Summary-led retrieval idea (not implemented)

File briefs could be navigation memory rather than qualified evidence: source-backed claims, exact owner/range
references, explicit unknowns, and proposed inspections. A brief must say which source was actually read; extracted
identifiers/calls alone cannot justify a whole-file behavioral summary. Batched source inspections still need
typed actions, novelty suppression, memoization, accounting and ordinary qualification. Assess source costs of
creating/updating briefs as well as savings in later repeated prompts. Do not inherit semantic proof from summaries.
Removing a separate final LLM call requires moving its consistency/coverage/citation checks into a final controller
decision; it does not remove the need for final evidence validation. This is a separate architectural experiment.

### Critical design assessment

The useful distinction is a compact navigation brief versus source-backed evidence. A brief would contain the file's
observed role; separately grounded claims linked to known owner/range handles and request obligation IDs; relevant
call targets and why inspecting them may close a stated gap; unresolved alternatives; and exactly which source was
read. Qualification remains claim/source-specific: a file can contain both direct proof and unrelated code. Do not
turn a single file-level label into semantic support for every member or every obligation.

This can reduce repeated raw-source disclosure and make cross-owner relationships easier to remember. It also risks
compressing away the decisive condition, ordering, or ignored return value. The Pandas _binop focus experiment is a
concrete warning: alignment is visible, name finalization is not. Summarizing that partial view cannot recover the
missing behavior. A known identifier/call inventory is a useful inspection catalogue, not enough source to summarize
the entire owner's semantics. Graph omissions for dynamic registration remain omissions.

An end-to-end version would perform batched source reading to create briefs, then let the controller jointly update
briefs and propose batched typed inspections. Newly inspected source updates the grounded claims, not an unsupported
global narrative. Keep model-produced interpretations separate from observed source facts and avoid requiring hidden
chain-of-thought; concise claim/connection justifications suffice. The final controller step could export the verified
evidence bundle directly, with deterministic known-handle, citation, coverage and budget checks. It must still handle
contradictions, unsupported obligations and pending inspections explicitly; eliminating a separate final model call
does not mean accepting an unfinished chain as sufficient.

Cost must count initial source reading + summary generation + repeated brief context + later inspections. Fewer calls
alone is not fewer tokens. Summarizing every initially retrieved file may be expensive; summarizing only admitted files
cannot repair pre-admission losses. A first separate experiment could replace repeated downstream source context with
source-grounded briefs on a fixed candidate pool and compare exact handoffs retained/missed, inspection quality, false
support and total tokens. That isolates memory compression, not initial admission. An early summary-first selector and
terminal-selection consolidation would be subsequent independent experiments, not additions to G/F.

This is more agent-directed if the model chooses the next inspection from its evidence state; summarization by itself
does not make the scheduler agent-directed. Existing typed tools, deterministic novelty/memoization and source identity
remain useful and necessary rather than being replaced by free-form file narratives.

Current-code distinction: retrieval_controller._evaluate sends only direct_evidence candidates to coverage;
coverage_evaluation._bounded_candidates truncates their snippet strings to per-candidate allowances. Qualification
already emits visible_support and missing_information, but this is not a persistent file-level evidence/lead brief.
A design that exposes navigation briefs to the action planner changes eligibility/context as well as compression.
Measure those effects separately. Including a rationale for every extracted identifier can itself exceed the snippet
payload; retain salient claims in the brief and keep the complete deterministic identifier/call catalogue addressable.
