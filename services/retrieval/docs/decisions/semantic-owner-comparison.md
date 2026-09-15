# Semantic owner comparison experiment

## Boundary and baseline

ORE-1 follow-up, baseline 6f5c17b plus trace-only owner audits. The rejected
metadata election remains disabled. Existing representatives already change;
the experiment tests whether source-grounded comparison makes better choices.
Thesis, qualification, retrieval, indexes, model and final selection stay unchanged.

## Steps

1. Replay a separate real LLM comparator over saved same-file contests. Supply
   exactly one recorded unresolved coverage question and both visible disclosure
   excerpts, not rank, recurrence, obligation counts or qualification conclusions.
   Require behavior, limitations and literal source receipts for both sides.
   Outcomes: replace, complementary, no clear improvement. Neither replacement
   nor complement grants obligation credit or forces final evidence inclusion.
2. Only after repeatable focused benefit, integrate bounded comparisons after
   qualification, before island/controller priority selection. Preserve all owners;
   do not restore the historical qualification contract or extra search policy.
3. If integrated, run two actual TypeScript acceptance runs and two Vue controls,
   with final selection enabled and response generation disabled. Audit each
   activation, replacement, complement and abstention against visible code.

## Focused inputs and admission

Saved runs 20260915T051437Z, 051447Z (TypeScript), 051508Z (Vue).
For each audit round, compare the prior same-file ranked incumbent against newly
present promoted owners. One shared qualified obligation must currently be partial
or missing with a nonempty recorded missing claim. Covered questions are skipped,
even if their missing_claim field contains explanatory text. No oracle-derived
question is added. Deduplicate exact pair/question/source payloads. These are
boundary replays, not live reruns or final recall measurements.

## Expectations and risks

Expected benefit: behavioral propagation can beat a mere reverse-reference lookup;
complementary behavior need not displace its incumbent. Expected cost: one bounded
LLM call per eligible contest, measured from provider usage; no new candidates.
Risks: unresolved questions can be broader than either owner, legitimate abstention
may produce no useful priority change, pair order bias, excerpt truncation, and
new priority still failing to help downstream selection. Source quote validation
does not establish that the semantic conclusion is correct; review each result.

Two identical real-LLM repetitions must show a defensible and repeatable intended
improvement before integration. Maximum three variants, no speculative tuning to
oracle scores. If focused evidence fails, leave the comparator diagnostic-only,
record the failure and do not run an unchanged pipeline claiming acceptance.

## Ledger

| Step | Variant | Repeat 1 | Repeat 2 | Tokens | Decision |
|---|---:|---|---|---:|---|
| Receipt contract: free quotes | 1 | Literal failures | Literal failures | 39,247 | Rejected |
| Receipt contract: source-line enum | 2 | Some accepted | Quoted-code HTTP 400 | 40,720 | Rejected |
| Relative-gain prompt, old receipt contract | 2 | Lookup replacement | Lookup replacement; controls blocked | 44,274 | Not accepted |
| Receipt contract: line-ID enum | 3 | 11/11 valid | 11/11 valid | 50,851 | Contract works in isolation |
| Semantic judgment, line-ID contract | 2 | See audit | See audit | Included above | Integration gate failed |

Variant 1 exposed invalid literal receipts (Markdown backticks and merged lines).
Variant 2 replaces free-form quote strings with exact supplied-line enums. It also
exposes the core reasoning failure: a module-propagation challenger is denied
replacement despite the model explicitly identifying added relevant propagation
and no lost incumbent behavior, because neither proves the whole import contrast.
Variant 3 changes only the relative-comparison instructions: shared insufficiency
is not a reason to reject a visible gain, and function names do not establish an
exclusive downstream use. No case names or desired fixture outcomes enter prompts.

Receipt contract is a separate boundary from semantic judgment: attempt 1 free
quotes failed literal validation; attempt 2 source-line enums triggered provider
HTTP 400 for code containing quotes; attempt 3 uses line-ID enums and resolves
the exact selected line locally. This is source lookup, not a deterministic
substitute for the LLM decision. Semantic judgment has two prompts (initial and
relative-gain clarification). Repeat all fixtures with the corrected transport;
retain every failed response and its usage. No further semantic tuning in this run.

## Final focused result (September 15)

No runtime integration was made. These are **11 saved contests, each invoked
twice through the real LLM**, not new pipeline runs. Baseline metadata ranking
remains active, with earlier trace-only instrumentation unchanged. No new Oracle,
coverage, sufficiency, or end-to-end benefit is claimed. Thesis untouched.

Final artifact: `testing/codeRepoQA/incremental-restoration/semantic-owner-replay-line-ids.json`.
Each row preserves source run, controller round, IDs, exact question, exact source,
both requests, schema, responses, resolved receipts and provider usage.
Earlier `semantic-owner-replay-v1.json`, `v2.json`, `v3.json` retain failed contracts.

