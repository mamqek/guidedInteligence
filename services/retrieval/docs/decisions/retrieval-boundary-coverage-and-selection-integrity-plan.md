# Retrieval boundary coverage and selection integrity experiment plan

Status: completed and measured on 2026-09-01. Change 1 was rejected after three live variants;
Changes 2–4 were retained with the bounded contracts described below.

## Objective

Test four independent corrections exposed by the 2026-09-01 20-case repetition campaign. The work must preserve
the current successful connected-mechanism behavior while improving cases that disappear at initial admission,
navigation continuation, final identity grounding, or packet allocation. Each change is implemented and measured
separately before any combined acceptance run.

The four changes are:

1. disclose strong zero-qualified file hypotheses;
2. preserve a bounded continuation and final-comparison route for unique navigation evidence;
3. make final candidate identity and redundancy decisions source-verifiable;
4. admit independent island representatives before optional sibling context.

No testcase path, Oracle filename, repository name, language, or issue-specific term may appear in production
eligibility or ranking logic.

## Evidence motivating the plan

### Initial-admission loss

In TypeScript 2953, `src/lib/extensions.d.ts` appeared in raw retrieval in all four campaign runs. It reached round
zero in only `run-20260901T093841Z`; in the other three runs it remained a set of unowned file ranges and never
reached qualification or final comparison. The successful admission was sent to final comparison but not selected.
The current dormant-file action requires distinct structural owners, so a declaration or manifest represented only
by file ranges can remain ineligible despite repeated retrieval support.

Vue 6301 showed the same boundary for `packages/vue-server-renderer/package.json`: raw retrieval contained the file
in all four runs, but only `run-20260901T094735Z` admitted, compared, and selected it.

### Navigation continuation and scheduling loss

In TypeScript 46770 `run-20260901T075900Z`, the selected
`moduleNameResolver.ts::createModuleResolutionCache::createPerModuleNameCache::set` observation was initial rank 3,
recurred four times, and was retained as a navigation lead. Its visible cache setter did not directly establish any
NodeNext resolution obligation, so zero contributing obligation IDs was a defensible judgment for that exact owner.

The controller did not lack a continuation. It enumerated four obligation-specific `InspectOwnerContinuation`
actions rooted at that observation in every round. None executed. The two ordinary slots instead went to earlier
test, `program.ts`, `types.ts`, and deferred-observation scopes. The correct file therefore remained represented by
the weak cache owner, and the navigation candidate was omitted from final comparison in that run. This is scheduler
starvation of an existing grounded continuation, followed by a final-admission loss; it is not raw-retrieval loss.

### Final candidate identity loss

In Vue 10803 `run-20260901T082309Z`, `src/platforms/web/server/modules/dom-props.js::renderDOMProps` was disclosed,
qualified as direct evidence, and presented in the highest-scoring final mechanism flow. The consolidation response
described `renderDOMProps` correctly but attached that description to the candidate ID for
`test/ssr/ssr-string.spec.js::renderVmWithOptions`. It rejected the actual `renderDOMProps` candidate ID.

Opaque candidate IDs were already present, so merely adding IDs to the prompt is not a correction. The missing
invariant is that a selected record's claimed source support must belong to the candidate identified by that record.

### Packet concentration

Across the two 80-run campaigns, mechanism-comparison input increased from an average 5.56 snippets / 2.76 unique
files to 7.96 snippets / 3.96 unique files, while the eventual selected-file mean decreased. Packet construction is
therefore not generally hiding files, but optional siblings can still consume capacity before an independent
singleton or unique island receives a useful representation. Presentation and final acceptance must remain separate
measurements.

## Change 1 — Strong zero-qualified file hypotheses

### Boundary

Extend the existing dormant-file inspection stage. Do not add a new repository search and do not bypass
qualification.

### Proposed contract

- Permit one file hypothesis when a file has zero retained direct/navigation observations but has multiple strong,
  independently retrieved file ranges even when CodeGraph exposes no structural owner.
- Treat structural-owner groups and unowned file-range groups as two adapters behind the same action contract.
- Require unresolved-obligation breadth, repeated or multi-channel retrieval support, and source-level request
  terms. A path match alone is insufficient.
- Inspect only already-retrieved ranges, merge overlaps, and disclose at most the existing bounded batch size.
- Attempt a normalized file hypothesis once per run, including zero-result or all-rejected outcomes.
- Send the disclosed ranges through the ordinary qualification contract. Admission is not final acceptance.

### Expected effects and risks

- Quality: declarations, manifests, and other graph-poor artifacts receive one real semantic judgment instead of
  behaving as permanently rejected dormant data.
