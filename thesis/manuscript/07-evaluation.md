# Evaluation

This chapter reports the frozen evaluation described in Chapter 4. The campaign comprised 35 CodeRepoQA-derived cases, five retrieval conditions, and four valid repetitions of every case-condition pair, giving 700 accepted runs. All conditions used `gpt-5.6-luna`, received the same issue and pre-resolution repository, skipped response generation, and retained final evidence selection. The results are first reported at file level, followed by comparisons among the four Workspace configurations and between Full Workspace and Codex. Cost, stability, and selected cases are then examined separately.

## Overall Retrieval Performance

Table 7.1 presents the principal ranking results across all 35 cases. Codex produced the strongest aggregate results: its R@5 was 0.677, compared with 0.508 for Full Workspace, and its NDCG@5 was 0.511, compared with 0.401. Among the native conditions, Workspace without CodeGraph placed an implementation Oracle first most often, reaching P@1 of 0.493. Full Workspace and the two controller-disabled conditions reached 0.329, 0.321, and 0.464 respectively. This early-rank difference did not extend to recall at five files: Full Workspace and Workspace without CodeGraph obtained nearly identical R@5 values of 0.508 and 0.505.

| Condition | P@1 | P@5 | R@5 | R@10 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 0.329 | 0.191 | 0.508 | 0.517 | 0.401 | 0.373 |
| Codex | 0.386 | 0.260 | 0.677 | 0.709 | 0.511 | 0.502 |
| Without CodeGraph | 0.493 | 0.200 | 0.505 | 0.508 | 0.463 | 0.427 |
| Without adaptive controller | 0.321 | 0.186 | 0.465 | 0.473 | 0.389 | 0.360 |
| Without either capability | 0.464 | 0.186 | 0.479 | 0.481 | 0.433 | 0.401 |

The development and held-out partitions followed the same broad ordering. The seven held-out cases provide an independent check across all issue categories, although their smaller number makes the exact aggregate values more sensitive to individual cases. Codex had the highest R@5 and NDCG@5 in both partitions. R@5 was higher on the held-out set for all four native conditions, including the combined ablation, whose value rose from 0.398 to 0.804. This does not indicate that held-out cases were generally easier; it reflects the particular seven selected cases. Its useful role is to show that the principal aggregate patterns were not confined to cases used during formative development.

| Partition | Condition | P@5 | R@5 | NDCG@5 | Any implementation hit | Full implementation recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development | Full Workspace | 0.188 | 0.474 | 0.392 | 0.670 | 0.366 |
|  | Codex | 0.246 | 0.596 | 0.464 | 0.866 | 0.473 |
|  | Without CodeGraph | 0.195 | 0.453 | 0.439 | 0.661 | 0.312 |
|  | Without adaptive controller | 0.184 | 0.434 | 0.391 | 0.616 | 0.295 |
|  | Without either capability | 0.173 | 0.398 | 0.385 | 0.607 | 0.268 |
| Held-out | Full Workspace | 0.207 | 0.643 | 0.437 | 0.714 | 0.571 |
|  | Codex | 0.314 | 1.000 | 0.700 | 1.000 | 1.000 |
|  | Without CodeGraph | 0.221 | 0.714 | 0.560 | 0.786 | 0.643 |
|  | Without adaptive controller | 0.193 | 0.589 | 0.382 | 0.679 | 0.571 |
|  | Without either capability | 0.236 | 0.804 | 0.626 | 0.857 | 0.750 |

Repository and issue-category results varied considerably. Codex had the highest R@5 in TypeScript, pandas, and Vue. The native differences were less uniform: removing CodeGraph slightly increased R@5 for TypeScript and Vue but reduced it for pandas, while controller removal reduced aggregate native recall but not every category. These small groups are therefore used to locate heterogeneous behaviour, not to rank repositories or claim that a component is uniformly beneficial for a particular language.

## Contributions of CodeGraph and Adaptive Exploration

The four native conditions form the two-factor comparison defined in Chapter 4. Table 7.3 reports each capability's observed difference while the other capability is either present or absent. A positive value means that enabling the named capability increased the measure.

| Capability contrast | P@1 | R@5 | NDCG@5 | Any hit | Full recall | Mean flow-token difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adaptive controller, with CodeGraph | +0.007 | +0.042 | +0.012 | +0.050 | +0.057 | +47,749 |
| Adaptive controller, without CodeGraph | +0.029 | +0.026 | +0.030 | +0.029 | +0.014 | +36,002 |
| CodeGraph, with adaptive controller | -0.164 | +0.002 | -0.062 | -0.007 | +0.029 | +13,137 |
| CodeGraph, without adaptive controller | -0.143 | -0.014 | -0.044 | -0.029 | -0.014 | +1,390 |

Adaptive exploration produced modest positive aggregate differences under both structural settings. With CodeGraph enabled, it increased R@5 from 0.465 to 0.508 and full implementation recall from 0.350 to 0.407. Without CodeGraph, the corresponding increases were smaller: R@5 rose from 0.479 to 0.505 and full recall from 0.364 to 0.379. The direction is consistent with the controller recovering some relevant evidence after round zero, but the scale is limited relative to its additional model use. It also did not transform the native sufficiency outcome discussed below.

