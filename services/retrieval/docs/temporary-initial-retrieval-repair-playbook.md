# Temporary Initial-Retrieval Repair Playbook

## Purpose

This is a temporary execution document for separating and testing the repairs discovered from the pandas
`Series._binop` regression. It is intentionally more procedural than the retrieval changelog. Follow it in order,
update the result ledger while working, and remove or archive it after every step has a recorded decision.

The central rule is: **change and evaluate one stage at a time**. Do not simultaneously change request analysis,
Qdrant candidate handling, CodeGraph resolution, comparison serialization, and qualification. A later step may rely
on the accepted output contract of an earlier step, but its own comparison must hold all earlier accepted behavior
fixed.

This playbook does not authorize implementation merely by existing. Implementation begins only after the user asks
to proceed.

## Motivating failure

The failed pandas run contained two distinct losses that must not be treated as one problem:

1. Request analysis retained the repository identifiers `Series` and `add`, but paraphrased the concrete contrast
   `s1 + s2` versus `s1.add(s2)` into broad language such as “Series entry points.” The earlier anchor repair therefore
   worked at the identifier level but did not preserve the relationship between the identifiers.
2. The exact `pandas/core/series.py::Series._binop` owner range was outside the returned top-48 windows, but Qdrant
   returned a valid source-grounded route in `pandas/core/ops.py`:

   ```python
   return self._binop(other, op, level=level, fill_value=fill_value)
   ```

   CodeGraph resolved the range to `_flex_method_SERIES::flex_wrapper`. The comparison serializer then chose the
   80-character preview `flex_wrapper.__name__ = name`, hiding the `_binop` call. The comparison LLM consequently
   rejected a useful lead.

The experiment must fix both losses while keeping their measurements separate.

## Global experiment rules

### Fixed inputs and baselines

- Save the exact pandas issue/request input used by the failing and successful historical runs.
- Keep repository snapshot, index signature, model, temperature/settings, prompt profile, and test harness fixed.
- Retain the successful historical query wording and the failing wording as comparison fixtures.
- Record the current request-analysis output, raw dense/sparse results, CodeGraph response, comparison payload,
  comparison response, qualification payload, and token counts before changing each corresponding stage.
- Do not use Oracle membership as the sole success test. Inspect whether returned owners and leads logically explain
  the issue, including relevant non-Oracle flow files and misleading generic matches.

### Attempt limit

An **attempt** is one implementation variant for one step, not one stochastic execution.

For every step:

1. Implement only that step's proposed change.
2. Run its isolated test twice with the same accepted candidate variant.
3. Accept the step only if both runs satisfy the step's criteria.
4. If either run fails, inspect the exact stage input/output, adjust only that stage, and count the adjustment as the
   next attempt.
5. Stop after at most three implementation attempts.

If no attempt produces two successful runs:

- compare all three variants against the unchanged baseline;
- retain the best variant only if it is measurably better and introduces no observed regression;
- otherwise revert the step completely;
- record every attempted variant, exact failures, likely causes, and the next plausible experiment in this file;
- continue to the next independent step only if doing so is still meaningful without the failed dependency.

### Isolation and rollback

- Keep each step as a separate patch/commit-sized unit so it can be reverted without removing accepted earlier work.
- Do not tune a later stage to hide an earlier-stage failure.
- When a step consumes an earlier accepted contract, replay the exact saved earlier output where possible. This avoids
  rerunning Qdrant or an unrelated LLM stage during an isolated comparison.
- Do not silently replace an LLM-backed stage with deterministic output. Saved LLM output may be replayed as an
  explicit fixture for downstream stage tests, but it must be labeled as replayed input.
- After a failed attempt, preserve its trace before modifying the next attempt.

### Required result record for every step

Record:

- date and attempt number;
- files changed;
- exact isolated command or harness entry point;
- whether inputs were live or replayed;
- two run IDs/artifact paths;
- acceptance checks and observed values;
- LLM tokens, serialized characters, runtime, and tool calls relevant to that stage;
- regressions or unresolved edge cases;
- decision: `accepted`, `best-effort retained`, or `reverted`.

## Step 1 — Preserve the concrete issue contrast in generated queries

### Boundary

Change only request-analysis prompt/schema/validation behavior that produces obligation descriptions and query hints.
Do not run Qdrant, CodeGraph, qualification, the controller, final evidence selection, or explanation generation.

