# Evaluation

This chapter reports the evaluation described in Chapter 4. It comprises 35 CodeRepoQA-derived cases, five retrieval conditions, and four valid repetitions of every case-condition pair, giving 700 accepted runs. All conditions use `gpt-5.6-luna`, receive the same issue and pre-resolution repository, skip response generation, and retain final evidence selection. The chapter first reports file-level results, then compares the four Workspace configurations and Full Workspace with Codex. It subsequently evaluates survival of the exact required source before examining cost, stability, and representative traces.

## Overall Retrieval Performance

The following table presents the principal ranking results across all 35 cases. Codex produces the strongest aggregate recall and ranking results: its R@5 is 0.677, compared with 0.517 for Full Workspace, and its NDCG@5 is 0.511, compared with 0.461. Full Workspace nevertheless places an implementation Oracle first more often, reaching P@1 of 0.450 compared with 0.386 for Codex. Among the native conditions, Workspace without CodeGraph has the highest P@1 and NDCG@5, whereas Full Workspace has the highest R@5 and R@10. The differences between these two configurations are small: Full Workspace gains 0.008 R@5, while the graphless condition gains 0.014 P@1 and 0.015 NDCG@5.

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

The four native conditions form the two-factor comparison defined in Chapter 4. The following table reports each capability's observed difference while the other capability is either present or absent. A positive value means that enabling the named capability increases the measure.

| Capability contrast | P@1 | R@5 | NDCG@5 | Any hit | Full recall | Mean flow-token difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adaptive controller, with CodeGraph | +0.043 | +0.033 | +0.032 | +0.064 | +0.021 | +33,494 |
| Adaptive controller, without CodeGraph | +0.021 | +0.039 | +0.046 | +0.000 | +0.014 | +29,944 |
| CodeGraph, with adaptive controller | -0.014 | +0.008 | -0.015 | +0.014 | +0.014 | +3,845 |
| CodeGraph, without adaptive controller | -0.036 | +0.014 | -0.001 | -0.050 | +0.007 | +295 |

Adaptive exploration produces modest positive aggregate differences under both structural settings. With CodeGraph enabled, it increases R@5 from 0.484 to 0.517 and full implementation recall from 0.379 to 0.400. Without CodeGraph, R@5 rises from 0.470 to 0.508 and full recall from 0.371 to 0.386. P@1 and NDCG@5 also increase in both comparisons. The direction is consistent with the controller recovering and reprioritising some relevant evidence after round zero, but the scale is limited relative to its additional model use. It also does not transform the native sufficiency outcome discussed below.

CodeGraph produces a smaller, measure-dependent trade-off. With the controller enabled, it increases R@5 by 0.008 and full implementation recall by 0.014, while P@1 falls by 0.014 and NDCG@5 by 0.015. Without adaptive exploration, it increases R@5 by 0.014 and full recall by 0.007, while P@1 falls by 0.036 and NDCG@5 is nearly unchanged. The completed evaluation therefore shows no large aggregate CodeGraph ranking penalty. Structural processing adds a small amount of relevant-file recovery, but the additional candidates do not consistently improve their ordering at the earliest ranks.

The interaction between the capabilities is limited. Adaptive exploration improves R@5 slightly more without CodeGraph, whereas its P@1 gain is larger with CodeGraph. CodeGraph's small full-recall gain appears both with and without the controller. These descriptive differences show that the controller can use structural evidence productively in some cases, but they do not establish a general dependency between the components.

## Required-Evidence Survival and Completeness

File ranking describes whether known fixing files reach the returned evidence, but it does not establish whether their responsible source ranges survive. The required-evidence audit therefore evaluates 78 exact source units across all 35 cases and 700 runs. A run is complete only when every required unit is present in its final evidence. Full Workspace completes 23 of 140 runs, compared with 17 without CodeGraph, 19 without the controller, and 10 without either capability. Codex completes 55. Individual-unit survival follows the same overall ordering: 36.2% for Full Workspace, 26.9% without CodeGraph, 30.8% without the controller, 19.9% without either capability, and 58.7% for Codex.

| Condition | Evidence-complete runs | Required units present | Mean final files | Mean required files represented | Mean other files |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 23/140 (16.4%) | 113/312 (36.2%) | 3.89 | 1.01 | 2.81 |
| Without CodeGraph | 17/140 (12.1%) | 84/312 (26.9%) | 3.81 | 0.98 | 2.76 |
| Without adaptive controller | 19/140 (13.6%) | 96/312 (30.8%) | 3.24 | 0.91 | 2.29 |
| Without either capability | 10/140 (7.1%) | 62/312 (19.9%) | 3.25 | 0.89 | 2.29 |
| Codex | 55/140 (39.3%) | 183/312 (58.7%) | 6.49 | 1.36 | 5.00 |

