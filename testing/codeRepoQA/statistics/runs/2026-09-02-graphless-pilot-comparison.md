# Graphless Retrieval Pilot — Four Repetitions per Case

This is a separate CodeGraph-ablation pilot, not part of the main Workspace/Codex aggregate.

Boundary audit: **16** runs used `structural_graph_enabled: false`; failures: **0**.

| System | Runs | P@5 | R@5 | NDCG@5 | Any Oracle | Full Oracle | Mean files | Mean flow tokens | Mean seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| graphless | 16 | 0.200 | 0.474 | 0.469 | 0.625 | 0.312 | 2.75 | 83448 | 183.0 |
| workspace | 16 | 0.225 | 0.656 | 0.510 | 0.750 | 0.625 | 3.94 | 96768 | 221.8 |
| codex_luna_efficient | 16 | 0.238 | 0.642 | 0.384 | 1.000 | 0.500 | 6.69 | 422559 | 124.2 |

## Per-case stability

| Case | System | R@5 | Oracle-hit runs | Full-recall runs | Mean files | Flow tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-35468` | graphless | 0.625 | 4/4 | 0/4 | 5.50 | 108560 |
| `microsoft-TypeScript-35468` | workspace | 0.625 | 4/4 | 2/4 | 4.75 | 130336 |
| `microsoft-TypeScript-35468` | codex_luna_efficient | 0.500 | 4/4 | 0/4 | 6.50 | 968002 |
| `pandas-dev-pandas-10068` | graphless | 0.250 | 1/4 | 1/4 | 1.75 | 71563 |
| `pandas-dev-pandas-10068` | workspace | 1.000 | 4/4 | 4/4 | 4.50 | 95499 |
| `pandas-dev-pandas-10068` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.00 | 278654 |
| `vuejs-vue-10803` | graphless | 1.000 | 4/4 | 4/4 | 1.75 | 70612 |
| `vuejs-vue-10803` | workspace | 1.000 | 4/4 | 4/4 | 2.75 | 79862 |
| `vuejs-vue-10803` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 5.75 | 304026 |
| `vuejs-vue-6301` | graphless | 0.023 | 1/4 | 0/4 | 2.00 | 83058 |
| `vuejs-vue-6301` | workspace | 0.000 | 0/4 | 0/4 | 3.75 | 81375 |
| `vuejs-vue-6301` | codex_luna_efficient | 0.068 | 4/4 | 0/4 | 8.50 | 139554 |