### What the earlier fix did and did not do

The earlier fix:

- supplied repository identity to request analysis;
- retained repository-facing identifiers such as `Series` and `add`;
- filtered tiny reproduction variables such as `s1` and `s2` from sparse identifiers when they were not real
  repository symbols.

It did **not** require the semantic relationship between those terms to survive in each relevant generated
obligation. Consequently, the output could contain both `Series` and `add` while replacing “operator arithmetic
versus the `.add(...)` method” with the much broader “Series entry points.”

### Desired output

For the pandas request, the relevant generated question must retain all three ideas, allowing natural paraphrase:

- the operation is performed in two different forms: an operator expression and the `Series.add` method;
- the operand names differ;
- retrieval is looking for where the result name is chosen or reconciled.

It need not preserve `s1` and `s2` as sparse search tokens. Those are example variables, not repository symbols. The
dense question may quote the expressions as behavioral examples, while the sparse side should continue to favor
confirmed repository-facing terms such as `Series`, `add`, operator/result/name, and any validated code symbols.

For the TypeScript regression fixture, repository context must continue to prevent reproduction names such as
`pure` and `main` from becoming repository architecture, and must not describe the TypeScript compiler as external
to its own repository.

### Preferred implementation direction

Start with a prompt/schema contract change, because the missing information is semantic rather than a simple list of
tokens. Ask request analysis to preserve each explicit behavioral contrast as a small structured field alongside the
ordinary obligation description. The field should express the two compared forms and what property differs; it must
not invent identifiers or repository facts. The query builder can then include that contrast in the dense question
without forcing reproduction variables into the sparse query.

Do not start with a regex that attempts to understand arbitrary source-code expressions. A deterministic validator
may check that a supplied contrast was not dropped, but it should not manufacture the contrast itself.

### Three-attempt ladder

1. Prompt-only: explicitly require preservation of concrete comparisons and contrasts in the relevant obligation.
2. Prompt plus structured contrast field: separate the contrast from the prose obligation so later paraphrasing
   cannot silently erase it.
3. Prompt/schema plus validation-and-retry within request analysis: retry once when an explicit input contrast is
   absent from all relevant structured outputs. Do not retry for stylistic wording differences.

Use the simplest attempt that passes. Do not automatically implement all three.

### Isolated verification

Run request analysis only, twice, on the exact pandas input. Both outputs must:

- retain the operator-versus-`.add(...)` comparison in meaning;
- retain the differing-name/result-name question;
- keep `Series` and `add` available as repository-facing identifiers;
- avoid promoting `s1`/`s2` as repository symbols;
- avoid reducing the question to generic “entry points,” “operations,” or “name handling” alone.

Then run the request-analysis-only TypeScript fixture twice as a regression check. Both must preserve correct
repository identity and distinguish reproduction context from compiler implementation. These are still isolated
stage runs, not full test cases.

### Measurements

- Exact generated obligation descriptions and structured contrasts.
- Dense query input and sparse identifier input that would be emitted; do not execute them yet.
- Variation between the two runs.
- Request-analysis token cost and any retry cost.

### Acceptance

Accept only if two consecutive pandas runs satisfy every semantic condition and the two TypeScript checks retain
the repository-context repair. If a validation retry is required frequently, treat that as instability rather than
success.

## Step 2 — Resolve every returned range through CodeGraph without first-N loss

### Boundary

Change/test only range submission, batching, response combination, owner/context classification, duplicate-owner
collapse, and diagnostics. Use saved Qdrant ranges. Do not call request analysis, Qdrant, or any LLM.

### Required behavior

- Submit every unique returned raw range to CodeGraph.
- Use batches of at most 80 ranges and run independent batches in parallel.
- Preserve deterministic input order when recombining responses.
- Fail explicitly if any batch fails or a submitted range has no accounted-for response.
- Log `submitted_ranges`, `batch_count`, `batch_sizes`, `resolved_ranges`, failures, and elapsed time.
- Classify broad containing nodes such as `class Series` as outer context using CodeGraph node type and exact source
  containment—not naming conventions.
- Treat executable members such as `Series.append` and `Series._binop` as independent candidate owners.
- Collapse repeated occurrences of the same exact CodeGraph node ID into one owner record.

Do not enlarge raw Qdrant chunks or union overlapping chunks. Structural resolution should identify exact owner
handles without immediately sending the complete owner source to an LLM.

