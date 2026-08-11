# Offline Shortlist Signal Audit

Historical traces do not contain the later `obligation_candidate_shortlists_created` event. 
This audit reconstructs a file/obligation candidate universe from Qdrant hybrid/dense/sparse results 
and CodeGraph nodes/edges; it does not claim byte-for-byte replay of the historical shortlist.

## Run coverage

| Case | Run | Candidate files | Oracle implementation files observed | Selected Oracle files |
|---|---|---:|---:|---:|
| `vuejs-vue-242` | `run-20260811T122541Z` | 56 | 2/2 | 1 |
| `vuejs-vue-242` | `run-20260811T122658Z` | 50 | 2/2 | 1 |
| `vuejs-vue-10803` | `run-20260811T130723Z` | 95 | 1/1 | 1 |
| `vuejs-vue-10803` | `run-20260811T130901Z` | 95 | 1/1 | 0 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | 142 | 4/4 | 0 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | 126 | 4/4 | 1 |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` | 109 | 1/1 | 1 |
| `pandas-dev-pandas-10068` | `run-20260811T131236Z` | 122 | 1/1 | 0 |

## Matched owner-survival pool

This comparison asks whether a causal source-owner Oracle file survives while competing against actual files from the same run. The policy uses no Oracle labels: retain every `implementation` file appearing within the top 12 hybrid results of at least one initial obligation, deduplicate across obligations, and cap the request-level pool at 24 files.

| Case | Run | Pool files | Source-owner Oracles retained | Retained owner paths |
|---|---|---:|---:|---|
| `vuejs-vue-242` | `run-20260811T122541Z` | 13 | 1/1 | `src/exp-parser.js` |
| `vuejs-vue-242` | `run-20260811T122658Z` | 12 | 1/1 | `src/exp-parser.js` |
| `vuejs-vue-10803` | `run-20260811T130723Z` | 12 | 1/1 | `src/platforms/web/server/modules/dom-props.js` |
| `vuejs-vue-10803` | `run-20260811T130901Z` | 13 | 1/1 | `src/platforms/web/server/modules/dom-props.js` |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | 16 | 2/2 | `src/compiler/builder.ts`, `src/compiler/builderState.ts` |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | 22 | 2/2 | `src/compiler/builder.ts`, `src/compiler/builderState.ts` |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` | 17 | 1/1 | `pandas/core/series.py` |
| `pandas-dev-pandas-10068` | `run-20260811T131236Z` | 15 | 1/1 | `pandas/core/series.py` |

## Intent-to-query drift

The first intent choice may be unchanged while the stage-requirement LLM changes proposition text or evidence boundary.

| Case | Runs | Repository queries | Boundary/source changes | Shared query obligations | Exact queries | Mean token Jaccard |
|---|---|---:|---|---:|---:|---:|
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` / `run-20260811T130428Z` | 4 / 6 | explain_resulting_effect, explain_trigger, explain_why | 4 | 0 | 0.418 |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` / `run-20260811T131236Z` | 6 / 6 | none | 6 | 0 | 0.486 |
| `vuejs-vue-10803` | `run-20260811T130723Z` / `run-20260811T130901Z` | 6 / 6 | none | 6 | 0 | 0.477 |
| `vuejs-vue-242` | `run-20260811T122541Z` / `run-20260811T122658Z` | 6 / 6 | none | 6 | 0 | 0.537 |

## Feature means

Oracle labels are used only for this evaluation table.

| Feature | Oracle mean | Non-Oracle mean | Difference |
|---|---:|---:|---:|
| `outbound_productive` | 23.625 | 4.846 | +18.779 |
| `unique_outbound_productive` | 17.250 | 4.189 | +13.061 |
| `inbound_productive` | 15.938 | 5.004 | +10.934 |
| `unique_inbound_productive` | 11.250 | 4.312 | +6.938 |
| `query_symbol_overlap` | 3.812 | 0.517 | +3.295 |
| `cross_file_fanout` | 4.500 | 2.211 | +2.289 |
| `obligation_recurrence` | 4.438 | 2.488 | +1.950 |
| `semantic_channels` | 2.500 | 1.101 | +1.399 |
| `bidirectional_productive` | 0.750 | 0.195 | +0.555 |
| `hybrid_present` | 0.875 | 0.322 | +0.553 |
| `semantic_graph_corroborated` | 0.812 | 0.271 | +0.542 |
| `best_hybrid_inverse_rank` | 0.571 | 0.091 | +0.480 |
| `mutation_text` | 0.750 | 0.325 | +0.425 |
| `action_symbol_terms` | 0.500 | 0.175 | +0.325 |
| `graph_present` | 0.938 | 0.677 | +0.261 |
| `executable` | 1.000 | 0.795 | +0.205 |

## Oracle candidate diagnostics