CodeGraph showed a different pattern. With the controller enabled, it changed R@5 by only +0.002 and full recall by +0.029, while P@1 fell by 0.164 and NDCG@5 by 0.062. Without adaptive exploration, enabling CodeGraph reduced all four reported quality measures. The early-rank difference therefore cannot be attributed only to graph-driven controller expansion: it remains when both conditions stop after round zero. At the same time, Full Workspace recovered all implementation Oracles slightly more often than the graphless condition, and individual positive cases were present. For pandas 10068, for example, Full Workspace achieved full recall in four of four repetitions, compared with one of four without CodeGraph. The results show that structural processing can recover useful evidence in individual cases, but can also introduce or prioritise additional structural candidates that reduce early file-ranking quality. Its contribution was therefore beneficial in some cases without producing a consistent aggregate improvement.

The interaction between the capabilities was small and measure-dependent. Adaptive exploration improved R@5 more with CodeGraph than without it, whereas it improved NDCG@5 more in the graphless pipeline. CodeGraph's slight full-recall benefit appeared only when the controller was active. These descriptive differences suggest that the controller sometimes used structural evidence productively, but they do not show a general dependency between the components.

## Evidence Survival and Mechanism Completeness

File ranking describes whether known fixing files reached the returned evidence, but it does not establish whether the selected source explains the requested mechanism. The final selector labelled 135 Full Workspace runs `partial`, four `missing`, and one `strong`; only one of the 140 runs was marked sufficient. Every run in each native ablation was labelled partial and insufficient. Codex labelled all 140 runs strong and sufficient. As established in Chapter 4, these are the systems' own judgements rather than independent completeness labels. The contrast therefore shows a substantial difference in output policy or confidence, but it cannot by itself establish that all Codex mechanisms were complete or that almost every native result was objectively incomplete.

The Full Workspace controller usually exhausted its ordinary exploration allowance. It stopped after the normal three-round budget in 113 runs and reached the conditional round limit in another 16. Nine runs stopped after a round produced no evidence gain, one stopped because every required obligation was covered, and one because no executable action remained. Across 423 executed rounds, evidence and navigation gains were each recorded in 347 rounds, while coverage improved in 137. Later exploration was therefore frequently productive at the candidate level, but new candidates translated into only modest aggregate recall gains and almost no sufficient outcomes.

Saved traces also show that an evidence identity can survive while the source visible to a later LLM becomes less complete. Across 563 recorded coverage calls, 239 required source truncation. There were 1,461 instances in which a candidate's visible source became shorter than in an earlier round; in 164 of the 195 affected calls, the previous views would collectively have fitted within the existing total character budget. This diagnostic does not change the campaign metrics, but it identifies a pipeline boundary that file-level recall cannot reveal: preserving a candidate ID is not equivalent to preserving all source needed to assess its contribution.

The available campaign did not include an independent owner-level or causal-transition Oracle for every case. Aggregate claims about mechanism completeness must therefore remain limited to final file recovery, selector-produced coverage states, and auditable examples. The traces can identify whether particular evidence was absent, transformed, rejected, or restored, but those case findings should not be generalized into a corpus-wide mechanism-completeness rate.

## Full Workspace versus Codex

Codex exceeded Full Workspace on every headline ranking measure. It returned at least one implementation Oracle in 89.3% of runs, compared with 67.9% for Full Workspace, and recovered the complete implementation Oracle in 57.9%, compared with 40.7%. Its advantage was especially visible by rank five: R@5 was higher by 0.169 and NDCG@5 by 0.110. The held-out comparison was stronger still, with Codex reaching complete recall in all 28 held-out repetitions and Full Workspace doing so in 16.

The comparison also reflects different output behaviour. Codex returned 6.49 unique files on average, whereas Full Workspace returned 2.96. Some of its recall advantage therefore came with a broader evidence set rather than only better prioritisation. Standard P@5 still favoured Codex, however, so the additional files did not merely dilute its result: implementation evidence remained more concentrated within the first five positions.

This remains a complete-system comparison. Codex used its own iterative repository inspection and decided how to navigate, stop, and assemble evidence, whereas Workspace used the staged evidence lifecycle described in Chapter 5. The numerical difference cannot be assigned to agentic navigation alone, nor does the universal Codex `strong` and `sufficient` output constitute external validation of its explanations. The defensible result is narrower: under the evaluated configurations, Codex recovered and ranked the file Oracle more effectively and returned broader evidence, while the native pipeline exposed more conservative coverage judgements and substantially lower model-token use.

## Efficiency, Stability, and Failures

Table 7.4 places the quality results beside operational cost and repeated-run stability. Mean pairwise Jaccard similarity measures agreement among the four returned file sets for each case, then averages those case values. A higher value indicates more repeatable file selection. The mean R@10 standard deviation measures variation in recall, with lower values indicating greater stability.