| Source run | Contests / decisions | Replace | Complementary | No improvement | Outcome defensible | Outcome AND explanation acceptable | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| TS run-20260915T051437Z | 4 / 8 | 4 | 0 | 4 | 8/8 | 8/8 | 17,920 |
| TS run-20260915T051447Z | 6 / 12 | 0 | 8 | 4 | 12/12 | 8/12 | 27,435 |
| Vue run-20260915T051508Z | 1 / 2 | 0 | 1 | 1 | 1/2 | 1/2 | 5,496 |
| Total | 11 / 22 | 4 | 9 | 9 | 21/22 | 17/22 | 50,851 |

Agreement is reviewer judgment against supplied source, not model self-grading or
hidden-Oracle scoring. A defensible outcome can have an unsupported explanation;
those counts are separate. Ten of eleven final pairs repeat the same outcome.
The Vue split leaves the incumbent in either case, but its complementary label
is not trustworthy question-specific guidance.

### Every final contest

Zero-based rows address the JSON artifact. R/C/N mean replace, complementary,
no clear improvement. All comparisons are same-file.

| Row | Run suffix / round | Incumbent → challenger | Repeats | Review |
|---:|---|---|---|---|
| 0 | 051437Z / 1 | builder.ts export-affected traversal → forEachFileAndExportsOfFile | R/R | Agree twice: visible recursive export-map traversal is closer to the missing re-export route than the truncated incumbent's signature gate/direct-reference branch. The stated loss of gating matters; do not delete the old owner. |
| 1 | 051437Z / 1 | same incumbent → createBuilderProgram::getSemanticDiagnostics | N/N | Agree twice: diagnostic aggregation does not expose the requested export/module route. |
| 2 | 051437Z / 2 | builderState.ts getReferencedByPaths → non-module-emit affected-file function | N/N | Agree twice: broad out/outFile/default-library handling adds no targeted wildcard propagation detail. |
| 3 | 051437Z / 2 | getReferencedByPaths → module-emit affected-file function | R/R | Agree twice: queue, source-file lookup, conditional updateShapeSignature call and recursive reverse-reference expansion add a mechanism beyond the isolated lookup. Neither proves the full bug. |
| 4 | 051447Z / 1 | getAllDependencies → getReferencedByPaths | N/N | Defensible twice: keep forward traversal setup for this question; reverse lookup is not clearly superior. Explanations explicitly note absent enqueue continuation. |
| 5 | 051447Z / 1 | getAllDependencies → FileInfo | C/C | Signature field is a defensible distinct contribution, but both explanations overstate the truncated incumbent as actually following referenced paths. Reject full explanations twice. |
| 6 | 051447Z / 1 | builder.ts export-affected traversal → getNextAffectedFile | C/C | Agree twice: traversal start versus affected-batch/cache sequencing are distinct visible contributions. |
| 7 | 051447Z / 1 | getAllDependencies → module-emit affected-file function | C/C | Forward setup versus reverse propagation can be complementary. Both explanations claim the incumbent follows references despite acknowledging omitted enqueue code. Reject full explanations twice; this does not prove replacement is necessarily required. |
| 8 | 051447Z / 1 | builder.ts export-affected traversal → createBuilderProgram::getSemanticDiagnostics | N/N | Agree twice: no added import-route behavior. |
| 9 | 051447Z / 3 | tsbuildPublic.ts getNextInvalidatedProject → getUpToDateStatusWorker | C/C | Defensible twice for the recorded state/reuse question: reload/watch setup versus visible upstream declaration-change timestamp reuse. NOT the already-covered trigger question. |
| 10 | 051508Z / 1 | props.js assertProp → validateProp | N/C | Agree with N. Disagree with C as question-specific guidance: boolean/default preparation does not expose Symbol coercion during message construction. assertProp already shows the closer getInvalidTypeMessage call. Neither exposes its body. |

### Why the integration gate failed

Rows 5 and 7 use an incumbent excerpt ending at `if (references) {`, followed by
the explicit complete-lines-omitted marker. Queue initialization, seen-map access
and reference-map lookup are visible. Enqueueing those references, completion of
the traversal, and its final result are not. The answers nevertheless describe a
completed forward dependency walk, sometimes citing only its explanatory comment.
A valid line receipt does not establish that the surrounding explanation is
supported. This is a source-grounding failure, not an oracle-score fluctuation.

The narrower success is real: row 3 replaces the lookup twice without claiming
complete obligation satisfaction. But the stage would also generate unsupported
comparison rationales and one questionable complementary label. Stop before live
integration rather than pass those through as trusted contextual reasons. Existing
owners remain available under the unchanged pipeline; the prototype does not
protect, promote, group or delete any of them.

### Verification and cost

- 122 focused tests pass, including five new comparator-contract tests.
- 88 attempted isolated LLM calls across four batches. Eight HTTP 400 requests
  have no provider usage response. Eleven first-batch answers fail local receipt
  validation; their returned usage is included.
- Total **175,092 provider-reported tokens**, including unsuccessful attempts.
  Final working-contract batch: **50,851**. This is experiment cost, not measured
  live-retrieval overhead or wiki-generation cost.
- No full-pipeline runs: source-grounding acceptance did not pass. Running the
  unchanged runtime would not test this prototype.

Future work, not implemented: test visibility-limited contribution descriptions
that do not import an unseen loop body, and require complementary to mean relevant
to the precise missing behavior rather than another part of the surrounding flow.
Do not compensate with ranking bonuses or obligation credit.
