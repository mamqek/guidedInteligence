# Evaluation

This chapter reports the evaluation described in Chapter 4. It comprises 35 CodeRepoQA-derived cases, five retrieval conditions, and four valid repetitions of every case-condition pair, giving 700 accepted runs. All conditions use `gpt-5.6-luna`, receive the same issue and pre-resolution repository, skip response generation, and retain final evidence selection. The chapter first reports file-level results, then compares the four Workspace configurations and Full Workspace with Codex. It examines cost, stability, and selected cases separately.

## Overall Retrieval Performance

Table 7.1 presents the principal ranking results across all 35 cases. Codex produces the strongest aggregate recall and ranking results: its R@5 is 0.677, compared with 0.517 for Full Workspace, and its NDCG@5 is 0.511, compared with 0.461. Full Workspace nevertheless places an implementation Oracle first more often, reaching P@1 of 0.450 compared with 0.386 for Codex. Among the native conditions, Workspace without CodeGraph has the highest P@1 and NDCG@5, whereas Full Workspace has the highest R@5 and R@10. The differences between these two configurations are small: Full Workspace gains 0.008 R@5, while the graphless condition gains 0.014 P@1 and 0.015 NDCG@5.

| Condition | P@1 | P@5 | R@5 | R@10 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 0.450 | 0.207 | 0.517 | 0.526 | 0.461 | 0.430 |
| Codex | 0.386 | 0.260 | 0.677 | 0.709 | 0.511 | 0.502 |
| Without CodeGraph | 0.464 | 0.207 | 0.508 | 0.514 | 0.476 | 0.444 |
| Without adaptive controller | 0.407 | 0.187 | 0.484 | 0.486 | 0.429 | 0.397 |
| Without either capability | 0.443 | 0.187 | 0.470 | 0.486 | 0.430 | 0.402 |

The development and held-out partitions follow the same broad recall pattern. The seven held-out cases provide an independent check across all issue categories, although their smaller number makes the exact aggregate values more sensitive to individual cases. Codex has the highest R@5 and NDCG@5 in both partitions. R@5 is higher on the held-out set for all four native conditions, ranging from 0.661 for the combined ablation to 0.786 without CodeGraph. This does not indicate that held-out cases are generally easier; it reflects the particular seven selected cases. Their useful role is to show that the aggregate recall advantage of Codex and the relatively small native-condition differences are not confined to cases used during formative development.

| Partition | Condition | P@5 | R@5 | NDCG@5 | Any implementation hit | Full implementation recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development | Full Workspace | 0.205 | 0.477 | 0.445 | 0.696 | 0.348 |
|  | Codex | 0.246 | 0.596 | 0.464 | 0.866 | 0.473 |
|  | Without CodeGraph | 0.198 | 0.439 | 0.439 | 0.661 | 0.295 |
|  | Without adaptive controller | 0.179 | 0.431 | 0.410 | 0.625 | 0.304 |
|  | Without either capability | 0.182 | 0.422 | 0.415 | 0.670 | 0.295 |
| Held-out | Full Workspace | 0.214 | 0.679 | 0.527 | 0.750 | 0.607 |
|  | Codex | 0.314 | 1.000 | 0.700 | 1.000 | 1.000 |
|  | Without CodeGraph | 0.243 | 0.786 | 0.620 | 0.821 | 0.750 |
|  | Without adaptive controller | 0.221 | 0.696 | 0.504 | 0.714 | 0.679 |
|  | Without either capability | 0.207 | 0.661 | 0.486 | 0.786 | 0.679 |

Repository and issue-category results vary considerably. Codex has the highest R@5 in TypeScript, pandas, and Vue. Among the native configurations, Full Workspace exceeds the graphless condition on TypeScript and pandas R@5, by 0.034 and 0.052 respectively, while the graphless condition exceeds Full Workspace on Vue by 0.059. Controller removal reduces aggregate native recall but not every repository-specific value. These small groups therefore locate heterogeneous behaviour rather than rank repositories or establish that a component is uniformly beneficial for a particular language.

## Contributions of CodeGraph and Adaptive Exploration

The four native conditions form the two-factor comparison defined in Chapter 4. Table 7.3 reports each capability's observed difference while the other capability is either present or absent. A positive value means that enabling the named capability increases the measure.

| Capability contrast | P@1 | R@5 | NDCG@5 | Any hit | Full recall | Mean flow-token difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adaptive controller, with CodeGraph | +0.043 | +0.033 | +0.032 | +0.064 | +0.021 | +33,494 |
| Adaptive controller, without CodeGraph | +0.021 | +0.039 | +0.046 | +0.000 | +0.014 | +29,944 |
| CodeGraph, with adaptive controller | -0.014 | +0.008 | -0.015 | +0.014 | +0.014 | +3,845 |
| CodeGraph, without adaptive controller | -0.036 | +0.014 | -0.001 | -0.050 | +0.007 | +295 |

