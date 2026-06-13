# Reranking Redesign Summary

## Why this note exists

The detailed token/cost experiments are recorded in the changelog. This note keeps only the high-level conclusion: what ideas were taken from the external sources, what was tested, and what the results imply for the next retrieval redesign.

## Source-driven ideas that were tested

- **Two-stage retrieval / retrieve-then-rerank**
  - Sources:
    - Outcome School, "How does a Reranker work?"  
      https://outcomeschool.com/blog/how-does-a-reranker-work
    - Pinecone, "Rerankers and Two-Stage Retrieval"  
      https://www.pinecone.io/learn/series/rag/rerankers/
    - MongoDB, "What are Rerankers?"  
      https://www.mongodb.com/resources/basics/artificial-intelligence/reranking-models
  - Main idea used here:
    - broad retrieval should stay cheap,
    - expensive relevance selection should run only on a reduced shortlist,
    - reranker cost grows with query-candidate pairs, so repeated per-candidate reranking is structurally expensive.

- **Vector database as first-stage recall, not as the place to solve second-stage cost**
  - Source:
    - Analytics Vidhya, "Choosing the Right Vector Database for RAG and AI Applications"  
      https://www.analyticsvidhya.com/blog/2026/06/vector-database-comparison/
  - Main idea used here:
    - Qdrant should remain the broad retrieval layer,
    - cost reduction should focus on the later LLM selection stage instead of weakening first-stage recall.

## What was actually tried

### 1. Cache repeated owner-declaration selections for the whole run

- Goal:
  - reduce repeated LLM reranking calls when the selector payload was identical.
- Result:
  - token cost dropped materially,
  - retrieval quality regressed to `partial / sufficient=False`.
- Meaning:
  - repeated selector calls were not only waste; they were also acting as recovery opportunities in the current pipeline.

### 2. Cache repeated owner-declaration selections only inside one follow-up batch

- Goal:
  - keep the same source-driven idea, but apply it more conservatively than run-wide caching.
- Result:
  - token cost again dropped materially,
  - retrieval quality still regressed to `partial / sufficient=False`.
- Meaning:
  - even local exact caching changes the final accepted evidence enough to break sufficiency.

### 3. Use a lexical-first shortcut before LLM reranking for one high-confidence role

- Goal:
  - let deterministic in-file refinement skip some reranking cost when lexical evidence looked strong.
- Result:
  - saved tokens,
  - final evidence quality still regressed.
- Meaning:
  - local shortcuts are not reliable while later recovery behavior is unstable.

## Main conclusion

The source-inspired direction is still correct, but the current system is not yet shaped like a proper two-stage reranking pipeline.

Right now:

- broad retrieval and expensive declaration selection are too interleaved,
- the same owner file gets reranked repeatedly through per-candidate refinement loops,
- repeated LLM calls are compensating for instability rather than cleanly reranking a stable shortlist.

Because of that, small optimizations such as caching, skipping, or narrowing individual reranker calls reduce cost but also reduce result strength.

## What the redesign should change

The next structural redesign should not start with more caching. It should change the reranking boundary itself:

- gather candidates broadly with Qdrant first,
- group them by `(role, owner_file)`,
- build one compact declaration shortlist per role/file,
- run the expensive owner-declaration selector once per grouped shortlist,
- then let later validation and support expansion work from that grouped result.

In other words, the expensive LLM stage should rerank a stable grouped shortlist, not many near-duplicate candidate refinements.

## Decision

- Keep Qdrant as the broad first-stage retrieval layer.
- Do not pursue more micro-optimizations around repeated owner-declaration selector calls in the current structure.
- Focus the next retrieval redesign on **grouped role/file reranking** rather than per-candidate reranking.

## New constraint after follow-up owner-routing experiments

A later experiment tried to add a cheap deterministic owner-routing stage before grouped snippet refinement, using only path-level and file-level signals to cut Vue overmatch earlier.

That experiment reduced tokens, but it did not solve the real problem:

- on Vue, it still failed sufficiency even after routing down to one file per role,
- on the stable TypeScript case, it redirected some roles onto the wrong owner files and regressed a previously strong run.

So the next redesign should not add another path-only owner gate.

If we add a pre-snippet owner stage at all, it needs stronger ownership evidence than filename/path heuristics:

- function or declaration ownership,
- import/reference convergence,
- caller/callee support,
- and conflict checks against nearby helper files.

In short:

- grouped role/file reranking was the right structural change,
- but Vue-like role overmatch will require a **real owner-resolution stage**, not just a cheaper path scorer.

## Correction: Vue Verification

The earlier Vue owner-overmatch analysis used an invalid verification setup.

The issue did not populate `fixed_by`, but it did include a referenced closing commit in the issue events. The evaluator was therefore building an empty oracle and the runner was using the wrong snapshot for `vuejs-vue-242`.

After fixing CodeRepoQA verification to use the event commit only when timestamp resolution is incoherent:

- Vue issue 242 resolves to the parent of `e422d959452332862a3ea9d70c58bccc475daccb`.
- The oracle files are:
  - `src/exp-parser.js`
  - `test/unit/specs/exp-parser.js`
- The corrected rerun still fails:
  - `coverage_status=partial`
  - `sufficient=False`
  - `overlap_count=0`

This changes the next-step interpretation:

- do not retry the previous Vue-specific codegen/html-parser owner-routing experiments as-is,
- focus the next Vue fix on getting `src/exp-parser.js` promoted from expression/parser diagnostics context into final snippet evidence.

## Owner-artifact relationship pass

The next pass tried the more general version of that idea:

- Step 2 now separates visible surface context from deeper owner artifacts.
- Retrieval can derive owner phrases such as `expression parser` from generic parsing language.
- JS/TS import and `require(...)` references are used as relationship edges.
- Accepted line-level synthesis refs can be materialized into final evidence if bucket selection misses them.

Corrected Vue result:

- baseline `run-20260612T221251Z`: `overlap_count=0`, `coverage_status=partial`, `sufficient=False`, `55638` retrieval tokens.
- owner-artifact run `run-20260613T084723Z`: `overlap_count=1` via `src/exp-parser.js`, `coverage_status=partial`, `sufficient=False`, `71087` retrieval tokens.

TypeScript guard:

- `run-20260613T085108Z`: `coverage_status=partial`, `sufficient=False`, `54862` retrieval tokens.

Conclusion:

- The owner-artifact direction is useful for recall: it can bridge from a surface directive/compiler file to the deeper expression parser owner.
- It is not yet a complete redesign: the pipeline still keeps too much surface-role noise, and the added recovery raises token cost.
- The next change should not add more recall. It should suppress or demote surface support files once a deeper owner artifact is found, so final evidence does not keep spending slots and tokens on adjacent but non-owner files.
