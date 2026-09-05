# Graphless Retrieval — Four Repetitions per Case

This is a separate CodeGraph-ablation comparison, not part of the main Workspace/Codex aggregate.

Boundary audit: **140** runs used `structural_graph_enabled: false`; failures: **0**.

| System | Runs | P@5 | R@5 | NDCG@5 | Any Oracle | Full Oracle | Mean files | Mean flow tokens | Mean seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| graphless | 140 | 0.200 | 0.505 | 0.463 | 0.686 | 0.379 | 2.81 | 82177 | 268.9 |
| workspace | 140 | 0.191 | 0.508 | 0.401 | 0.679 | 0.407 | 2.96 | 95315 | 227.5 |
| codex_luna_efficient | 140 | 0.260 | 0.677 | 0.511 | 0.893 | 0.579 | 6.49 | 283913 | 121.7 |

## Per-case stability

| Case | System | R@5 | Oracle-hit runs | Full-recall runs | Mean files | Flow tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | graphless | 0.500 | 4/4 | 0/4 | 2.50 | 95172 |
| `microsoft-TypeScript-10020` | workspace | 0.500 | 4/4 | 0/4 | 3.00 | 108624 |
| `microsoft-TypeScript-10020` | codex_luna_efficient | 0.500 | 4/4 | 0/4 | 5.25 | 203872 |
| `microsoft-TypeScript-10041` | graphless | 0.750 | 3/4 | 3/4 | 1.50 | 59397 |
| `microsoft-TypeScript-10041` | workspace | 0.500 | 2/4 | 2/4 | 1.75 | 76983 |
| `microsoft-TypeScript-10041` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.00 | 849162 |
| `microsoft-TypeScript-10473` | graphless | 1.000 | 4/4 | 4/4 | 3.50 | 87216 |
| `microsoft-TypeScript-10473` | workspace | 1.000 | 4/4 | 4/4 | 3.00 | 110861 |
| `microsoft-TypeScript-10473` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.50 | 224604 |
| `microsoft-TypeScript-16278` | graphless | 0.594 | 4/4 | 0/4 | 5.00 | 96722 |
| `microsoft-TypeScript-16278` | workspace | 0.500 | 4/4 | 0/4 | 5.00 | 121339 |
| `microsoft-TypeScript-16278` | codex_luna_efficient | 0.625 | 4/4 | 0/4 | 6.25 | 200626 |
| `microsoft-TypeScript-19074` | graphless | 0.125 | 1/4 | 0/4 | 1.25 | 60534 |
| `microsoft-TypeScript-19074` | workspace | 0.125 | 1/4 | 0/4 | 1.25 | 75507 |
| `microsoft-TypeScript-19074` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 7.25 | 73227 |
| `microsoft-TypeScript-24625` | graphless | 1.000 | 4/4 | 4/4 | 2.00 | 76690 |
| `microsoft-TypeScript-24625` | workspace | 1.000 | 4/4 | 4/4 | 2.75 | 101704 |
| `microsoft-TypeScript-24625` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.75 | 175100 |
| `microsoft-TypeScript-2953` | graphless | 0.000 | 0/4 | 0/4 | 1.50 | 66906 |
| `microsoft-TypeScript-2953` | workspace | 0.000 | 0/4 | 0/4 | 1.25 | 63998 |
| `microsoft-TypeScript-2953` | codex_luna_efficient | 0.250 | 1/4 | 1/4 | 6.75 | 297974 |
| `microsoft-TypeScript-35468` | graphless | 0.625 | 4/4 | 0/4 | 5.50 | 108560 |
| `microsoft-TypeScript-35468` | workspace | 0.625 | 4/4 | 2/4 | 4.75 | 130336 |
| `microsoft-TypeScript-35468` | codex_luna_efficient | 0.500 | 4/4 | 0/4 | 6.50 | 968002 |
| `microsoft-TypeScript-45713` | graphless | 0.357 | 4/4 | 0/4 | 2.75 | 83090 |
| `microsoft-TypeScript-45713` | workspace | 0.214 | 4/4 | 0/4 | 2.50 | 108377 |
| `microsoft-TypeScript-45713` | codex_luna_efficient | 0.500 | 4/4 | 0/4 | 5.50 | 310299 |
| `microsoft-TypeScript-46770` | graphless | 0.750 | 3/4 | 3/4 | 5.25 | 96716 |
| `microsoft-TypeScript-46770` | workspace | 1.000 | 4/4 | 4/4 | 2.75 | 124925 |
| `microsoft-TypeScript-46770` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 5.25 | 646619 |
| `microsoft-TypeScript-52695` | graphless | 0.333 | 4/4 | 0/4 | 2.75 | 87417 |
| `microsoft-TypeScript-52695` | workspace | 0.333 | 4/4 | 0/4 | 3.00 | 127062 |
| `microsoft-TypeScript-52695` | codex_luna_efficient | 0.333 | 4/4 | 0/4 | 4.50 | 315889 |
| `pandas-dev-pandas-10068` | graphless | 0.250 | 1/4 | 1/4 | 1.75 | 71563 |
| `pandas-dev-pandas-10068` | workspace | 1.000 | 4/4 | 4/4 | 4.50 | 95499 |
| `pandas-dev-pandas-10068` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.00 | 278654 |
| `pandas-dev-pandas-10150` | graphless | 0.625 | 4/4 | 1/4 | 3.25 | 93077 |
| `pandas-dev-pandas-10150` | workspace | 0.875 | 4/4 | 3/4 | 3.75 | 95908 |
| `pandas-dev-pandas-10150` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.50 | 262136 |
| `pandas-dev-pandas-14942` | graphless | 0.208 | 4/4 | 0/4 | 3.75 | 130318 |
| `pandas-dev-pandas-14942` | workspace | 0.333 | 4/4 | 0/4 | 3.75 | 129212 |
| `pandas-dev-pandas-14942` | codex_luna_efficient | 0.375 | 4/4 | 0/4 | 6.00 | 487512 |
| `pandas-dev-pandas-16499` | graphless | 1.000 | 4/4 | 4/4 | 1.25 | 67748 |
| `pandas-dev-pandas-16499` | workspace | 1.000 | 4/4 | 4/4 | 1.00 | 88571 |
| `pandas-dev-pandas-16499` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 2.50 | 91718 |
| `pandas-dev-pandas-16764` | graphless | 0.044 | 3/4 | 0/4 | 2.00 | 81805 |
| `pandas-dev-pandas-16764` | workspace | 0.015 | 1/4 | 0/4 | 1.75 | 84468 |
| `pandas-dev-pandas-16764` | codex_luna_efficient | 0.044 | 4/4 | 0/4 | 18.50 | 287425 |
| `pandas-dev-pandas-22698` | graphless | 0.000 | 0/4 | 0/4 | 2.25 | 69336 |
| `pandas-dev-pandas-22698` | workspace | 0.000 | 0/4 | 0/4 | 2.75 | 97283 |
| `pandas-dev-pandas-22698` | codex_luna_efficient | 0.000 | 0/4 | 0/4 | 4.00 | 180673 |
| `pandas-dev-pandas-22872` | graphless | 0.000 | 0/4 | 0/4 | 3.50 | 100269 |
| `pandas-dev-pandas-22872` | workspace | 0.000 | 0/4 | 0/4 | 1.00 | 100792 |
| `pandas-dev-pandas-22872` | codex_luna_efficient | 0.000 | 0/4 | 0/4 | 8.00 | 136366 |
| `pandas-dev-pandas-25183` | graphless | 0.000 | 0/4 | 0/4 | 2.25 | 98820 |
| `pandas-dev-pandas-25183` | workspace | 0.000 | 0/4 | 0/4 | 2.25 | 125116 |
| `pandas-dev-pandas-25183` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.75 | 418598 |
| `pandas-dev-pandas-32289` | graphless | 0.000 | 0/4 | 0/4 | 1.75 | 56003 |
| `pandas-dev-pandas-32289` | workspace | 0.000 | 0/4 | 0/4 | 1.00 | 62958 |
| `pandas-dev-pandas-32289` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.50 | 254060 |
| `pandas-dev-pandas-35925` | graphless | 0.077 | 4/4 | 0/4 | 1.25 | 58069 |
| `pandas-dev-pandas-35925` | workspace | 0.077 | 4/4 | 0/4 | 1.00 | 42513 |
| `pandas-dev-pandas-35925` | codex_luna_efficient | 0.154 | 4/4 | 0/4 | 4.75 | 86356 |
| `pandas-dev-pandas-36617` | graphless | 1.000 | 4/4 | 4/4 | 1.75 | 73001 |
| `pandas-dev-pandas-36617` | workspace | 0.750 | 3/4 | 3/4 | 1.50 | 74026 |
| `pandas-dev-pandas-36617` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 13.75 | 307547 |
| `pandas-dev-pandas-4542` | graphless | 0.667 | 4/4 | 0/4 | 3.75 | 95099 |
| `pandas-dev-pandas-4542` | workspace | 0.667 | 4/4 | 0/4 | 2.75 | 103909 |
| `pandas-dev-pandas-4542` | codex_luna_efficient | 0.667 | 4/4 | 0/4 | 7.25 | 217524 |
| `vuejs-vue-10004` | graphless | 0.000 | 0/4 | 0/4 | 7.25 | 127342 |
| `vuejs-vue-10004` | workspace | 0.000 | 0/4 | 0/4 | 7.00 | 132152 |
| `vuejs-vue-10004` | codex_luna_efficient | 0.000 | 4/4 | 4/4 | 13.50 | 441284 |
| `vuejs-vue-10519` | graphless | 1.000 | 4/4 | 4/4 | 1.00 | 54695 |
| `vuejs-vue-10519` | workspace | 1.000 | 4/4 | 4/4 | 3.00 | 77737 |
| `vuejs-vue-10519` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 5.75 | 198564 |
| `vuejs-vue-10803` | graphless | 1.000 | 4/4 | 4/4 | 1.75 | 70612 |
| `vuejs-vue-10803` | workspace | 1.000 | 4/4 | 4/4 | 2.75 | 79862 |
| `vuejs-vue-10803` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 5.75 | 304026 |
| `vuejs-vue-11718` | graphless | 0.500 | 3/4 | 0/4 | 1.75 | 45531 |
| `vuejs-vue-11718` | workspace | 0.500 | 3/4 | 0/4 | 2.25 | 58299 |
| `vuejs-vue-11718` | codex_luna_efficient | 0.667 | 4/4 | 0/4 | 5.00 | 138336 |
| `vuejs-vue-11782` | graphless | 0.500 | 2/4 | 2/4 | 4.25 | 71042 |
| `vuejs-vue-11782` | workspace | 0.250 | 1/4 | 1/4 | 3.25 | 71765 |
| `vuejs-vue-11782` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 7.25 | 145754 |
| `vuejs-vue-13052` | graphless | 0.000 | 0/4 | 0/4 | 1.25 | 55350 |
| `vuejs-vue-13052` | workspace | 0.000 | 0/4 | 0/4 | 1.25 | 65717 |
| `vuejs-vue-13052` | codex_luna_efficient | 0.000 | 0/4 | 0/4 | 2.25 | 78695 |
| `vuejs-vue-5884` | graphless | 1.000 | 4/4 | 4/4 | 3.00 | 74416 |
| `vuejs-vue-5884` | workspace | 0.750 | 4/4 | 4/4 | 4.75 | 99086 |
| `vuejs-vue-5884` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.75 | 216048 |
| `vuejs-vue-6097` | graphless | 1.000 | 4/4 | 4/4 | 3.00 | 77232 |
| `vuejs-vue-6097` | workspace | 0.750 | 4/4 | 2/4 | 4.75 | 100008 |
| `vuejs-vue-6097` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.50 | 118720 |
| `vuejs-vue-6301` | graphless | 0.023 | 1/4 | 0/4 | 2.00 | 83058 |
| `vuejs-vue-6301` | workspace | 0.000 | 0/4 | 0/4 | 3.75 | 81375 |
| `vuejs-vue-6301` | codex_luna_efficient | 0.068 | 4/4 | 0/4 | 8.50 | 139554 |
| `vuejs-vue-8528` | graphless | 1.000 | 4/4 | 4/4 | 1.00 | 51414 |
| `vuejs-vue-8528` | workspace | 1.000 | 4/4 | 4/4 | 2.00 | 65312 |
| `vuejs-vue-8528` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 2.25 | 81530 |
| `vuejs-vue-9042` | graphless | 0.750 | 3/4 | 3/4 | 4.25 | 118649 |
| `vuejs-vue-9042` | workspace | 1.000 | 4/4 | 4/4 | 5.50 | 134786 |
| `vuejs-vue-9042` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 9.50 | 418258 |
| `vuejs-vue-9842` | graphless | 1.000 | 4/4 | 4/4 | 6.00 | 133331 |
| `vuejs-vue-9842` | workspace | 1.000 | 4/4 | 4/4 | 5.50 | 119941 |
| `vuejs-vue-9842` | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 7.25 | 382230 |