The broader Codex output contributes to this advantage but does not guarantee completeness. On average, five of its 6.49 selected files are outside the implementation Oracle, and 85 Codex runs still omit or only partially expose at least one required unit. Full Workspace selects fewer files and retains fewer required units, but its ablations show that both native capabilities contribute to survival: removing CodeGraph reduces the number of present units by 29 and removing adaptive exploration reduces it by 17. Removing both reduces it by 51.

Seventeen cases contain two or more required snippets connected through source-level calls, state, data, configuration, or lifecycle paths; the other 18 have no inter-unit connection. Complete-set rates are lower for connected cases in Full Workspace and Codex, but unit-survival rates are slightly higher. This is not evidence that connections themselves help individual retrieval while harming completion. Connected cases are much more likely to span several files: 12 of 17 require at least two files, compared with three of 18 independent cases. Required-file count provides the clearer pattern. Full Workspace completes 19 of 80 one-file runs and four of 36 two-file runs, but none of the 24 runs requiring three or more files. Codex completes 39 of 80 one-file runs, 12 of 36 two-file runs, and four of 16 three-file runs; neither system completes the five- or six-file cases.

The Workspace traces locate the missing units more precisely. The table counts every absent or partial unit rather than assigning one boundary to an entire run. Raw retrieval is the first recorded unavailability boundary for 54 Full Workspace units. Another 19 first become unavailable during initial comparison, 31 during controller recovery or semantic qualification, 66 before entering the final candidate pool, and 29 during final evidence selection. The final-selection omissions are directly recorded; the earlier boundaries are inferred from successive stage observations and do not identify the exact rejecting decision. Graphless and controller-disabled conditions exhibit different distributions: removing CodeGraph increases unavailability at raw retrieval and semantic qualification, while disabling the controller increases it at initial comparison because no later exploration can recover the unit. Codex does not expose an equivalent internal trace, so only its final-unit status is reported.

| Condition | Raw retrieval | Initial comparison | Recovery or qualification | Candidate-pool construction | Final selection |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 54 | 19 | 31 | 66 | 29 |
| Without CodeGraph | 78 | 24 | 71 | 32 | 23 |
| Without adaptive controller | 90 | 62 | 49 | 0 | 15 |
| Without either capability | 82 | 29 | 134 | 0 | 5 |

The independent reference also clarifies the systems' own completeness judgements. The final selector labels 137 Full Workspace runs `partial` and three `missing`, while Codex labels all 140 runs `strong` and sufficient. Required-evidence scoring confirms that native evidence is often incomplete, but it also shows that Codex's universal confidence is not an external completeness result: only 55 Codex runs contain every defined required unit. Conversely, a complete required set establishes source availability, not that the response model understands every relationship between those snippets.

## Full Workspace versus Codex

Codex returns at least one implementation Oracle in 89.3% of runs, compared with 70.7% for Full Workspace, and recovers the complete implementation Oracle in 57.9%, compared with 40.0%. Its advantage is especially visible by rank five: R@5 is higher by 0.160 and NDCG@5 by 0.050. Full Workspace, however, has the higher P@1, 0.450 compared with 0.386. On the held-out cases, Codex reaches complete recall in all 28 repetitions and Full Workspace does so in 17.

The comparison also reflects different output behaviour. Codex returns 6.49 unique files on average, whereas Full Workspace returns 3.89. Some of its recall advantage therefore comes with a broader evidence set rather than only better prioritisation. Standard P@5 still favours Codex, however, so the additional files do not merely dilute its result: implementation evidence remains more concentrated within the first five positions, even though Full Workspace more often places one implementation file first.

This remains a complete-system comparison. Codex uses its own iterative repository inspection and decides how to navigate, stop, and assemble evidence, whereas Workspace uses the staged evidence lifecycle described in Chapter 5. The numerical difference cannot be assigned to agentic navigation alone, nor does the universal Codex `strong` and `sufficient` output constitute external validation of its explanations. The defensible result is narrower: under the evaluated configurations, Codex recovers more of the file Oracle and returns broader evidence, while Full Workspace has higher first-rank precision, more conservative coverage judgements, and substantially lower model-token use.

## Efficiency, Stability, and Failures

The following table places the quality results beside operational cost and repeated-run stability. Mean pairwise Jaccard similarity measures agreement among the four returned file sets for each case, then averages those case values. A higher value indicates more repeatable file selection. The mean R@10 standard deviation measures variation in recall, with lower values indicating greater stability.