- Tokens: at most one existing qualification request when the action activates; no new round or retry.
- Risks: repeated lexical noise can activate an irrelevant artifact, and large declarations can contain many
  redundant ranges. The multi-channel/obligation gate and merged-range cap are mandatory.

### Verification

- Focused fixtures for unowned declaration ranges, manifest ranges, overlap merging, one-attempt novelty, and
  all-rejected completion.
- Actual positive cases: TypeScript 2953 and Vue 6301, two runs each.
- Regression guard: TypeScript 35468 twice with final selection enabled and response generation skipped.

### Result

Rejected. Three graphless file-range adapter variants on TypeScript 2953 selected `src/lib/core.d.ts` rather than
the Oracle `src/lib/extensions.d.ts` (`run-20260901T211830Z`, `212617Z`, `213102Z`, and final ranking adjustment
`213433Z`). Repeated lexical range support did not distinguish the central declaration from the larger declaration
surface reliably enough. The adapter and its tests were removed. An independent deterministic source-decoding fix
was retained after an actual run exposed legacy cp1252 input: owner disclosure now tries UTF-8/UTF-8-SIG and then
cp1252/latin-1 rather than crashing on a strict UTF-8 read.

## Change 2 — Unique navigation continuation and comparison

### Boundary

Unify the scheduling and final-comparison treatment of a retained navigation lead without converting navigation
into direct proof.

### Proposed contract

- Fold obligation-specific continuation duplicates into one normalized continuation effect per source owner.
- Persist that continuation independently of the per-round catalogue.
- If it is the only retained representation of its file/island and remains grounded in an explicit qualification
  handoff, give it one bounded later ordinary opportunity after revalidation. Do not add an action slot.
- If the continuation is still unexecuted or remains navigation-only at controller completion, include one concrete
  navigation candidate in final comparison when it is the only qualified representation of that file/island.
- Preserve `navigation_only` provenance. It may explain a route or missing handoff but cannot establish an
  obligation or sufficiency by itself.

### Expected effects and risks

- Quality: a correct file represented by an incomplete owner can be matured or at least compared instead of
  silently disappearing.
- Tokens: usually no extra call; one existing controller slot can move to the persisted continuation.
- Risks: navigation can displace more direct work or introduce attractive but non-proving files. Eligibility must
  require retained qualification, concrete handoff text, unique representation, and one attempt per effect.

### Verification

- Focused scheduler replay of TypeScript 46770 `run-20260901T075900Z`: the four obligation variants fold to one
  effect and the continuation remains schedulable after earlier islands consume round-one slots.
- Actual positive case: TypeScript 46770 twice.
- Main regression guard: TypeScript 35468 twice; Builder, BuilderState, WatchMode, and the Helpers trace remain the
  explicit audit targets, with at least the established three-file baseline retained in every valid run.
- Cross-repository guard: Vue 10803 once, verifying that direct evidence is not displaced by navigation.

### 2026-09-01 scheduling-substep result

Implemented only the continuation-normalization and bounded scheduling portion of Change 2. Obligation-specific
`InspectOwnerContinuation` clones for the same observation and source ranges are now one catalogue action carrying
the union of obligation IDs. The frontier ledger preserves first-seen round and obligation recurrence for normalized
effects. Waiting-age fairness covers grounded owner disclosure, relationship expansion, explicit within-file
handoff, and deferred inspection; it excludes broad new-island search and auxiliary pools. Rounds one and two remain
unchanged. After two complete losses, at most one continuation can use slot two in round three. Neither signal creates
another slot or another execution.

The focused tests reproduce four obligation variants, three competing verified relationships, earlier ordinary
scopes, and a competing independent-island action. They prove one normalized action, unchanged first/second rounds,
bounded round-three selection, and no age effect on broad search. The wider focused retrieval suite passes 134 tests.

Actual pipeline runs kept final evidence selection enabled and skipped only response generation:

| Case / run | Implementation overlap | Final files | Coverage / sufficient | Retrieval tokens | Continuation activated |
|---|---:|---:|---|---:|---|
| TypeScript 46770 / `run-20260901T164005Z` | 1 | 3 | partial / false | 101,191 | available in round 3 |
| TypeScript 35468 / `run-20260901T162844Z` | 4 | 5 | partial / false | 115,578 | grounded actions aged |
| TypeScript 35468 / `run-20260901T163358Z` | 3 | 4 | partial / false | 130,184 | grounded actions aged |

The one-round generalized variant is rejected: 35468 `run-20260901T162238Z` retained only Builder (1/4) after an
owner continuation was promoted in round two. The two-round final variant restored the baseline floor: 4/4 and 3/4,
with Helpers selected in both. The 46770 final run retained `moduleNameResolver.ts::resolveModuleName`.