### Recurrence diagnostics

For each collapsed owner, keep these counts separate:

- raw chunk count;
- distinct query-view count;
- distinct obligation count;
- distinct retrieval-channel count.

Do not convert raw occurrence count into proof of relevance. These fields are trace/support information for later
comparison and auditing.

### Isolated verification

Replay the same saved range set twice. Verify:

- every input range is accounted for;
- batching produces the same combined semantic result as a small sequential reference subset;
- all chunks crossing `_flex_method_SERIES::flex_wrapper` resolve to that owner;
- duplicate node IDs collapse without losing their provenance counts;
- `Series` is context and its individual methods remain candidate owners;
- no LLM or embedding tokens are spent.

### Three-attempt ladder

1. Parallel 80-range batching plus strict count diagnostics.
2. Fix ordering/error-accounting defects without changing semantic resolution.
3. If bridge behavior differs across batch composition, isolate and correct the bridge contract; do not conceal the
   difference by choosing a favorable batch size.

### Acceptance

Two identical complete replays with `submitted_ranges == accounted_ranges`, stable owner IDs, and no first-80 bias.

## Step 3 — Serialize source views once and attach owners by reference

### Boundary

Change only the object prepared for initial owner comparison. Use the saved Step 2 structural output. Do not invoke
the comparison LLM yet.

### Current problem

One raw range can cross several owners. The current format creates a separate owner card and repeats excerpts and
support metadata for each owner. That inflates the comparison payload and allows each repeated miniature excerpt to
hide a different important line.

### New representation

Represent each unique retrieved source view once. A view contains:

- stable view ID, path, and raw returned line range;
- the compact source lines selected in Step 4;
- retrieval channel/query/obligation provenance;
- references to all independent candidate owner IDs crossing the range;
- references to outer-context owner IDs, kept separate from candidates.

Each owner record contains only:

- stable CodeGraph owner ID and symbol;
- node kind and exact owner range;
- view IDs supporting it;
- the four separate recurrence/support counts;
- any compact structural relationship needed to understand containment.

An owner that appears in five chunks is one owner with five supporting view references, not five comparison entries.

### Isolated verification

Serialize the same saved structural set twice and compare byte-for-byte output. Assert:

- every candidate owner and every supporting view remains reachable;
- source text is stored once per view rather than once per owner;
- candidate owners and outer context cannot be confused;
- duplicate owner IDs are absent;
- the payload contains no qualification allocation/debug bookkeeping irrelevant to comparison.

### Measurements

- owner count, view count, and owner-to-view edge count;
- total serialized characters;
- characters occupied by source, provenance, and structural metadata separately;
- reduction versus the current owner-card payload.

The prior estimate of reducing the comparison call from about 26k to 15–18k tokens is a hypothesis, not an
acceptance claim. Record the measured result.

### Three-attempt ladder

1. Normalize the current data into shared views without removing any information.
2. Remove only repeated or trace-only fields proven unnecessary to the LLM contract.
3. Compact provenance references while retaining full trace data outside the LLM payload.

### Acceptance

Two deterministic serializations with no lost owner/view/provenance and a meaningful measured payload reduction.
Do not accept token reduction if the `_binop` call or any equivalent concrete lead disappears.

## Step 4 — Preserve executable hit and lead lines in compact source views

### Boundary

Change only compact source-line selection inside each shared source view. Do not change owner ranking, LLM prompts,
or qualification.

### Current problem

The current 80-character owner preview prioritizes a line containing the owner's leaf symbol. For
`_flex_method_SERIES::flex_wrapper`, that selected `flex_wrapper.__name__ = name` and truncated away the later
`return self._binop(...)` call. The implementation followed its rule, but the rule is wrong for retrieval.

### Generic desired behavior

Do not hardcode `_binop`. Preserve complete source lines in this priority:

1. executable call/reference/return lines that expose a concrete repository-resolvable next owner;
2. lines containing the concrete issue contrast or confirmed repository anchors;
3. the owner signature and a minimal amount of structural context;
4. assignments or labels containing only the current owner name.

Use structural syntax/CodeGraph information where available. Do not treat every line with parentheses as a useful
call, and do not use raw keyword count alone. Preserve line boundaries; never cut a meaningful line at an arbitrary
character ceiling. Keep the view bounded by a small line/count budget, with an explicit omission marker when needed.

