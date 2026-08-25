# Initial Evidence-Region Experiment

## Scope

This experiment changes only the representation between the single canonical-snippet pool and initial owner
comparison. It does not change Qdrant retrieval, exact-range deduplication, CodeGraph owner resolution, canonical
identity merging, the 100,000-character comparison admission policy, round-zero qualification, controller behavior,
or final evidence selection.

The user-authorized execution boundary is two actual TypeScript `microsoft-TypeScript-35468` runs stopped immediately
before round-zero qualification. No downstream acceptance run and no admission-policy rewrite are part of this step.

## Observed problem and baseline

Retained pre-qualification runs `run-20260824T223236Z` and `run-20260824T223430Z` produced 415 and 464 canonical
snippets. Multi-owner resolution contributed at most 80 and 112 extra owner occurrences: 33 ranges produced 113
owners in the first run, and 36 produced 148 in the second. The pools also contained 74/76 nested owners and 55/84
one-line owners. Exact comparison fitting then admitted 329 and 324 top-level owner candidates at 100,000 and 99,986
characters.

The first full downstream checkpoint `run-20260825T000741Z` produced 417 canonical snippets, admitted 323 candidates
at 99,929 characters, used 38,262 initial-comparison tokens, and did not improve final Oracle overlap. This experiment
does not attempt to fix that downstream result; it tests whether structural evidence can be represented with fewer
top-level comparison units without hiding the original owners.

## Attempt 1 hypothesis

One deterministic evidence region can represent structural owners that arose from the same retrieved locality:

- a single resolved owner remains one owner region;
- owners with the same enclosing callable become matched members of one enclosing-callable region while the retrieved
  local ranges remain the visible focus;
- sibling owners supported by the same retrieved range become one sibling region;
- one-line owners remain addressable members rather than mandatory top-level evidence;
- one canonical unresolved range becomes one unresolved region.

Every original canonical snippet must remain addressable through exactly one region. Region selection produces one
focused region card; the comparison model may explicitly promote a member when that member needs separate evidence.
Unpromoted members remain available as dormant structural snippets rather than becoming trace-only.

## Expected effects

- Candidate volume: fewer top-level comparison units, bounded by the number of canonical snippets and expected to
  remove a material part of the 80/112 multi-owner expansion observed in the baseline.
- Tokens: unknown in this isolated step. The unchanged admission fitter may spend saved characters on additional
  files, keeping the request close to 100,000 characters.
- Quality: cleaner comparison units, member-specific source retained, no loss of Builder/BuilderState/watch paths.
- Runtime: small deterministic grouping cost; CodeGraph and LLM call counts remain unchanged.

## Regression risks and rollback criteria

- Transitive overlapping ranges can create an excessively broad region.
- A nested owner can lose semantic specificity if the enclosing callable replaces the retrieved local focus.
- Member metadata can cost as much as the removed top-level owner representation.
- Region selection can make an original CodeGraph node unreachable to later inspection.
- Strict-schema member promotion can violate the 24/two-per-file limits.

Revert attempt 1 if any original canonical snippet lacks exactly one region membership, a promoted member cannot be
recovered byte-for-byte as its original canonical snippet, either repeat violates lifecycle/selection limits, direct
Builder/BuilderState/watch evidence consistently disappears, or the representation fails to reduce top-level units.

## Verification

Focused deterministic tests cover single owners, enclosing-callable regions, sibling regions, one-line members,
unresolved regions, provenance aggregation, exact one-region membership, member promotion, response validation, and
literal payload accounting. The focused suite is run twice.

If those pass, run the actual TypeScript pipeline twice with `--stop-before-round-zero-qualification`. Inspect region
counts and kinds, member counts, comparison characters/tokens, admitted files, selected regions/promotions, dormant
members, source focus, and the specifically tracked Builder/BuilderState/watch/test paths. Stop and report afterward.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Deterministic evidence regions and member promotion | 1 | 98 tests pass | 98 tests pass | Live comparison remained approximately 38.4K-38.8K tokens | Reverted | One live run passed; the repeat violated the two-per-file contract |

## Results

Focused verification passed twice with 98 tests. It proved exact one-region membership, non-transitive range grouping,
single/nested/sibling/unresolved construction, member-specific source views, local-focus disclosure, exact member
promotion, literal payload fitting, and shared 24/two-per-file runtime validation.

### Live run 1 — mechanically complete, mixed quality

`run-20260825T010258Z` stopped before qualification as requested:

- 405 canonical snippets across 81 files became 348 regions with all 405 members represented exactly once;
- kinds: 152 single-owner, 136 unresolved, 46 enclosing-callable, and 14 sibling regions;
- 60 regions were synthetic; the pool contained 83 nested and 39 one-line members;
- the unchanged admission fitter admitted 245 regions across 27 files at 99,901 characters;
- the newly measured unbounded request was 139,503 characters for all 348 regions;
- the comparison payload contained 245 regions and 80 member descriptors; it used 38,788 tokens;
- the LLM selected the maximum 24 regions across 13 files and promoted zero members;
- qualification preparation used 14,715 source characters and 37,775 total characters; the qualification LLM was not
  called;
- all region lifecycle and canonical-member membership invariants passed.

The selection retained strong Builder/BuilderState/watch evidence, including
`forEachReferencingModulesOfExportOfAffectedFile`, `createBuilderProgram`, `updateShapeSignature`,
`updateExportedFilesMapFromCache`, `invalidateProjectAndScheduleBuilds`, and `createWatchProgram`. It also selected
clear noise or weak context: a diagnostic-message range, two `tsbuild.ts` status constants, multiple broad
server `Project`/`Session` regions, and tsserver project-reference tests. Because the fitter spent the saved structural
units on member metadata and additional candidates, comparison cost did not fall.

### Live run 2 — contract failure

`run-20260825T010523Z` reached the real comparison call but failed explicit response validation:

- 443 canonical snippets became 356 regions with complete 443-member accounting;
- kinds: 130 single-owner, 174 unresolved, 39 enclosing-callable, and 13 sibling regions;
- the fitter admitted 252 regions across 22 files at 99,962 characters;
- the unbounded request was 146,571 characters;
- the comparison used 38,414 tokens;
- the model selected ten regions and no promoted members, but selected three regions from `builderState.ts`:
  `updateShapeSignature`, `updateExportedFilesMapFromCache`, and
  `getFilesAffectedByUpdatedShapeWhenModuleEmit`;
- the existing two-per-file invariant rejected that response with
  `initial_owner_comparison_file_limit_exceeded:g4`. Nothing was silently clipped and qualification did not run.

The failure is not evidence that those three regions were poor; all three are directly relevant. It exposes a
conflict between semantic selection and the hard two-per-file limit, which the current global JSON schema cannot
express per group. Changing that schema or limit is a separate experiment and was not authorized here.

## Decision

Attempt 1 is reverted. Candidate volume fell by 14% in the successful run (405 -> 348 top-level units), but the
unchanged budget filler still saturated 100,000 characters, admitted fewer files than the previous owner payload,
did not reduce comparison tokens, produced mixed selections, promoted no member, and failed repeatability. No second
implementation attempt, admission-policy change, downstream run, or silent deterministic repair was performed.
