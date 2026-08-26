# Qualification-Scoped Obligation Support Experiment

## Observed problem

In TypeScript run `run-20260826T103528Z`, the unrelated range
`src/testRunner/unittests/tsserver/compileOnSave.ts:120-159` reached final evidence rank 1. Qualification correctly
stated that the range did not show project-reference builds, wildcard re-export resolution, watch-mode scheduling,
or the reported diagnostic. Nevertheless, the promoted candidate inherited five `obligation_ids` from the Qdrant
queries that retrieved it. Mechanism-flow scoring treated those discovery associations as direct semantic support,
giving the isolated test range a flow score of `161.9667`.

## Unchanged baseline

- Qdrant provenance records every obligation-specific query that retrieved an observation.
- Qualification returns one promote/defer/reject decision and one support level per observation.
- `_candidate_from_qualified` copies `observation.obligation_ids` into the promoted candidate.
- Mechanism-flow construction rewards every copied ID as direct obligation support.
- Tests are not globally penalized and final-selection behavior remains unchanged.

## Step 1 — Qualification-scoped obligation IDs

### Boundary

Qualification receives the repository obligations already owned by the retrieval controller. Every decision returns
`supported_obligation_ids`, restricted to known repository obligations but independent from the queries that happened
to retrieve the observation. Candidate construction
uses this qualified subset instead of the complete retrieval provenance set.

No Qdrant query, source disclosure, CodeGraph behavior, causal-role classification, flow weight, controller action,
or final-selection prompt changes in this step.

### Intended effect

- Retrieval provenance remains available in `semantic_discoveries` and trace data.
- A snippet retrieved by five queries no longer receives five direct-support bonuses unless qualification says its
  visible source supports all five obligations.
- A promoted test can still support scenario, trigger, or outcome obligations when its visible source establishes
  them; `file_role=test` receives no blanket penalty.

### Expected cost

The qualification payload gains the obligation IDs and descriptions, and each decision gains one short string array.
Candidate volume is unchanged. Later mechanism-flow payloads may shrink when weak candidates lose inflated priority.

### Risks

- The qualification model may scope valid evidence too narrowly.
- Qualification may incorrectly remap evidence to an obligation that did not retrieve it; the visible-source rule and
  known-ID validation bound this risk.
- Reduced recurrence scores can alter final-request admission under the unchanged character ceiling.

### Verification

1. Focused schema, validation, payload, and candidate-construction tests.
2. Two actual TypeScript `microsoft-TypeScript-35468` runs with response generation disabled and final evidence
   selection enabled.
3. Inspect the compile-on-save range's qualified IDs, flow score/admission, final decision, implementation-Oracle
   retention, coverage, tokens, and candidate counts.

### Acceptance and rollback

Retain only if both actual runs show coherent obligation scoping, no loss of the previously stable implementation
Oracle set attributable to this change, and no new unstable sufficiency result. Revert if the model repeatedly removes
valid direct support, returns invalid IDs, or merely shifts the same false support to final selection.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Qualification-scoped obligation IDs | 2 | Replay 1: pass; compile-on-save received no supported obligations | Replay 2: identical classification boundary | Qualification replay: 8,173 / 8,115 tokens; actual retrieval: 97,031 / 100,105 tokens | Best-effort retained | The noisy range was absent upstream in both actual runs, so its final-flow removal is not naturally exercised |

### Attempt history

| Attempt | Hypothesis | Exact change | Observed failure | Root cause | Future option |
|---:|---|---|---|---|---|
| 1 | Qualification support should be a subset of retrieval-associated obligations. | Validated each returned ID against the observation's Qdrant provenance IDs. | Actual TypeScript attempt `run-20260826T140105Z` stopped during round-0 qualification when visible source was mapped to `explain_trigger`, which had not retrieved that observation. | Retrieval provenance is not a semantic eligibility boundary; enforcing it prevents valid cross-obligation classification. | Attempt 2 validates against all known repository obligations while keeping retrieval provenance separate. |

Invalid actual-pipeline attempts that do not count toward repeatability:

- `run-20260826T135958Z`: CodeGraph could not start because the invoking shell used Node without `node:sqlite`.
- `run-20260826T140409Z`: unchanged initial owner comparison returned an invalid global selection before qualification.
- `run-20260826T140554Z`, `run-20260826T141145Z`, and `run-20260826T141316Z`: unchanged initial owner comparison returned an invalid global selection before qualification.

## Results

Two focused replays used the exact qualification batch from `run-20260826T103528Z` that contained
`compileOnSave.ts:120-159`. Both independently returned `defer/navigation_only`, no supported obligations, and the
explicit finding that compile-on-save affected-file behavior does not establish the issue's project-reference,
wildcard-re-export, or watch-mode path. The calls used 8,173 and 8,115 tokens.

Two valid actual-pipeline runs completed with final selection enabled:

- `run-20260826T140738Z`: `partial/false`, one implementation Oracle, 97,031 retrieval tokens;
- `run-20260826T141453Z`: `partial/false`, two implementation Oracles, 100,105 retrieval tokens.

Both produced coherent narrow obligation assignments. Neither retrieved the compile-on-save range, so they do not
exercise its downstream score directly. The closest unchanged disabled-dormant baselines,
`run-20260826T101602Z` and `run-20260826T102023Z`, retained three and two implementation Oracles and used 101,551
and 113,486 tokens. The first new run's lower Oracle overlap is a regression signal, but its candidate inventory
differed before qualification; it cannot be attributed to scoped obligation support. Sufficiency remained unchanged.

## Decision

Attempt 2 is retained as best-effort. It repeatably fixes the intended qualification boundary and removes the false
equivalence between retrieval provenance and semantic support. Natural end-to-end removal of the exact noisy range
remains unexercised, so the change is not labeled fully accepted. No test-role penalty, causal-role adjustment, flow
weight change, or final-selection prompt change is included.
