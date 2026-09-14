# August 29 historical runtime repeat

## Preservation and configuration

User requested checkout of the historical mixed-island repair and three actual TypeScript
35468 runs. Original branch: `codex/snippet-first-admission`, HEAD `df75bfc`.
Tracked and untracked work was preserved with `git stash push --include-untracked`:
`a43a0c281b48e8dbdded2b9bb014875d5256593c`, message
`preserve current runtime and OpenWiki experiments before August29 checkout 2026-09-14`.
Existing older stashes were not dropped. Ignored local dependencies/configuration remain in place.

Checkout: branch `codex/aug29-trace-repair-repeat`, commit
`0e725b498b26c364c0cc730f33875c495751b48f` (`after selection islands`).
No retrieval source changes were made. This document is a new experiment record only.

Actual command, with Node 22.22.0 prepended to the process PATH:

```text
npm run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/microsoft-TypeScript-35468/issue.json --skip-response-generation --exclude-path openwiki
```

The extra exclusion prevents the subsequently generated wiki from entering historical code search.
The historical harness does not provide the later repository-local OpenWiki connection.
Final evidence selection is enabled; response generation is skipped.
The existing local API configuration supplies the retrieval model (not the profile's unused
Codex-mode model field). Run metadata is authoritative for the effective settings.

The first run required a historical-format BM25/Qdrant refresh (83,408 documents).
The user was notified before synchronization; later runs wait for completion before starting.

## Results

All three actual processes completed with exit code zero. Effective retrieval model:
`gpt-5.6-luna`. Final selection enabled and response generation skipped throughout.

| Run | Focal oracle overlap | Final focal matches | Coverage / sufficient | Retrieval tokens |
| --- | --- | --- | --- | --- |
| `run-20260914T210202Z` | 3/4 | BuilderState, WatchMode, Helpers | partial / false | 109,463 |
| `run-20260914T211656Z` | 3/4 | Builder, WatchMode, Helpers | partial / false | 109,699 |
| `run-20260914T211707Z` | 3/4 | Builder, BuilderState, WatchMode | partial / false | 113,928 |

Helpers in the first two runs is a file trace, not a direct internal-behavior snippet.
The third run's WatchMode source is only L600-L602; file overlap alone is not proof of
equivalent explanatory coverage. These are final-output comparisons, not diagnoses of
raw retrieval absence or the stage at which other owners were lost.

Total: 333,090 retrieval tokens; mean: 111,030. Usage sums provider-reported total tokens
from `llm_response_received` records. Compared with the preceding current-runtime
three-run batch (1/4, 2/4, 3/4; mean 135,645.3 tokens), these repeats have higher mean
focal file overlap and approximately 18.1% lower mean retrieval usage. This is a comparison
of entire runtime versions, not a controlled attribution to any single repair.
The historical 4/4 pair was not reproduced; all three now reach 3/4 with different gaps.

The first run rebuilt BM25 and the Qdrant collection using the historical format/signature;
the other two reused it. All used 83,408 indexed documents. No document-embedding API
batches were sent: the vector upload reused the embedding cache. CodeGraph performed
its normal synchronization. The later generated wiki was excluded, while the historical
local-notes connector remained at its ordinary historical default. No connected-source
failures were reported.

Secondary verification: 114 focused historical tests passed (file traces, initial owner
comparison, final orchestration, and action policies). No retrieval source edits were
made to obtain these results. The checkout remains on the historical branch; the only
new working-tree file is this report. The prior current-runtime stash remains intact.

## Returning to the saved current version

Preserve this report first, then switch to `codex/snippet-first-admission` and apply
stash `a43a0c281b48e8dbdded2b9bb014875d5256593c`. Prefer `apply`, not `pop`, to keep
the recovery copy. Do not apply the older OpenWiki stash on top: the new stash already
contains the current restored experiments. Switching source versions may require index
compatibility synchronization again; the stash is not an index backup.
