# Bounded unresolved comparison source experiment

Baseline checkpoint 803f5e2. Vue corrected baselines 235805Z/235815Z/003449Z:
1/2 each, partial/false, 51684/59197/48013 retrieval tokens. TypeScript controls
000114Z/000333Z/000343Z: 4/4 each, partial/false, 95024/100609/111020 tokens.

Observed boundary: indexed test range L220-246 survives retrieval and admission,
but unresolved_owner_unchanged routes it through the 80-character regex compactor.
All Symbol-specific behavior disappears. This is a visibility defect, not a recorded
LLM rejection rationale. See the callable-restoration note and open-questions registry.

Variant 1 changes only comparison preparation for unresolved owners: retain full
retrieved source if it fits 1024 characters including labels; otherwise take a contiguous
window centered on a line matching the most distinct recorded retrieval terms, growing
outward within the same budget. No matches means a leading window. Explicit omission
markers and clipped-line labels prevent partial text looking complete. Original views
and owner identities remain untouched. No test-specific policy or oracle input.

Use the existing preparation stage before admission; admission measures the actual
rendered payload, so no hidden budget growth. Named-owner preparation, prompts, ranks,
qualification, controller and final limits remain unchanged. No new model calls. Risks:
larger views crowd out admitted snippets, and incidental matched terms can misfocus long
ranges. Do not assume higher file count or fewer tokens follows from better visibility.

Verify renderer bounds, contiguity, source preservation and unchanged resolved owners;
then two real selector replays on saved input, changing unresolved views only. Replays
hold admitted pool fixed to isolate visibility and do NOT replace admission/full runs.
Then three actual Vue runs, final selection on and response generation off, followed by
three TypeScript regressions with unchanged model/index. Audit all evidence-loss boundaries
for regressions. At most three variants; revert unhelpful/attributably regressing behavior.
No thesis edits.

## Variant 1 measurements

Focused verification: 100 tests passed. Full suite: 496 tests, 492 passed; the same
three index-setup fixture errors (missing lexical_ranking_profile) and one requirements
manifest failure (analyze_qualified_file_leads) remain from the checkpoint.

Two real fixed-pool selector replays on 003449Z, recorded as unresolved-selector-1/2:
the first selected source plus the Symbol test; the second selected source alone.
Costs 34079/34312 tokens. Payload 44912 -> 91987 characters, before live admission.
These diagnose visibility only; neither replaces a full run or proves selection stability.

| Actual Vue run | Oracle files | Coverage/sufficient | Retrieval tokens | Admitted owners/files |
|---|---:|---|---:|---|
| run-20260915T012705Z | 1/2 | partial/false | 52477 | 54/14 |
| run-20260915T012715Z | 2/2 | partial/false | 60353 | 52/14 |
| run-20260915T012726Z | 2/2 | partial/false | 73112 | 55/17 |

Mean 61981 tokens versus checkpoint mean 52965 (+17.0%). Original source is present
in all three finals. The exact L220-246 test range is retrieved, structurally unresolved,
canonicalized, admitted, and fully visible including Symbol assertions in all three.
Total comparison inputs are 60862/60051/61533 characters under the unchanged 60K
crossing-item policy and 100K hard guard. Larger source reduces admitted candidates;
it does not bypass admission. Source ranks and graph/index scopes were not changed.

- 012705Z: initial selector leaves the entire test file dormant despite visible Symbol
  behavior. No test qualification/controller action/final evidence follows. The selector
  returns no rationale; do not invent one or describe this as a retrieval absence.
- 012715Z: selects L220-246. Qualification initially defers it, correctly noting that
  it does not test a Symbol against a non-Symbol type. Round 2 within-file search and
  requalification retain it as navigation-only behavioral reference, not obligation proof.
  That exact test range survives final selection.
- 012726Z: initial selector chooses makeInstance L149-168 and an unrelated frozen-object
  test. Qualification rejects the latter and promotes the helper as navigation. Ordinary
  owner maturation also reaches the Symbol range, which is promoted as navigation;
  final selection retains makeInstance, not the Symbol range. The file-level 2/2 therefore
  does not mean identical snippets or complete behavioral evidence in both successful runs.

The existing source formatter path remains incomplete (styleValue behavior); no automatic
Oracle reservation, obligation credit, prompt change or budget increase was introduced.
Real audit artifacts: testing/codeRepoQA/incremental-restoration/unresolved-vue-audit.json.
## TypeScript regression and decision