| Case | Run | Oracle path | Selected | Channels | Hybrid rank | Obligations | Query/symbol overlap | Action terms | Unique out/in | Fanout | Hybrid/corroboration/responsibility/chain ranks |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `vuejs-vue-242` | `run-20260811T122541Z` | `src/exp-parser.js` | yes | 3 | 1 | 6 | 3 | 0 | 13/13 | 0 | 2/3/5/5 |
| `vuejs-vue-242` | `run-20260811T122541Z` | `test/unit/specs/exp-parser.js` | no | 3 | 1 | 5 | 2 | 0 | 2/2 | 0 | 3/7/6/6 |
| `vuejs-vue-242` | `run-20260811T122658Z` | `src/exp-parser.js` | yes | 3 | 1 | 7 | 4 | 0 | 13/13 | 0 | 2/2/4/4 |
| `vuejs-vue-242` | `run-20260811T122658Z` | `test/unit/specs/exp-parser.js` | no | 3 | 1 | 5 | 1 | 0 | 2/2 | 0 | 4/7/6/6 |
| `vuejs-vue-10803` | `run-20260811T130723Z` | `src/platforms/web/server/modules/dom-props.js` | yes | 3 | 5 | 6 | 7 | 1 | 16/5 | 4 | 16/3/3/6 |
| `vuejs-vue-10803` | `run-20260811T130901Z` | `src/platforms/web/server/modules/dom-props.js` | no | 3 | 1 | 4 | 6 | 1 | 16/5 | 4 | 1/6/5/8 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `src/compiler/builder.ts` | no | 3 | 12 | 2 | 0 | 0 | 0/0 | 0 | 36/45/48/107 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `src/compiler/builderState.ts` | no | 2 | 8 | 1 | 0 | 0 | 2/0 | 1 | 24/28/63/51 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `src/testRunner/unittests/tsbuild/watchMode.ts` | no | 3 | 1 | 3 | 2 | 1 | 1/0 | 1 | 3/11/7/25 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `src/testRunner/unittests/tscWatch/helpers.ts` | no | 0 | — | 1 | 0 | 0 | 11/4 | 3 | 110/120/119/23 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `src/compiler/builder.ts` | no | 3 | 4 | 3 | 10 | 2 | 32/5 | 3 | 15/10/2/2 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `src/compiler/builderState.ts` | no | 2 | 7 | 6 | 11 | 1 | 49/27 | 10 | 28/12/15/7 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `src/testRunner/unittests/tsbuild/watchMode.ts` | yes | 3 | 1 | 6 | 12 | 1 | 68/49 | 10 | 1/4/9/6 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `src/testRunner/unittests/tscWatch/helpers.ts` | no | 0 | — | 2 | 0 | 0 | 0/5 | 1 | 118/85/76/82 |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` | `pandas/core/series.py` | yes | 3 | 3 | 7 | 2 | 1 | 40/25 | 20 | 8/4/2/1 |
| `pandas-dev-pandas-10068` | `run-20260811T131236Z` | `pandas/core/series.py` | no | 3 | 1 | 7 | 1 | 0 | 11/25 | 15 | 4/2/14/9 |

## Counterfactual file rankings

| Case | Run | Policy | First Oracle rank | Recall@5 | Recall@10 |
|---|---|---|---:|---:|---:|
| `vuejs-vue-242` | `run-20260811T122541Z` | `hybrid` | 2 | 1.000 | 1.000 |
| `vuejs-vue-242` | `run-20260811T122541Z` | `corroboration` | 3 | 0.500 | 1.000 |
| `vuejs-vue-242` | `run-20260811T122541Z` | `responsibility` | 5 | 0.500 | 1.000 |
| `vuejs-vue-242` | `run-20260811T122541Z` | `chain` | 5 | 0.500 | 1.000 |
| `vuejs-vue-242` | `run-20260811T122658Z` | `hybrid` | 2 | 1.000 | 1.000 |
| `vuejs-vue-242` | `run-20260811T122658Z` | `corroboration` | 2 | 0.500 | 1.000 |
| `vuejs-vue-242` | `run-20260811T122658Z` | `responsibility` | 4 | 0.500 | 1.000 |
| `vuejs-vue-242` | `run-20260811T122658Z` | `chain` | 4 | 0.500 | 1.000 |
| `vuejs-vue-10803` | `run-20260811T130723Z` | `hybrid` | 16 | 0.000 | 0.000 |
| `vuejs-vue-10803` | `run-20260811T130723Z` | `corroboration` | 3 | 1.000 | 1.000 |
| `vuejs-vue-10803` | `run-20260811T130723Z` | `responsibility` | 3 | 1.000 | 1.000 |
| `vuejs-vue-10803` | `run-20260811T130723Z` | `chain` | 6 | 0.000 | 1.000 |
| `vuejs-vue-10803` | `run-20260811T130901Z` | `hybrid` | 1 | 1.000 | 1.000 |
| `vuejs-vue-10803` | `run-20260811T130901Z` | `corroboration` | 6 | 0.000 | 1.000 |
| `vuejs-vue-10803` | `run-20260811T130901Z` | `responsibility` | 5 | 1.000 | 1.000 |
| `vuejs-vue-10803` | `run-20260811T130901Z` | `chain` | 8 | 0.000 | 1.000 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `hybrid` | 3 | 0.250 | 0.250 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `corroboration` | 11 | 0.000 | 0.000 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `responsibility` | 7 | 0.000 | 0.250 |
| `microsoft-TypeScript-35468` | `run-20260811T125639Z` | `chain` | 23 | 0.000 | 0.000 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `hybrid` | 1 | 0.250 | 0.250 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `corroboration` | 4 | 0.250 | 0.500 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `responsibility` | 2 | 0.250 | 0.500 |
| `microsoft-TypeScript-35468` | `run-20260811T130428Z` | `chain` | 2 | 0.250 | 0.750 |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` | `hybrid` | 8 | 0.000 | 1.000 |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` | `corroboration` | 4 | 1.000 | 1.000 |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` | `responsibility` | 2 | 1.000 | 1.000 |
| `pandas-dev-pandas-10068` | `run-20260811T131029Z` | `chain` | 1 | 1.000 | 1.000 |
| `pandas-dev-pandas-10068` | `run-20260811T131236Z` | `hybrid` | 4 | 1.000 | 1.000 |
| `pandas-dev-pandas-10068` | `run-20260811T131236Z` | `corroboration` | 2 | 1.000 | 1.000 |
| `pandas-dev-pandas-10068` | `run-20260811T131236Z` | `responsibility` | 14 | 0.000 | 0.000 |
| `pandas-dev-pandas-10068` | `run-20260811T131236Z` | `chain` | 9 | 0.000 | 1.000 |