### Three-attempt ladder

1. Prioritize CodeGraph/AST-resolved outgoing calls and references, then signature context.
2. If that misses useful unresolved calls, include executable return/call expressions that resolve to an exact
   repository node even when the edge is not native.
3. If a fixed small line budget remains lossy, let the view contain a bounded set of labeled fragments
   (`matched`, `executable lead`, `signature`) rather than one concatenated excerpt.

### Isolated fixtures

At minimum include:

- pandas `flex_wrapper`, where `return self._binop(...)` must be visible and `__name__ = name` may remain secondary;
- a function whose relevant evidence is an assignment rather than a call, ensuring assignments are not globally
  discarded;
- a comment-plus-declaration case;
- a large owner with several unrelated calls, ensuring the preview does not become a call dump;
- TypeScript and Python fixtures through the language-routed source abstraction.

Run the fixture set twice for the chosen attempt.

### Acceptance

The concrete source-grounded next step is always visible in both runs, generic assignments do not displace it, and
non-call evidence fixtures do not regress. Record preview characters/lines and omission status.

## Step 5 — Let the owner-comparison LLM choose from bundled views

### Boundary

Change the initial owner-comparison prompt/schema to consume Step 3/4's bundled views and compact owner references.
Do not yet run qualification or the controller.

### Required decision contract

- Make a separate decision for each candidate owner ID even when several share one source view.
- Allow selection of more than one owner from a file when they prove genuinely different parts of an obligation.
- Do not force one representative merely because owners share a file.
- Treat outer context as context, never as another competing evidence owner.
- Explain selection using visible source and the exact obligation/contrast.
- Reject generic owners that match only broad words when a concrete mechanism owner is present.
- Keep rejected owners as exact dormant handles with their provenance; do not promote them to evidence or islands.

Dormant handles may later be activated only by an existing source-grounded verified lead. This step does not add
every rejected owner to CodeGraph islands and does not make rejection itself a follow-up action.

### Isolated verification

Use saved comparison inputs; invoke only the real comparison LLM. Run the chosen variant twice. The fixture set must
include:

- a view containing `flex_wrapper.__name__ = name` and `return self._binop(...)`;
- a `series.py` group containing generic owners and `Series._binop` when the exact owner is available;
- a file where two non-overlapping owners legitimately prove different steps;
- a negative generic-name owner;
- at least one TypeScript group to detect pandas-specific prompt tuning.

### Measurements

- selected/rejected owner IDs and reasons;
- whether concrete mechanism owners beat generic-word owners;
- comparison input/output tokens;
- source characters and repeated-source characters;
- decision variation between the two runs.

### Three-attempt ladder

1. Adapt the current prompt/schema to shared views without changing its decision policy.
2. Clarify that executable leads and concrete issue contrasts outweigh generic lexical overlap.
3. Add a bounded comparative requirement within each file/obligation group: state why a selected owner contributes
   more than the strongest rejected alternative.

### Acceptance

Two runs must retain the concrete pandas route, reject the known generic alternatives, and keep the TypeScript
fixture sensible. Token use must be measured, not inferred from character count.

## Step 6 — Fully disclose and qualify only selected owners

### Boundary

Integrate accepted comparison output with contextual disclosure and the existing qualification stage. Stop before
controller scheduling and final selection for the initial isolated check.

### Required behavior

- Resolve each selected owner to its exact complete structural range.
- Apply existing safe disclosure policy: complete small owners; bounded, complete-line representations for large
  owners; outer class/function context only when structurally necessary.
- Do not enlarge every Qdrant chunk to its full owner before comparison. That previously produced large, vague
  qualification cards and source-budget pressure.
- Give each selected owner one qualification decision.
- Keep shared file/outer context deduplicated in the LLM payload.
- Keep rejected dormant handles out of qualification unless a later verified source lead activates one.
- Emit explicit diagnostics for empty source, reduced source, selected-owner disclosure, and dormant-handle
  activation.

### Isolated verification

Replay accepted Step 5 outputs twice through disclosure plus real qualification. Verify:

- `Series._binop`, when selected, receives its exact owner source rather than the raw 40-line chunk or whole class;
- the `flex_wrapper -> Series._binop` call remains visible and produces a concrete local follow-up when `_binop` was
  not initially selected;
- no qualification card has empty source;
- source-reduced cards retain their executable/matched lines;
- qualification token growth is recorded and remains attributable.