Decision: retain the two-round generalized scheduler and the bounded final-comparison route. The latter admits at
most one navigation-only candidate only when qualification supplied a concrete local handoff and no direct
candidate represents its path. It remains non-proving evidence. TypeScript 46770 `run-20260901T232545Z` and
`233029Z` both retained `moduleNameResolver.ts` with 1 implementation overlap; it was already mandatory in both,
so deterministic tests—not those runs—exercise the fallback admission itself. One preceding run `232201Z` failed
explicitly in initial-owner response validation and never reached this boundary.

Separate downstream finding: 35468 `run-20260901T145629Z` had four file traces selected by the LLM. A hardcoded
two-item post-LLM cap retained the first two payload entries and discarded `tscWatch/helpers.ts` and
`virtualFileSystemWithWatch.ts`. This cap is an order-sensitive presentation safeguard, not a semantic selection;
the separate ranked-file-trace experiment now replaces it. Three frozen-payload replays ranked Helpers 1st/1st/3rd;
capacity-based allocation retained the top three without trimming any of the 11 exact snippets. Actual runs
`run-20260901T175328Z` / `run-20260901T175753Z` retained Helpers in both and produced 4/4 / 3/4 focal overlap.

## Change 3 — Source-verifiable final selection and unique-role decisions

### Boundary

Replace the ambiguous final-selection response records, not the final LLM stage and not its evidence judgment.

### Proposed contract

- Present each candidate with a short stable display label containing its candidate ID, path, symbol, and range.
- Require one candidate-local decision record per submitted candidate: candidate ID, selected/rejected disposition,
  obligation IDs, mechanism role, and a short exact source anchor copied from that candidate's supplied snippet.
- Validate that every candidate ID was submitted, appears once, and owns its stated source anchor.
- Do not infer ownership from free-form explanation text.
- If an anchor matches no candidate or multiple candidates, surface an explicit invalid final-selection response;
  do not retry the LLM and do not substitute a deterministic relevance decision.
- A uniquely matching exact anchor may be used to correct a mismatched ID only as an explicit, traced identity
  normalization. Measure this as a second variant; do not enable it unless the stricter candidate-local contract
  still produces mismatches.
- Require every rejection as redundant to name one or more selected candidate IDs that represent the same grounded
  proposition or mechanism role. Validate that the representatives were submitted and share the relevant island,
  connection, or obligation context. A unique role with no valid representative cannot be rejected as redundant.

This is narrower than unconditional per-file preservation. Existing path, artifact role, qualification rationale,
provenance, obligation IDs, island identity, and mechanism flows already reach the selector. The new behavior makes
identity and claimed redundancy auditable instead of adding a broad one-file guarantee.

### Expected effects and risks

- Quality: prevent the Vue failure in which correct reasoning is credited to the wrong candidate; make loss of a
  unique file/mechanism an explicit model decision.
- Tokens: a modest increase for candidate-local decisions and short anchors; no additional LLM call.
- Risks: exact anchors can be duplicated or copied incorrectly, and requiring a record for every candidate increases
  output size. Anchors must be short and output limits measured before promotion.

### Verification

- Exact saved-payload replay of Vue 10803 `run-20260901T082309Z`.
- Focused tests for swapped IDs, duplicate IDs, absent IDs, anchors belonging to another candidate, ambiguous
  anchors, and valid rejection-by-representative records.
- Actual cases: Vue 10803 twice and TypeScript 35468 twice.

### Result

Retained after two contract refinements. Every submitted candidate now has one decision record. Candidate-specific
strict-schema branches bind each ID to bounded exact source lines that occur in no other submitted snippet; unsafe
backslash/double-quote lines are excluded before request construction. Redundancy targets are likewise constrained
per candidate to IDs sharing pre-LLM island, connection, or credited-obligation context. Runtime validation still
rejects missing/duplicate IDs, wrong or ambiguous anchors, ungrounded redundancy, and more than 14 selections.
There is no retry, ID reassignment, or deterministic relevance fallback.

Vue `run-20260901T231436Z` / `231748Z` both retained `dom-props.js::renderDOMProps` under its own candidate ID with
1 implementation overlap. TypeScript 35468 `run-20260901T225105Z` / `225612Z` retained 3/4 and 4/4 focal files,
respectively, while validating all 13/13 and 11/11 submitted candidate identities. Rejected intermediate runs are
diagnostic evidence: `221751Z` exposed an overlapping-range anchor; `222309Z` / `222849Z` exposed strict-schema
unsafe string literals; `230507Z` exposed an invented redundancy representative. Each failure was surfaced
explicitly and corrected at schema construction rather than retried.

