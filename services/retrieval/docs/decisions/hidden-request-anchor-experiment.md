# Hidden request-anchor visibility experiment

Baseline runtime: 803f5e2, with the broad unresolved-source variant reverted.
Related boundary: IOC-1 / unresolved comparison visibility. The previous experiment
made Vue's Symbol test visible but failed TypeScript acceptance (2/4,4/4,1/4).

This experiment changes only unresolved comparison-source preparation, before admission.
Resolution still runs first; complete resolved owners are untouched. Derive exact code-shaped
names from the literal user request (capitalized identifiers, camelCase or snake_case;
minimum three characters). A name must also be a recorded retrieval match and occur
case-sensitively in original source, but not anywhere in the candidate's compact views.
Do not treat ordinary lower-case prose terms as identifiers or infer missing symbols.
This is a conservative lexical visibility gate, not semantic relevance certification.

For an eligible candidate, keep every old compact view and append ONE contiguous source
window around a missing name to one view. Maximum seven lines / 512 added characters,
with exact line labels. Total rendered text across that candidate's views must fit 1024
characters. If no witness fits, leave the candidate unchanged and record why. No extra
source reads, graph calls, LLM calls, ranking bonus, obligation credit or reservations.
Trace witness name/range/size and skip reasons. No paths or oracle-specific conditions.

Risks: code-shaped English words or unrelated identifiers can match; same name elsewhere
in compact views can suppress useful context; some genuine lowercase identifiers will
not activate; additional text can still displace candidates. Budget/schema/controller/
qualification/final selection and model/index scope stay fixed. No thesis edits.

Verification: focused gate/budget/context/identity tests; saved-pool deterministic
visibility/admission comparisons for Vue and TypeScript (including prior failing inputs),
then two real fixed-pool selector replays, labelled diagnostics. Three fresh Vue actual
pipeline runs and three TypeScript regression runs, final selection on, response off.
Measure actual tokens, oracle files and first evidence-loss boundary. At most three
variants; archive/revert if repeatable gain and regression safety are not demonstrated.
Do not explain differing fresh-run scores as causal proof without paired input evidence.

Variant 1 failed saved-input specificity: "The" and "Cannot" in comments/messages
passed capitalization-only filtering. No live calls were run on it. Variant 2 adds a
lexical code-use requirement at the hidden occurrence: the name must be followed by
a call parenthesis or member-access dot. This is not AST proof (code-like text in a
comment can still match), but excludes the observed prose triggers without a growing
testcase-specific stopword list. Current tests include this counterexample.

## Focused results

106 focused tests pass. Full suite: 502 tests, 498 pass; same three index-setup fixture
errors and one requirements-manifest failure as the checkpoint. No new third-party imports.

Saved-pool reconstruction verifies original prepared admission IDs/character counts before
changing anything. On the three prior broad-variant Vue inputs, old -> narrow admission:
116 -> 114 (012705Z), 118 -> 116 (012715Z), 118 -> 117 (012726Z). On TypeScript
013159Z/013209Z/013219Z the narrow rule activates nowhere and preserves counts and costs
exactly: 64/60361, 70/60713, 74/60322. This is a property of those saved inputs, not a
claim that fresh runs must choose the same owners.

Paired actual LLM selector calls on saved Vue 012715Z, each with its own normal admission:

| Condition | Repeat 1 | Repeat 2 | Tokens |
|---|---|---|---|
| Old compact source | assertProp + getInvalidTypeMessage only | same | 20336 / 20576 |
| Narrow hidden-name source | same implementation owners + Symbol test L220-246 | same | 20147 / 20226 |

Two narrow admitted candidates receive witnesses: props.spec.js L236-242 and
render-proxy.spec.js L31-36. The latter is correctly not selected by the selector.
Two compiler-bundle candidates fall beyond admission; no authored focal candidate is
displaced in this paired input. The Symbol candidate has 356 source characters rather
than broad expansion to ~1K. One shared candidate cap includes all old compact views.

These are saved-candidate diagnostics with real LLM calls, not full acceptance runs.
First four selector calls: 81285 tokens.

To isolate visibility from admission, two more old-renderer calls used exactly the new
116-owner admitted pool. Both omitted the Symbol test (20099/20365 tokens). One selected
compiled equivalents as well; the other selected validateProp. Thus candidate removal
alone did not produce the repeated positive selection. Total selector usage: 121749.

## Actual pipeline results