Adaptive exploration produces modest positive aggregate differences under both structural settings. With CodeGraph enabled, it increases R@5 from 0.484 to 0.517 and full implementation recall from 0.379 to 0.400. Without CodeGraph, R@5 rises from 0.470 to 0.508 and full recall from 0.371 to 0.386. P@1 and NDCG@5 also increase in both comparisons. The direction is consistent with the controller recovering and reprioritising some relevant evidence after round zero, but the scale is limited relative to its additional model use. It also does not transform the native sufficiency outcome discussed below.

CodeGraph produces a smaller, measure-dependent trade-off. With the controller enabled, it increases R@5 by 0.008 and full implementation recall by 0.014, while P@1 falls by 0.014 and NDCG@5 by 0.015. Without adaptive exploration, it increases R@5 by 0.014 and full recall by 0.007, while P@1 falls by 0.036 and NDCG@5 is nearly unchanged. The completed evaluation therefore shows no large aggregate CodeGraph ranking penalty. Structural processing adds a small amount of relevant-file recovery, but the additional candidates do not consistently improve their ordering at the earliest ranks.

The interaction between the capabilities is limited. Adaptive exploration improves R@5 slightly more without CodeGraph, whereas its P@1 gain is larger with CodeGraph. CodeGraph's small full-recall gain appears both with and without the controller. These descriptive differences show that the controller can use structural evidence productively in some cases, but they do not establish a general dependency between the components.

## Evidence Survival and Mechanism Completeness

File ranking describes whether known fixing files reach the returned evidence, but it does not establish whether the selected source explains the requested mechanism. The final selector labels 137 Full Workspace runs `partial` and three `missing`; none is labelled `strong` or sufficient. Workspace without CodeGraph has 137 `partial`, two `missing`, and one `strong` run, with one run marked sufficient. Workspace without the controller has 137 `partial` and three `missing` runs, while the combined ablation labels all 140 runs `partial`; neither controller-disabled condition marks a run sufficient. Codex labels all 140 runs `strong` and sufficient. As Chapter 4 establishes, these are the systems' own judgements rather than independent completeness labels. The contrast therefore shows a substantial difference in output policy or confidence, but it cannot by itself establish that every Codex mechanism is complete or that almost every native result is objectively incomplete.

The controller's positive file-ranking differences do not produce a corresponding shift to sufficient native evidence. This gap is compatible with two distinct outcomes: later exploration can recover additional Oracle files without recovering every causal transition needed by the selector, or useful evidence can be weakened or rejected at a later boundary. The file-level statistics cannot distinguish these explanations. They support only the narrower conclusion that adaptive exploration improves retrieval modestly while mechanism-completeness judgements remain almost uniformly incomplete.

Saved traces also show why file identity alone is an incomplete survival measure. A candidate can remain present while the source visible to a later model is shortened, replaced by a structural owner, or omitted from a bounded request. These transformations are auditable in individual traces, but the final statistics do not provide a corpus-level owner or source-span correctness measure. They are therefore treated as diagnostic explanations for selected cases rather than as another aggregate evaluation result.

The evaluation does not include an independent owner-level or causal-transition Oracle for every case. Aggregate claims about mechanism completeness must therefore remain limited to final file recovery, selector-produced coverage states, and auditable examples. The traces can identify whether particular evidence is absent, transformed, rejected, or restored, but those case findings should not be generalised into a corpus-wide mechanism-completeness rate.

## Full Workspace versus Codex

Codex returns at least one implementation Oracle in 89.3% of runs, compared with 70.7% for Full Workspace, and recovers the complete implementation Oracle in 57.9%, compared with 40.0%. Its advantage is especially visible by rank five: R@5 is higher by 0.160 and NDCG@5 by 0.050. Full Workspace, however, has the higher P@1, 0.450 compared with 0.386. On the held-out cases, Codex reaches complete recall in all 28 repetitions and Full Workspace does so in 17.

The comparison also reflects different output behaviour. Codex returns 6.49 unique files on average, whereas Full Workspace returns 3.89. Some of its recall advantage therefore comes with a broader evidence set rather than only better prioritisation. Standard P@5 still favours Codex, however, so the additional files do not merely dilute its result: implementation evidence remains more concentrated within the first five positions, even though Full Workspace more often places one implementation file first.

This remains a complete-system comparison. Codex uses its own iterative repository inspection and decides how to navigate, stop, and assemble evidence, whereas Workspace uses the staged evidence lifecycle described in Chapter 5. The numerical difference cannot be assigned to agentic navigation alone, nor does the universal Codex `strong` and `sufficient` output constitute external validation of its explanations. The defensible result is narrower: under the evaluated configurations, Codex recovers more of the file Oracle and returns broader evidence, while Full Workspace has higher first-rank precision, more conservative coverage judgements, and substantially lower model-token use.