| Condition | Mean files | Mean flow tokens | Mean seconds | File-set Jaccard | Mean SD of R@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 3.89 | 79,407 | 206.5 | 0.555 | 0.118 |
| Codex | 6.49 | 283,913 | 104.2 | 0.685 | 0.033 |
| Without CodeGraph | 3.81 | 75,562 | 182.4 | 0.519 | 0.071 |
| Without adaptive controller | 3.24 | 45,913 | 146.8 | 0.608 | 0.073 |
| Without either capability | 3.25 | 45,618 | 115.0 | 0.564 | 0.102 |

Codex uses approximately 3.6 times the flow tokens of Full Workspace but completes sooner on average. Provider-reported tokens and elapsed time therefore describe different operational costs and should not be treated as interchangeable measures. Disabling adaptive exploration reduces mean flow-token use by 33,494 with CodeGraph and 29,944 without it; the corresponding runtime reductions are 59.6 and 67.4 seconds. CodeGraph adds only 3,845 mean flow tokens when the controller is enabled and 295 when it is disabled, although it increases runtime by 24.1 and 31.8 seconds respectively. The controller is therefore the dominant source of native model-token cost, while both capabilities contribute to execution time.

Repeated-run agreement is moderate for every condition. Codex has the highest mean file-set Jaccard similarity and the lowest R@10 variation. Removing the controller increases Workspace file-set agreement from 0.555 to 0.608 and lowers mean R@10 standard deviation from 0.118 to 0.073, consistent with eliminating stochastic later exploration, although round-zero semantic stages and final evidence selection remain model-backed. CodeGraph's stability effect is mixed: with the controller it raises file-set agreement but also raises recall variation, while without the controller it has the opposite Jaccard effect and slightly lowers recall variation.

## Illustrative Case Analyses

The four cases below are selected after corpus-wide scoring to expose different combinations of connection, file dispersion, component behaviour, and first-unavailable boundary. They are not presented as statistically representative. The [Required-Evidence Audit appendix](appendix-required-evidence-audit.md) reports all 700 run-level judgements.

Pandas 10068 requires three connected snippets in three files: the named arithmetic wrapper, the common-name helper, and the Series binary-operation body. Full Workspace retains the wrapper in one repetition, the helper in three, and the binary-operation body in one, but never all three together. One wrapper reaches the final candidate pool and is then omitted, while other missing units disappear earlier. Codex retains all three in every repetition. This case demonstrates cross-run fragmentation: Full Workspace can locate every part of the mechanism, but does not assemble the parts in one final evidence set.

Pandas 16499 provides a contrasting independent, single-file case. Three test classes exhibit the same collection defect but do not call or pass state to one another. Full Workspace and Codex retain all three declarations in all four repetitions. Without the controller, Workspace is complete in two. Both graphless conditions are never complete: raw retrieval reaches the file and its class-start ranges, but initial comparison retains interior test methods without the declarations that expose the defective class names. CodeGraph is useful here not because the requirements form a graph path, but because owner resolution restores the enclosing class identity; the controller then makes that recovery more consistent.

Vue 10803 isolates a later loss. Both required snippets occur in one implementation file: `renderDOMProps` supplies the textarea value and `setText` constructs its child node. Full Workspace retains both in one repetition. In the other three, the helper reaches the final candidate pool and is omitted by final evidence selection. Every run still returns the responsible file, so file recall is perfect while exact required-evidence completeness is only one of four. This is the clearest example of a final hit concealing a later snippet-level loss.

TypeScript 16278 represents the opposite scale. Its refactor API path requires six snippets across six files, while the broader implementation Oracle contains eight files. No condition completes the required set. Full Workspace returns 5.5 files on average and represents 4.75 of the six required files; Codex returns 6.25 and represents 5.25. Several runs therefore return as many files as the minimum required-file count but still contain the wrong combination or only partial source ranges. This case shows that result-set size creates a capacity ceiling but does not by itself determine evidence completeness.

Together, the aggregate and trace results separate four findings. Codex provides the strongest file recall and required-evidence completeness at the highest token cost, while Full Workspace has higher first-rank precision. Adaptive exploration improves both file ranking and exact-source survival modestly and accounts for most of the native retrieval-flow token cost. CodeGraph has only small aggregate file-ranking effects but materially changes source ownership and survival in particular cases. Finally, incomplete evidence arises at several boundaries rather than from raw retrieval alone. The next chapter interprets these findings in relation to the research questions and their construct-validity limits.