| Condition | Mean files | Mean flow tokens | Mean seconds | File-set Jaccard | Mean SD of R@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 2.96 | 95,315 | 227.5 | 0.545 | 0.083 |
| Codex | 6.49 | 283,913 | 121.7 | 0.685 | 0.033 |
| Without CodeGraph | 2.81 | 82,177 | *not comparable* | 0.597 | 0.098 |
| Without adaptive controller | 2.66 | 47,566 | 127.4 | 0.657 | 0.079 |
| Without either capability | 2.50 | 46,176 | 115.8 | 0.601 | 0.092 |

Codex used approximately three times the flow tokens of Full Workspace, but it completed sooner on average. Provider-reported tokens and elapsed time therefore describe different operational costs and should not be treated as interchangeable measures. Disabling adaptive exploration nearly halved Workspace token use and reduced mean runtime by about 100 seconds. Removing CodeGraph while retaining the controller reduced mean flow tokens by approximately 13,100, while removing it after controller removal saved only about 1,400. The controller, rather than CodeGraph, was therefore the dominant source of native retrieval-flow token cost.

Runtime is not reported for Workspace without CodeGraph because several imported runs had placeholder zero-duration timestamps, while one run's recorded interval included an approximately four-hour interruption. These records do not provide a reliable estimate of ordinary execution time. Token accounting and final artifacts were available and remain included. Invalid infrastructure or schema attempts were retained in the condition ledgers but excluded according to the validity rule in Chapter 4; collection continued until every cell contained four valid runs.

Repeated-run agreement was moderate for every condition. Codex had the highest mean file-set Jaccard similarity and the lowest R@10 variation. Removing the controller increased Workspace file-set agreement from 0.545 to 0.657, consistent with eliminating stochastic later exploration, although round-zero semantic stages and final evidence selection remained model-backed. Graphless retrieval did not improve recall stability: its mean R@10 standard deviation was the highest of the five conditions.

## Representative Trace Cases

Vue 10519 demonstrates why CodeGraph's weaker top-ranked result cannot be explained simply by the addition of noisy neighbours. In Full Workspace run `run-20260902T084105Z`, raw dense and sparse retrieval found both the Oracle source file, `src/core/util/props.js`, and generated bundle files containing equivalent copies of its validation logic. CodeGraph then resolved the retrieved ranges into callable owners. It correctly identified the relevant formatting function in the original source file, but other validation ranges from that file became small or incomplete code fragments; the corresponding ranges in the generated bundles resolved to complete function bodies. Evidence from `src/core/util/props.js` was admitted, qualified, and retained through every controller round. Final evidence selection nevertheless preferred the complete validation chain from a generated bundle; file-trace preservation then added the original source file as the second result. All four Full Workspace repetitions therefore returned the generated bundle first and `src/core/util/props.js` second, whereas all four Workspace-without-CodeGraph repetitions returned only `src/core/util/props.js`. Full recall was identical, but P@1 was zero for Full Workspace and one without CodeGraph. The decisive loss of priority occurred during final evidence selection rather than raw retrieval.

Pandas 10068 illustrates a positive structural and controller interaction. Full Workspace recovered its complete implementation Oracle in every repetition. Removing CodeGraph reduced this to one repetition, removing only the controller to two, and removing both to none. A saved Full Workspace trace also showed a limitation: the relevant `_binop` owner remained in final evidence, but its visible source shrank during a later coverage call and lost part of the function signature and return context. The case therefore supports both sides of the aggregate result. Structural and adaptive processing could preserve an implementation that the simpler variants often missed, while survival of its file and identity did not guarantee stable presentation of its complete proof.

TypeScript 35468 provides a second controller-sensitive mechanism case. Full Workspace reached R@5 of 0.625 and complete recall in two of four repetitions. The graphless condition reached the same R@5 but never complete recall, while both controller-disabled conditions reached R@5 of 0.500 and also never completed the Oracle. The result is consistent with later exploration helping assemble more of a multi-file mechanism, but the variation across repetitions prevents treating one recovered set as a deterministic controller outcome.

Finally, TypeScript 19074 shows the size of the complete-system divergence on a difficult held-out case. Codex recovered the full implementation Oracle in all four repetitions. Full Workspace found any implementation Oracle once and never achieved full recall; the graphless condition behaved similarly, and both controller-disabled conditions produced no final implementation overlap. These final outputs do not reveal whether the native pipeline failed at raw retrieval or at a later selection boundary. They do establish that the agentic system repeatedly returned the known implementation while the native evidence pipeline did not.

Together, the aggregate and trace results separate three findings. Codex provided the strongest file localization at the highest token cost. Adaptive exploration supplied small but consistent native recall gains while accounting for most of the native retrieval-flow cost. CodeGraph did not improve aggregate early file ranking and only slightly improved complete recall when paired with the controller, although individual cases show useful structural recovery. The next chapter interprets these findings in relation to the research questions and the limits of the file-level Oracle.