| Case | Run | Focal Oracle files | Coverage/sufficient | Retrieval tokens |
|---|---|---:|---|---:|
| Vue | run-20260915T020544Z | 2/2 | partial/false | 65457 |
| Vue | run-20260915T020554Z | 1/2 | partial/false | 50821 |
| Vue | run-20260915T020605Z | 1/2 | partial/false | 63813 |
| TypeScript | run-20260915T020751Z | 3/4 | partial/false | 105524 |
| TypeScript | run-20260915T020802Z | 4/4 | partial/false | 112429 |
| TypeScript | run-20260915T020812Z | 3/4 | partial/false | 106439 |

All six are fresh actual runs, final selection enabled, explanation disabled. Same
model/config/scopes; verified existing Qdrant collections (4350/83408), no reindex.
Vue mean 60030 versus original checkpoint controls 52965 (+13.3%). TypeScript mean
108131 versus 102218 (+5.8%); since the narrow gate did not activate on TypeScript,
that difference is not attributable to extra witness text. Controller/selection paths
and fresh analysis differed. No numerical cost benefit is claimed.

Vue repairs 7/6/4 candidates across the complete pool, not all admitted. L220-246 is
raw-retrieved, canonicalized as unresolved, admitted and shown with the Symbol calls
and assertions in all three comparisons. Nevertheless none of the three initial
selectors chooses that exact range:

- 020544Z chooses makeInstance and an unrelated duplicate-method/boolean test fragment.
  Qualification rejects the latter and promotes makeInstance as navigation. Subsequent
  test-file search obtains ordinary mismatch assertions. Final selection retains the
  neighboring L277-316 tests, NOT the repaired Symbol range.
- 020554Z and 020605Z leave the test file dormant at initial comparison despite visible
  Symbol code. It does not reach qualification, controller recovery or final evidence.
  The selector contract gives no rejection rationale; none is invented here.

This differs from the controlled saved-input result: the isolated visibility gain is
repeatable, but final quality improvement is not. One higher file count is not proof
that the intended range is being retained. The existing tests themselves do not demonstrate
the reported Symbol-to-non-Symbol mismatch; no automatic obligation credit was granted.

TypeScript activates zero repairs in all three runs. Exact reconstructed prepared pools
and admission verify ALL candidate objects remain equal with the rule on/off:
68/60036, 77/60615, 70/60451 owners/characters. The third diagnostic initially failed
because its reconstruction clipped an unresolved merged view as if it had a resolved
owner; the diagnostic was corrected to preserve raw unresolved view ranges and whitespace,
then passed exact reconstruction. No live code was changed for this diagnostic correction.

The two TypeScript misses are pre-existing boundaries on these inputs, not narrow-rule
effects: 020751Z has 21 raw Builder dense/sparse occurrences and canonical Builder owners,
but none enters admission under either condition; no Builder qualification/final candidate
follows. 020812Z retrieves the Helpers HostOutputWatchDiagnostic interface but leaves it
outside admission. No WatchMode file expansion executes, and no Helpers trace is created.
020802Z retains all four focal files. Do not blame inactive witness expansion for these
misses or infer raw-retrieval absence from the final scores.

## Decision

**Reverted after variant 2.** The narrower gate substantially reduces capacity impact and
passes the isolated visibility/selection checks, but the fresh Vue runs do not demonstrate
repeatable final benefit. Do not call the mechanism pointless, and do not call it an accepted
end-to-end repair. Do not add another gate or force test selection to manufacture Oracle
overlap. The remaining focal loss is initial comparison deciding against visible context,
not resolution replacing that context with an owner.

Runtime matches checkpoint 803f5e2 again, including the retained Flow parser fix. After
reversion 97 focused checkpoint tests pass. No post-reversion full runs claimed. Thesis
and unrelated changes untouched. The patch (including nine focused tests) is archived at
testing/codeRepoQA/incremental-restoration/hidden-anchor-variant2.patch; git apply --check
passes. testing/codeRepoQA/hidden_anchor_variant.py is diagnostic-only and not imported
by runtime. Detailed reports are hidden-v2-vue-audit.json, hidden-v2-ts-audit.json and
hidden-v2-live-ts-*-admission.json in that artifact directory; paired selector traces and
the rejected first gate's admission outputs are preserved too.

Measured new usage: 180091 Vue + 324392 TypeScript + 121749 selectors = **626232 tokens**.
Excludes earlier experiments, request analysis, embeddings and wiki generation.