### Three-attempt ladder

1. Wire the new comparison contract into existing disclosure unchanged.
2. Deduplicate shared context/trace-only fields if qualification payload pressure remains.
3. Adjust bounded owner rendering only for demonstrated information loss; do not globally increase owner size.

### Acceptance

Two qualification-only runs preserve the intended owner/lead behavior with no empty cards and no unexplained source
loss.

## Step 7 — Integrated diagnostic and full acceptance

Run this only after Steps 1–6 each have a recorded decision.

### Diagnostic smoke

Run the pandas actual pipeline with explanation generation and final evidence selection disabled. Inspect every
boundary rather than only Oracle overlap:

1. generated contrast and sparse anchors;
2. raw dense/sparse exact owner ranges and textual call/reference leads;
3. submitted/resolved CodeGraph counts;
4. owner/view grouping and recurrence support types;
5. compact view source lines;
6. comparison selection/rejection;
7. full disclosure and qualification;
8. verified-lead creation/execution;
9. controller stop reason and pending actions.

The smoke is diagnostic only and cannot accept the combined behavior.

### Acceptance runs

If the smoke is sound:

- run pandas twice through the actual pipeline with final evidence selection enabled and explanation generation
  disabled;
- run the usual TypeScript case twice under the same policy as a regression comparison;
- reuse unchanged indexes and record their signatures;
- record run IDs, `coverage_status`, `sufficient`, selected evidence, logical non-Oracle evidence, retrieval tokens,
  comparison tokens, qualification tokens, runtime, and stop reasons.

### Combined acceptance

Accept the complete experiment only if:

- the pandas mechanism is consistently represented either by exact `Series._binop` evidence or an executed,
  source-grounded route to it;
- the initial comparison no longer discards the route because of the `__name__` assignment preview;
- candidate diversity does not create a new generic-owner regression;
- TypeScript does not lose previously stable implementation mechanisms because of the new grouping contract;
- measured token growth is justified by improved intermediate and final behavior;
- both repositories finish without hidden range loss, empty qualification source, or unexplained dormant leads.

If the integrated result regresses, disable/revert one accepted step at a time against the same saved inputs to find
the interaction. Do not tune all steps simultaneously or revert the entire set without identifying which boundary
caused the regression.

## Result ledger

Fill this table during implementation. Do not mark a step accepted from a single successful execution.

### Execution record — 2026-08-21/22

All actual-pipeline runs used the unchanged workspace profile, reused the prepared repository indexes, enabled final
evidence selection, and disabled explanation generation. The Node 24 runtime bundled with the workspace was used for
the real CodeGraph bridge because the system Node 20 lacks `node:sqlite`. An optional Obsidian `local_notes` source
reported a native-module ABI warning under that runtime; source-code retrieval continued and no deterministic fallback
was used.

1. **Contrast-preserving request analysis — accepted, attempt 1.**
   `request_analysis_stage_requirements.md` now requires concrete code/API/path contrasts to retain both forms and
   their differing property. Two live pandas request-analysis calls retained the operator-versus-`Series.add(...)`
   result-name contrast while keeping `Series`/`add` repository-facing and `s1`/`s2` contextual. Two live TypeScript
   calls retained the watch/non-watch and direct-import/wildcard-re-export distinctions and did not describe the
   compiler as external. No retry was added.
2. **Complete CodeGraph range resolution — accepted.** The existing parallel batches of at most 80 ranges were
   retained. Focused batch tests passed. The integrated pandas smoke resolved the complete owner set rather than
   stopping at a first-80 slice. This stage incurred local bridge work, not LLM tokens.
3. **Shared source views / compact serialization — best-effort retained, attempt 3.** Attempt 1 created a
   83,633-character / 34,234-token comparison payload. Attempt 2 removed more fields but a stochastic input reached
   the explicit 100,000-character cap (101,807). The retained compact `views`/`owners`/`groups` form keeps all
   owners and view references while using short keys: 48,004 characters and 24,636 comparison tokens in the pandas
   smoke; 42,598 and 46,259 characters with 19,116 and 20,650 comparison tokens in the TypeScript acceptance runs.
   It is below the cap but remains expensive and is not quality-accepted.
4. **Executable-line preservation — accepted, attempt 1.** A compact view now prioritizes complete executable
   return/call/reference lines above a leaf-name assignment. The focused fixture exposes
   `return self._binop(...)` rather than `flex_wrapper.__name__ = name`; 30 focused tests passed.
