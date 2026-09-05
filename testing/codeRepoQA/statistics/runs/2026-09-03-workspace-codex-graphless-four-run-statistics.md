# Workspace, Codex, and Graphless Retrieval — Four Repetitions per Case

This consolidated comparison keeps the graphless ablation explicit while presenting all three systems together.

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
|  | workspace | 0.500 | 4/4 | 0/4 | 3.00 | 108624 |
|  | codex_luna_efficient | 0.500 | 4/4 | 0/4 | 5.25 | 203872 |
| `microsoft-TypeScript-10041` | graphless | 0.750 | 3/4 | 3/4 | 1.50 | 59397 |
|  | workspace | 0.500 | 2/4 | 2/4 | 1.75 | 76983 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.00 | 849162 |
| `microsoft-TypeScript-10473` | graphless | 1.000 | 4/4 | 4/4 | 3.50 | 87216 |
|  | workspace | 1.000 | 4/4 | 4/4 | 3.00 | 110861 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.50 | 224604 |
| `microsoft-TypeScript-16278` | graphless | 0.594 | 4/4 | 0/4 | 5.00 | 96722 |
|  | workspace | 0.500 | 4/4 | 0/4 | 5.00 | 121339 |
|  | codex_luna_efficient | 0.625 | 4/4 | 0/4 | 6.25 | 200626 |
| `microsoft-TypeScript-19074` | graphless | 0.125 | 1/4 | 0/4 | 1.25 | 60534 |
|  | workspace | 0.125 | 1/4 | 0/4 | 1.25 | 75507 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 7.25 | 73227 |
| `microsoft-TypeScript-24625` | graphless | 1.000 | 4/4 | 4/4 | 2.00 | 76690 |
|  | workspace | 1.000 | 4/4 | 4/4 | 2.75 | 101704 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.75 | 175100 |
| `microsoft-TypeScript-2953` | graphless | 0.000 | 0/4 | 0/4 | 1.50 | 66906 |
|  | workspace | 0.000 | 0/4 | 0/4 | 1.25 | 63998 |
|  | codex_luna_efficient | 0.250 | 1/4 | 1/4 | 6.75 | 297974 |
| `microsoft-TypeScript-35468` | graphless | 0.625 | 4/4 | 0/4 | 5.50 | 108560 |
|  | workspace | 0.625 | 4/4 | 2/4 | 4.75 | 130336 |
|  | codex_luna_efficient | 0.500 | 4/4 | 0/4 | 6.50 | 968002 |
| `microsoft-TypeScript-45713` | graphless | 0.357 | 4/4 | 0/4 | 2.75 | 83090 |
|  | workspace | 0.214 | 4/4 | 0/4 | 2.50 | 108377 |
|  | codex_luna_efficient | 0.500 | 4/4 | 0/4 | 5.50 | 310299 |
| `microsoft-TypeScript-46770` | graphless | 0.750 | 3/4 | 3/4 | 5.25 | 96716 |
|  | workspace | 1.000 | 4/4 | 4/4 | 2.75 | 124925 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 5.25 | 646619 |
| `microsoft-TypeScript-52695` | graphless | 0.333 | 4/4 | 0/4 | 2.75 | 87417 |
|  | workspace | 0.333 | 4/4 | 0/4 | 3.00 | 127062 |
|  | codex_luna_efficient | 0.333 | 4/4 | 0/4 | 4.50 | 315889 |
| `pandas-dev-pandas-10068` | graphless | 0.250 | 1/4 | 1/4 | 1.75 | 71563 |
|  | workspace | 1.000 | 4/4 | 4/4 | 4.50 | 95499 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.00 | 278654 |
| `pandas-dev-pandas-10150` | graphless | 0.625 | 4/4 | 1/4 | 3.25 | 93077 |
|  | workspace | 0.875 | 4/4 | 3/4 | 3.75 | 95908 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.50 | 262136 |
| `pandas-dev-pandas-14942` | graphless | 0.208 | 4/4 | 0/4 | 3.75 | 130318 |
|  | workspace | 0.333 | 4/4 | 0/4 | 3.75 | 129212 |
|  | codex_luna_efficient | 0.375 | 4/4 | 0/4 | 6.00 | 487512 |
| `pandas-dev-pandas-16499` | graphless | 1.000 | 4/4 | 4/4 | 1.25 | 67748 |
|  | workspace | 1.000 | 4/4 | 4/4 | 1.00 | 88571 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 2.50 | 91718 |
| `pandas-dev-pandas-16764` | graphless | 0.044 | 3/4 | 0/4 | 2.00 | 81805 |
|  | workspace | 0.015 | 1/4 | 0/4 | 1.75 | 84468 |
|  | codex_luna_efficient | 0.044 | 4/4 | 0/4 | 18.50 | 287425 |
| `pandas-dev-pandas-22698` | graphless | 0.000 | 0/4 | 0/4 | 2.25 | 69336 |
|  | workspace | 0.000 | 0/4 | 0/4 | 2.75 | 97283 |
|  | codex_luna_efficient | 0.000 | 0/4 | 0/4 | 4.00 | 180673 |
| `pandas-dev-pandas-22872` | graphless | 0.000 | 0/4 | 0/4 | 3.50 | 100269 |
|  | workspace | 0.000 | 0/4 | 0/4 | 1.00 | 100792 |
|  | codex_luna_efficient | 0.000 | 0/4 | 0/4 | 8.00 | 136366 |
| `pandas-dev-pandas-25183` | graphless | 0.000 | 0/4 | 0/4 | 2.25 | 98820 |
|  | workspace | 0.000 | 0/4 | 0/4 | 2.25 | 125116 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.75 | 418598 |
| `pandas-dev-pandas-32289` | graphless | 0.000 | 0/4 | 0/4 | 1.75 | 56003 |
|  | workspace | 0.000 | 0/4 | 0/4 | 1.00 | 62958 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 4.50 | 254060 |
| `pandas-dev-pandas-35925` | graphless | 0.077 | 4/4 | 0/4 | 1.25 | 58069 |
|  | workspace | 0.077 | 4/4 | 0/4 | 1.00 | 42513 |
|  | codex_luna_efficient | 0.154 | 4/4 | 0/4 | 4.75 | 86356 |
| `pandas-dev-pandas-36617` | graphless | 1.000 | 4/4 | 4/4 | 1.75 | 73001 |
|  | workspace | 0.750 | 3/4 | 3/4 | 1.50 | 74026 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 13.75 | 307547 |
| `pandas-dev-pandas-4542` | graphless | 0.667 | 4/4 | 0/4 | 3.75 | 95099 |
|  | workspace | 0.667 | 4/4 | 0/4 | 2.75 | 103909 |
|  | codex_luna_efficient | 0.667 | 4/4 | 0/4 | 7.25 | 217524 |
| `vuejs-vue-10004` | graphless | 0.000 | 0/4 | 0/4 | 7.25 | 127342 |
|  | workspace | 0.000 | 0/4 | 0/4 | 7.00 | 132152 |
|  | codex_luna_efficient | 0.000 | 4/4 | 4/4 | 13.50 | 441284 |
| `vuejs-vue-10519` | graphless | 1.000 | 4/4 | 4/4 | 1.00 | 54695 |
|  | workspace | 1.000 | 4/4 | 4/4 | 3.00 | 77737 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 5.75 | 198564 |
| `vuejs-vue-10803` | graphless | 1.000 | 4/4 | 4/4 | 1.75 | 70612 |
|  | workspace | 1.000 | 4/4 | 4/4 | 2.75 | 79862 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 5.75 | 304026 |
| `vuejs-vue-11718` | graphless | 0.500 | 3/4 | 0/4 | 1.75 | 45531 |
|  | workspace | 0.500 | 3/4 | 0/4 | 2.25 | 58299 |
|  | codex_luna_efficient | 0.667 | 4/4 | 0/4 | 5.00 | 138336 |
| `vuejs-vue-11782` | graphless | 0.500 | 2/4 | 2/4 | 4.25 | 71042 |
|  | workspace | 0.250 | 1/4 | 1/4 | 3.25 | 71765 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 7.25 | 145754 |
| `vuejs-vue-13052` | graphless | 0.000 | 0/4 | 0/4 | 1.25 | 55350 |
|  | workspace | 0.000 | 0/4 | 0/4 | 1.25 | 65717 |
|  | codex_luna_efficient | 0.000 | 0/4 | 0/4 | 2.25 | 78695 |
| `vuejs-vue-5884` | graphless | 1.000 | 4/4 | 4/4 | 3.00 | 74416 |
|  | workspace | 0.750 | 4/4 | 4/4 | 4.75 | 99086 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.75 | 216048 |
| `vuejs-vue-6097` | graphless | 1.000 | 4/4 | 4/4 | 3.00 | 77232 |
|  | workspace | 0.750 | 4/4 | 2/4 | 4.75 | 100008 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 6.50 | 118720 |
| `vuejs-vue-6301` | graphless | 0.023 | 1/4 | 0/4 | 2.00 | 83058 |
|  | workspace | 0.000 | 0/4 | 0/4 | 3.75 | 81375 |
|  | codex_luna_efficient | 0.068 | 4/4 | 0/4 | 8.50 | 139554 |
| `vuejs-vue-8528` | graphless | 1.000 | 4/4 | 4/4 | 1.00 | 51414 |
|  | workspace | 1.000 | 4/4 | 4/4 | 2.00 | 65312 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 2.25 | 81530 |
| `vuejs-vue-9042` | graphless | 0.750 | 3/4 | 3/4 | 4.25 | 118649 |
|  | workspace | 1.000 | 4/4 | 4/4 | 5.50 | 134786 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 9.50 | 418258 |
| `vuejs-vue-9842` | graphless | 1.000 | 4/4 | 4/4 | 6.00 | 133331 |
|  | workspace | 1.000 | 4/4 | 4/4 | 5.50 | 119941 |
|  | codex_luna_efficient | 1.000 | 4/4 | 4/4 | 7.25 | 382230 |
