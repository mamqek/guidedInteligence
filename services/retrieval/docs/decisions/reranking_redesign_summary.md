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