## Efficiency, Stability, and Failures

Table 7.4 places the quality results beside operational cost and repeated-run stability. Mean pairwise Jaccard similarity measures agreement among the four returned file sets for each case, then averages those case values. A higher value indicates more repeatable file selection. The mean R@10 standard deviation measures variation in recall, with lower values indicating greater stability.

| Condition | Mean files | Mean flow tokens | Mean seconds | File-set Jaccard | Mean SD of R@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 3.89 | 79,407 | 206.5 | 0.555 | 0.118 |
| Codex | 6.49 | 283,913 | 104.2 | 0.685 | 0.033 |
| Without CodeGraph | 3.81 | 75,562 | 182.4 | 0.519 | 0.071 |
| Without adaptive controller | 3.24 | 45,913 | 146.8 | 0.608 | 0.073 |
| Without either capability | 3.25 | 45,618 | 115.0 | 0.564 | 0.102 |

Codex uses approximately 3.6 times the flow tokens of Full Workspace but completes sooner on average. Provider-reported tokens and elapsed time therefore describe different operational costs and should not be treated as interchangeable measures. Disabling adaptive exploration reduces mean flow-token use by 33,494 with CodeGraph and 29,944 without it; the corresponding runtime reductions are 59.6 and 67.4 seconds. CodeGraph adds only 3,845 mean flow tokens when the controller is enabled and 295 when it is disabled, although it increases runtime by 24.1 and 31.8 seconds respectively. The controller is therefore the dominant source of native model-token cost, while both capabilities contribute to execution time.

Repeated-run agreement is moderate for every condition. Codex has the highest mean file-set Jaccard similarity and the lowest R@10 variation. Removing the controller increases Workspace file-set agreement from 0.555 to 0.608 and lowers mean R@10 standard deviation from 0.118 to 0.073, consistent with eliminating stochastic later exploration, although round-zero semantic stages and final evidence selection remain model-backed. CodeGraph's stability effect is mixed: with the controller it raises file-set agreement but also raises recall variation, while without the controller it has the opposite Jaccard effect and slightly lowers recall variation.

## Representative Trace Cases

Vue 9042 illustrates a difference in retrieval consistency. Each configuration processes the case independently four times. With CodeGraph enabled, the file containing the responsible implementation appears among the first five results in every run. Without CodeGraph, it appears in two of four runs when the adaptive controller is enabled and in only one run when the controller is also disabled. Related files are still returned in the unsuccessful runs, but the file that directly explains the failure is lost before final selection. CodeGraph therefore makes that central evidence substantially more likely to survive, while the controller provides only partial recovery when structural information is unavailable.

Pandas 10068 is an important counterexample to a general structural-benefit claim. Full Workspace recovers its implementation Oracle in one of four repetitions, while the other three native configurations never recover it. Codex recovers the complete implementation Oracle in all four repetitions. Full Workspace therefore has a small case-specific advantage over its ablations, but one successful repetition does not establish a reliable component effect. Without a boundary audit, the evaluation cannot assign the other three failures to raw retrieval, structural resolution, controller behaviour, or final selection.

TypeScript 35468 provides a second controller-sensitive mechanism case. Full Workspace reaches R@5 of 0.625 and complete recall in two of four repetitions. The graphless condition reaches R@5 of 0.438 and never complete recall, while both controller-disabled conditions reach R@5 of 0.500 and also never complete the Oracle. The result is consistent with later exploration and structural evidence helping assemble more of a multi-file mechanism, but the variation across repetitions prevents treating one recovered set as a deterministic controller outcome.

Finally, TypeScript 19074 shows the size of the complete-system divergence on a difficult held-out case. Codex recovers the full implementation Oracle in all four repetitions. Full Workspace and the graphless condition each find an implementation Oracle once and never achieve full recall, while both controller-disabled conditions produce no final implementation overlap. These final outputs do not reveal whether the native pipeline fails at raw retrieval or at a later selection boundary. They establish only that the agentic system repeatedly returns the known implementation while the native evidence pipeline does not.

Together, the aggregate and trace results separate three findings. Codex provides the strongest recall and ranked-list quality at the highest token cost, while Full Workspace has higher first-rank precision. Adaptive exploration supplies small but consistent native quality gains and accounts for most of the native retrieval-flow token cost. In the repaired pipeline, CodeGraph slightly improves recall while slightly reducing early-rank precision, without producing a large aggregate ranking penalty. The next chapter interprets these findings in relation to the research questions and the limits of the file-level Oracle.
