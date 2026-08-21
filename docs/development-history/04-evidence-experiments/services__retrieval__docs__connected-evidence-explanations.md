# Connected Evidence Explanation Selection

## Replaced design

This change removes the request-level 24-file promotion pool, inherited file
scores, per-root reserved final positions, one-representative-per-file
allocation, and component filler from final evidence consolidation. Those
mechanisms improved Oracle survival but treated a prompt budget as a relevance
boundary and could redirect a file away from the obligation searches that
originally found it.

## Stage boundary

The rewrite begins after initial per-obligation semantic retrieval:

1. Every initial result is grounded and retained for the obligation whose query
   returned it. The lexical overlap gate no longer discards a valid top-12
   Qdrant result.
2. The four strongest recurrent or exceptional semantic files remain discovery
   roots only. CodeGraph queries their file neighborhoods separately and takes
   the top two productive neighbor hints per root for exact localization.
3. Each neighbor is localized once using the descriptions of every obligation
   that retrieved its originating root. The exact candidate is attached to all
   of those obligations as inherited provenance. No combined all-obligation
   query chooses a new owning obligation.
4. Exact candidates are globally deduplicated by CodeGraph node or grounded
   range. Direct and inherited obligation support remain separate immutable
   relationships.
5. Directed productive CodeGraph edges and discovery-path edges connect exact
   candidates into an evidence graph. A root's score is not transferred into a
   neighbor's node score.
6. Greedy bounded connected explanations are generated from strong exact
   candidates. Explanations are scored by obligation coverage, direct support,
   verified internal edges, node specificity, and a generic-degree penalty.
7. Up to six diverse explanations are selected under a 16,000-character
   snippet budget. Shared candidates are deduplicated across explanations.
   There is no fixed file or candidate count.
8. The final LLM receives obligations, one global candidate table, directed
   connections, and the selected explanation subgraphs. It may accept a
   candidate for an obligation only when immutable direct or inherited support
   includes that obligation.

## Expected quality impact

- Candidate placement cannot be redirected by later lexical comparison.
- Graph connectivity raises the value of a connected explanation rather than
  artificially raising a neighbor's independent relevance.
- Multiple exact nodes from one file may survive when they support different
  mechanisms; there is no one-representative-per-file collapse.
- The final LLM sees proposed handoffs explicitly instead of reconstructing a
  causal path from a flat candidate list.

## Expected token and runtime impact

The final evidence input is controlled by a 16,000-character unique-snippet
budget rather than 24 candidates. Metadata adds some prompt cost, while snippet
deduplication across explanations reduces repeated text. No LLM stage is added.

Discovery uses four CodeGraph file-neighbor calls, up to four root-specific
restricted Qdrant localization calls, and one shared CodeGraph range-resolution
call. This can cost more retrieval latency than the former single grouped
localization but preserves obligation provenance.

## Regression risks

- File-level neighbors remain coarse discovery hints; the restricted semantic
  localization can still choose an irrelevant exact node within the file.
- Greedy explanation growth is deterministic but not globally optimal.
- A high-degree utility can still enter an explanation, though generic degree is
  penalized and its score is not inherited from another node.
- The character budget approximates tokens; actual LLM usage must be measured.
- Generated obligation wording can change initial candidates and therefore the
  evidence graph between runs.

## Comparison method and retention rule

Run the difficult CodeRepoQA cases through the actual workspace pipeline. Record
selected explanation count, candidate count, Oracle presence in the structured
final request, final Oracle overlap, `coverage_status`, `sufficient`, total
retrieval LLM tokens, and index reuse.

Per explicit user instruction, retain this rewrite even when individual runs do
not improve quality. Failures are follow-up evidence for graph construction or
final assessment, not grounds for restoring the 24-file allocator.

## Measured results

All runs used the real workspace pipeline. The TypeScript runs additionally
excluded `lib` and `tests/cases` as required by the established benchmark scope.

| Case and run | Explanations | Unique candidates | Oracle files in structured request | Final overlap | Coverage / sufficient | Retrieval tokens | Qdrant rebuilt |
|---|---:|---:|---|---:|---|---:|---|
| TypeScript `run-20260811T202723Z` | 3 | 14 | `watchMode.ts` | 1 | `partial / false` | 19,317 | false |
| TypeScript `run-20260811T203005Z` | 5 | 21 | none | 0 | `partial / false` | 24,053 | false |
| Vue 242 `run-20260811T203316Z` | 6 | 26 | `src/exp-parser.js` | 0 | `partial / false` | 24,333 | false |
| Vue 10803 `run-20260811T203434Z` | 5 | 25 | `dom-props.js`, `ssr-string.spec.js` | 1 | `partial / false` | 25,907 | false |
| pandas 10068 `run-20260811T203626Z` | 5 | 15 | none | 0 | `partial / false` | 18,753 | false |

The rewrite successfully removed obligation redirection and the fixed 24-file
cutoff. It also demonstrated that exact Oracle candidates can reach structured
assessment without being accepted (`exp-parser.js`), separating explanation
selection from final LLM judgment. Quality remains unstable: causal explanation
ranking omitted all measured Oracles in the second TypeScript run and pandas
run. The retained next problem is therefore better causal subgraph ranking and
assessment, not restoration of file-level protection.