## Mean recall@10

| Policy | Mean recall@10 |
|---|---:|
| `chain` | 0.844 |
| `corroboration` | 0.812 |
| `responsibility` | 0.719 |
| `hybrid` | 0.688 |

## Conclusions

1. Intent selection is not the stable boundary assumed by retrieval. The selected `explain` contract and stage IDs can remain fixed while the second request-analysis LLM changes proposition text and evidence boundary. None of the paired initial Qdrant queries were byte-identical, and the TypeScript pair changed from four to six repository obligations because `explain_resulting_effect` and `explain_why` moved from `external` to `repository/local_to_external_handoff`.

2. Qdrant alone cannot explain final instability. In the bad Vue 10803 and pandas repeats, the Oracle file had hybrid rank 1 but was not selected. Conversely, the good Vue 10803 run had the Oracle file only at reconstructed hybrid rank 16, while semantic/graph corroboration brought it to rank 3.

3. Oracle files are unusually recurrent and structurally active in aggregate. They appear across more obligations, more semantic channels, and more productive incoming/outgoing edges, with higher query-to-symbol overlap. No one feature is a safe eligibility gate.

4. Penalizing graph fanout is not generally valid. Oracle files had higher mean cross-file fanout than non-Oracle files. Generic utilities can be high-fanout, but real orchestration and state-propagation owners can be high-fanout too.

5. The chain policy is useful for pool building, not as a replacement shortlist policy. It has the best mean recall@10 but still misses every TypeScript Oracle file in the first run's top ten and misses several owners at rank five.

6. A bounded survival invariant does separate the causal source owners from the point at which they are currently lost. The union of top-12 initial hybrid files classified as implementation retains every source-owner Oracle in all eight runs, with only 12-22 files per run. This is a file-pool guarantee, not evidence acceptance and not an Oracle-ranking claim.

## Recommended design order

### 1. Keep repository scope backend-owned

- Backend stage policy must own whether a stage receives repository retrieval. The stage-requirement LLM may describe an external boundary, but it should not suppress a repository-policy stage merely by emitting `external`.
- The measured deterministic base-query experiment was stable but did not recover owners, so it should not be treated as part of this candidate-survival proposal.

### 2. Build the measured bounded owner-survival pool

- Before connected-component ranking, union every implementation file in the top 12 hybrid results of any initial obligation and cap the request-level pool at 24 files.
- Allocate one exact executable representative per protected file across the request before allocating additional per-obligation nodes. The eight-run maximum was 22 files, so this does not require a larger candidate count than the current four-by-six final request.
- Keep dense, sparse, exact-anchor, and productive-graph provenance on those files as corroboration; do not let one winning component erase a directly retrieved protected file.

### 3. Select a joint responsibility chain after file survival

- Within the bounded file pool, assign exact nodes to trigger/producer, state-mutation owner, and consumer/effect roles.
- Treat productive graph adjacency in both directions. Newer TypeScript traces show builder functions as upstream callers of semantic seed nodes; the current provenance tier favors visible downstream `graph_direct_target` nodes and can demote those upstream owners to generic `graph_neighbor` candidates.
- Assess role assignments jointly with real CodeGraph edges and source snippets, rather than isolated lexical overlap, component size, edge direction, or fanout.
- Keep the prompt bounded by selecting exact ranges after file pooling instead of shrinking the file pool prematurely.

### 4. Evaluation gate

- Replay policies against saved traces first, using Oracle labels only for metrics.
- Require improvement on every repository pair, not only mean recall.
- Then run two unchanged real repetitions per main case and record scope drift, candidate-pool recall, shortlist recall, final selection, sufficiency, and retrieval tokens separately.
