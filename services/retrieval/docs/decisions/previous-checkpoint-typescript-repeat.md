# TypeScript repeat at 3a4a705 — 2026-09-15

User explicitly requested the checkpoint preceding the Flow-aware callable integrity
repair, tested in the original working directory rather than a separate worktree.

## Preservation and checkout

- Current thesis committed as `543209f` on `codex/aug29-trace-repair-repeat` (77 files).
- Other tracked and untracked changes preserved in stash
  `2b98e810e2aa43c41eaa8063d939dba44fa19e11`, named
  `Preserve post-803f5e2 experiments before 3a4a705 TypeScript reruns`.
- Original directory switched to detached `3a4a705`; runtime remained unmodified.
- The separate worktree created before the user's clarification was not used for runs.
- Ignored dependencies, configuration, credentials and external run artifacts remain
  local; they were not committed or removed.

## Execution

Two fresh executions of:

```text
npm run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/microsoft-TypeScript-35468/issue.json --skip-response-generation --exclude-path openwiki
```

Node 22, gpt-5.6-luna, existing workspace profile, final selection enabled. No replay
environment variable. Existing complete 83408-point Qdrant index reused. No scope,
model, prompt or runtime edits for the reruns. Both processes exited successfully.

| Run | Focal oracle files | Retrieval tokens | Coverage / sufficient |
| --- | --- | ---: | --- |
| run-20260915T030801Z | 4/4 | 107264 | partial / false |
| run-20260915T030811Z | 2/4 | 109469 | partial / false |

First run retains builder.ts, builderState.ts, tsbuild/watchMode.ts and
tscWatch/helpers.ts. Second final selection retains builder.ts and watchMode.ts;
BuilderState and Helpers are absent from final evidence. This is a final-set
observation, not a diagnosis that those files were absent from raw retrieval.

Total retrieval tokens: 216733; mean 108366.5. Provider usage is summed once from
llm_response_received events; request analysis, embeddings and explanation are excluded.

The immediately prior 803f5e2 pair (022328Z/022339Z) produced 4/4 and 3/4 using
102293/103095 tokens. These two-run samples establish that neither checkpoint
consistently retained all four focal files; they do not establish why the sets differ
or a causal effect of the Flow repair. Full behavioral sufficiency remains false.

Artifacts: `C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/<run>/`.
At completion of that comparison, checkout was left at 3a4a705. The following
user-requested restoration supersedes that working-directory state.

## Restoration and two further actual runs

Returned to `codex/aug29-trace-repair-repeat` at `543209f` (803f5e2 runtime plus
the thesis commit), then applied stash `2b98e810e2aa43c41eaa8063d939dba44fa19e11`.
The stash is retained as a backup. Thesis and all saved experimental artifacts are
visible again. This older-checkpoint report was preserved across the switch.
Runtime/config/package diffs against 803f5e2 show only documentation changes;
the rejected runtime experiments remain disabled/reverted.

Two fresh TypeScript executions used the identical command above and reused the
same complete 83408-point index. Final evidence selection remained enabled.

| Run | Focal oracle files | Retrieval tokens | Coverage / sufficient |
| --- | --- | ---: | --- |
| run-20260915T035850Z | 4/4 | 109089 | partial / false |
| run-20260915T035900Z | 4/4 | 110848 | partial / false |

Both final sets retain Builder, BuilderState, WatchMode and Helpers. Total 219937
retrieval tokens, mean 109968.5 (1.48% above the preceding older-checkpoint pair).
Both commands exited zero. These are actual fresh runs, not replays. File-level
4/4 does not establish complete behavioral evidence; sufficient remains false.
Across the two recent 803f5e2 pairs, scores are 4/4, 3/4, 4/4, 4/4. The older
3a4a705 intervening pair was 4/4, 2/4. This ordering alone does not isolate the
cause of differences; no additional runtime repair was introduced for this repeat.