| Actual TypeScript run | Focal Oracle files | Coverage/sufficient | Retrieval tokens | Admitted owners |
|---|---:|---|---:|---:|
| run-20260915T013159Z | 2/4 | partial/false | 89011 | 58 |
| run-20260915T013209Z | 4/4 | partial/false | 109420 | 58 |
| run-20260915T013219Z | 1/4 | partial/false | 101239 | 54 |

Mean 99890 versus checkpoint mean 102218 (-2.3%). This does NOT compensate for
the quality regression against three 4/4 controls. All six runs were actual fresh-analysis
pipeline runs, with final selection enabled and response generation disabled. Both Qdrant
collections were verified before starting (Vue 4350, TypeScript 83408 points) and reused.

Exact prepared-pool counterfactuals reproduce current admission IDs and character counts,
then restore only the old unresolved rendering. Reconstructed raw source also reproduces
every recorded unresolved view. Old/new admitted owner counts:

- Vue: 116/54, 118/52, 118/55.
- TypeScript: 64/58, 70/58, 74/54.

This proves a capacity effect, but not that capacity caused each final loss:

- 013159Z: both Builder and BuilderState have raw hits and canonical owners. Builder
  and the issue-specific BuilderState owners are outside admission under BOTH renderers.
  Only getFilesAffectedByUpdatedShapeWhenNonModuleEmit L515-523 represents BuilderState;
  its unchanged view concerns out/outFile behavior and initial comparison omits it.
  The six additionally admitted owners under the old renderer are editor-service owners,
  not missing Builder owners. Neither Builder file reaches the final pool. WatchMode and
  the Helpers structural participant do survive; final overlap is 2/4.
- 013219Z: raw results include Builder (7 dense/sparse occurrences) and BuilderState (5).
  Canonical owners include forEachReferencingModulesOfExportOfAffectedFile,
  updateShapeSignature, updateExportedFilesMapFromCache and module-emit propagation;
  none enters initial admission under EITHER rendering condition. They consequently do
  not enter comparison/qualification or the final pool. Initial comparison does retain
  WatchMode verifyProjectChanges and verifyTransitiveReferences. Its literal source shows
  verifyTscWatch and createWatchedSystem calls, so there is a source-grounded Helpers lead,
  even though no exact Helpers raw range is returned. Executed controller actions follow
  editor/server/project paths and never perform the WatchMode file expansion. No Helpers
  trace or final candidate is created. This is not final-selection capacity loss.
- 013209Z: all four focal files survive. Old rendering additionally admits some WatchMode
  owners (including createSolutionAndWatchModeOfProject) plus compiler/editor-service
  owners, but their exclusion does not prevent 4/4 in this run.

Fresh analysis/query outputs differ across runs. The patch starts after these stages and
cannot explain those upstream differences. Therefore the numerical comparison is an
acceptance failure, NOT proof that this renderer alone caused the TypeScript losses.
The exact counterfactual isolates admission, not downstream LLM/controller decisions.
Do not dismiss the loss as randomness or claim that old rendering would recover 4/4 on
these same inputs; that was not demonstrated.

**Decision: reverted after variant 1.** The intended text-visibility improvement is real,
but it is not enough to accept the cross-repository runtime change. No compensating
ranking, qualification, reservation or controller heuristic was added. Runtime files and
their tests match checkpoint 803f5e2 again; 97 focused checkpoint tests pass after reversion.
The prior Babel/Flow callable integrity fix is untouched. No new post-reversion full runs
are claimed. Thesis files were not changed.

The next separate investigation is why the current admission priority can leave genuinely
relevant Builder owners outside the prefix even under the old renderer. A renderer-only
experiment should then be compared on identical saved analysis/candidate inputs, retaining
the visibility check as a required invariant, without increasing global evidence limits.

Archived implementation plus its three tests:
testing/codeRepoQA/incremental-restoration/unresolved-source-variant1.patch
(git apply --check verified after reversion). The standalone renderer in
testing/codeRepoQA/unresolved_source_variant.py supports diagnostic replays only; live
retrieval does not import it. Reports are unresolved-vue/ts-audit.json and
unresolved-vue/ts-admission.json in the same artifact directory. No LLM was used for the
deterministic admission counterfactuals.

New measured usage: Vue 185942 + TypeScript 299670 + selector replays 68391 = **554003**
provider-reported retrieval/selector tokens. This excludes older baseline runs, request
analysis, embeddings and wiki generation. No explanations were generated.