## Change 4 — Independent representation before sibling enrichment

### Boundary

Change deterministic island-packet request construction only. Do not automatically select any added candidate as
final evidence.

### Proposed admission order

1. Run the unchanged normal-flow reducer and retain every resulting mandatory seed.
2. Give each qualified independent singleton or otherwise unrepresented island one compact representative unit.
   Duplicate obligation coverage in another island is not a reason to exclude it.
3. Complete the compact base packet around islands containing mandatory seeds.
4. Spend remaining capacity on role-diverse sibling context, round-robin across represented connected islands.

When capacity is insufficient, optional sibling enrichment yields before the first representative of a qualified
independent island. Whole-unit character accounting and the existing total input budget remain unchanged.

### Expected effects and risks

- Quality: preserve precise baseline evidence, independent alternatives, and coherent connected context without one
  strong island consuming all optional capacity.
- Tokens: no new call and no larger input budget; composition may change while serialized size remains bounded.
- Risks: weak singleton islands can crowd out genuinely useful second/third steps of a central mechanism. Only
  qualified singleton/island representatives participate, and connected base packets remain ahead of optional
  enrichment.

### Verification

- Deterministic fixtures for mandatory-seed invariance, duplicate-obligation singleton admission, sibling yielding,
  whole-unit budget crossing, and round-robin enrichment.
- Saved-pool comparisons for TypeScript 35468, Vue 10803, TypeScript 46770, and pandas 10068.
- Actual acceptance after the first three changes are independently decided: TypeScript 35468 twice, Vue 10803
  twice, TypeScript 46770 twice, and pandas 10068 once.

### Result

Retained with obligation-bearing eligibility. Admission now preserves all normal-flow seeds, attempts one
representative from each otherwise unrepresented island before seeded siblings, completes seeded base packets,
then enriches represented connected/grouped islands round-robin. An independent representative must carry a
credited obligation, except for the separately bounded grounded-navigation route. This refinement followed Vue
`run-20260901T230946Z`, where a zero-credit supporting fact from `vue-template-compiler/browser.js` was admitted and
selected. Final Vue runs no longer admit that file through the independent reservation; if it appears as a
mandatory normal-flow seed, packet construction correctly does not remove it.

Actual combined results:

| Case / run | Implementation overlap | Mandatory / submitted | Identity selected | Retrieval tokens | Result |
|---|---:|---:|---:|---:|---|
| TypeScript 35468 `225105Z` | 3 | 13 / 13 | 8 | 136,293 | Builder, WatchMode, Helpers |
| TypeScript 35468 `225612Z` | 4 | 11 / 11 | 10 | 137,202 | all four focal files |
| Vue 10803 `231436Z` | 1 | 3 / 3 | 3 | 74,602 | `renderDOMProps` retained |
| Vue 10803 `231748Z` | 1 | 10 / 10 | 7 | 96,331 | `renderDOMProps` retained |
| TypeScript 46770 `232545Z` | 1 | 11 / 11 | 8 | 119,079 | resolver retained |
| TypeScript 46770 `233029Z` | 1 | 8 / 8 | 6 | 102,643 | resolver retained |
| pandas 10068 `233458Z` | 0 | 2 / 2 | 2 | 50,874 | `_binop` absent upstream |

All actual runs were `partial/false`; response generation was skipped and final selection remained enabled. Pandas
reached final comparison with only `core/ops.py::add_flex_arithmetic_methods` and the exact regression test. The
missing `core/series.py::_binop` therefore remains a pre-packet discovery/scheduling loss and is not evidence
against packet ordering.

## Experiment sequence and decision rule

Implement Changes 1–4 in that order, but reset to the unchanged current baseline between measurements. Use no more
than three variants for any change. Diagnostic smoke runs may skip final selection only while checking upstream
boundaries; they never count as acceptance. Acceptance runs keep final selection enabled and skip only response
generation.

For every comparison record:

- run ID, configuration hash, and index signature;
- raw target presence and first loss boundary;
- qualification disposition/kind/obligations;
- actions enumerated, normalized, selected, executed, and productive;
- candidates/files/islands sent to final comparison;
- final candidate IDs and identity-validation result;
- implementation-Oracle overlap, `coverage_status`, `sufficient`, and retrieval tokens by stage.

Reject or revise a change when two main-case acceptance runs show a repeatable loss of established implementation
evidence, unstable sufficiency, or materially higher tokens without a verified boundary improvement. Only after all
four changes pass separately should a combined run test their interaction.