5. **Bundled real-LLM owner comparison — mechanically accepted, quality open.** Two real comparison calls on the
   compact `flex_wrapper` fixture selected the owner while seeing the `_binop` call (738 and 723 tokens). The full
   pandas behavior remained stochastic, so this does not establish end-to-end selection stability.
6. **Disclosure and qualification integration — mechanically accepted, quality open.** The diagnostic pandas smoke
   `run-20260821T224935Z` promoted exact `pandas/core/series.py::Series::_binop` as direct evidence. No empty
   qualification source appeared. The playbook's separate pair of qualification-only runs was subsumed by the two
   more demanding final-selection runs below and should be repeated only if this boundary is revisited.
7. **Integrated acceptance — not accepted.**
   - Pandas `run-20260821T225305Z`: `partial/false`, one implementation-Oracle overlap, 81,000 recorded retrieval
     tokens; the early route was useful but final selection chose `ops.py` and generic Series/test evidence rather
     than `_binop`.
   - Pandas `run-20260821T225808Z`: `partial/false`, 75,443 tokens; it followed an unrelated sparse-Series branch
     and did not retain `_binop`.
   - TypeScript `run-20260821T230249Z`: `partial/false`, two implementation-Oracle overlaps, 85,166 tokens; final
     evidence included Builder and BuilderState mechanisms.
   - TypeScript `run-20260821T231406Z`: `partial/false`, two implementation-Oracle overlaps, 76,599 tokens; final
     evidence retained Builder, watch, and test-side mechanisms.

The concrete preview-loss bug is fixed, and the comparison stage no longer silently drops structurally resolved
owners. However, the full experiment is **not accepted**: it adds roughly 19k–23k comparison tokens to TypeScript
runs, while pandas remains unstable and sometimes takes a generic sparse branch before the right owner can be
selected. Do not tune this same combined change further. Map future failures to `IOC-1` and separately investigate
upstream initial query/ranking diversity before revisiting the comparison policy.

### Follow-up correction — held owners across obligation variants (2026-08-22)

The statement above was too broad: structurally resolved held owners could still disappear when their file/obligation
pair was outside the later two-variants-per-path guardrail. The correction and measured runs are documented in
`retrieval-changelog.md` under “Held-owner comparison loss and file-group correction.” Owner comparison now groups
once per admitted file across obligations; `_binop` reached qualification and final selection in the first measured
run that contained its raw Qdrant range. Stability and comparison cost remain open under IOC-1.

| Step | Attempt | Two successful isolated runs | Token/runtime result | Decision | Remaining issue |
|---|---:|---|---|---|---|
| 1. Contrast-preserving queries | 1 | Yes: 2 pandas + 2 TypeScript live calls | No retry | Accepted | None observed |
| 2. Complete CodeGraph resolution | Existing | Yes: focused replay / integrated smoke | Local bridge only | Accepted | Scale trace remains in IOC-1 |
| 3. Shared source-view serialization | 3 | Deterministic serializer tests | 48,004 chars / 24,636 smoke tokens | Best-effort retained | Cost and ranking quality |
| 4. Executable-line preservation | 1 | Yes: focused fixtures | No added call | Accepted | Broader fixture coverage later |
| 5. Bundled owner comparison | 1 | Yes: 2 real LLM fixture calls | 738 / 723 fixture tokens | Mechanically accepted | End-to-end stability |
| 6. Selected-owner disclosure/qualification | 1 | One integrated smoke | `_binop` direct in smoke | Mechanically accepted | Separate pair not run |
| 7. Integrated acceptance | 1 | 2 pandas + 2 TypeScript full runs | 75,443–85,166 total tokens | Not accepted | pandas instability; comparison cost |

## Final report template

When all steps are finished, report:

1. which steps were accepted, retained as best effort, or reverted;
2. the three-attempt history for every unstable step;
3. the exact behavior now observed at every evidence-loss boundary;
4. measured token/runtime changes by stage and end to end;
5. pandas and TypeScript final evidence outcomes;
6. unresolved cases that were not naturally exercised;
7. whether the complete idea should be kept, revised later, or avoided.

Reference detailed run artifacts in `services/retrieval/docs/retrieval-changelog.md` rather than duplicating long
logs here.
