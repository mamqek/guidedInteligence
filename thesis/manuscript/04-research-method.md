# Research Method

## Research Design

This study combines artifact development with a controlled empirical evaluation of Guided Intelligence Workspace, the native system developed in this research to retrieve repository evidence for software-engineering questions derived from GitHub issue reports. Chapter 5 describes its architecture.

We use the development partition to iteratively diagnose retrieval failures. For each suspected failure mechanism, we formulate a bounded hypothesis, validate the relevant behaviour with focused tests, and then assess its retrieval effect through repeated full-pipeline executions. We define a regression as a repeated decrease in implementation-Oracle recovery or rank, or unstable `coverage_status` or `sufficient` outcomes under an otherwise unchanged comparison. We retain a change only when focused tests pass and repeated full-pipeline runs reproduce its intended effect without such a regression; lower token use alone does not justify retention. These experiments inform the final architecture, while Chapter 6 presents the principal retained and rejected changes as design rationale rather than evaluation evidence. After formative development, the system variants and evaluation procedure are frozen before the measured evaluation begins.

## CodeRepoQA Corpus and Historical Case Construction

We draw the initial issue candidates from the TypeScript, pandas, and Vue collections released with CodeRepoQA [@Hu2025CodeRepoQA]. CodeRepoQA uses multi-turn conversations from GitHub issues to evaluate questions that require repository-wide understanding. This study does not adopt its dialogue-answering protocol directly. Instead, we construct the issue categories, selection rules, pre-resolution snapshots, evaluator Oracles, and development and held-out partitions specifically for this retrieval evaluation.

The corpus contains 35 retrieval testcases: 11 from TypeScript, 12 from pandas, and 12 from Vue. It contains five testcases in each of seven categories: bug and regression, feature enhancement, performance and memory, compatibility and versioning, API behaviour and design, testing and build tooling, and maintenance and refactoring.

We include a case only when the initial issue describes a concrete software-engineering problem—such as a bug, requested feature, performance problem, API concern, or maintenance task—and a fixing pull request, commit, or comparable resolution artifact can be identified. We favour issues that can be understood without later discussion and whose resolution provides enough evidence to construct an Oracle. We also avoid selecting several cases that concern the same responsibility within the same subsystem. The resulting corpus includes both compact single-file changes and mechanisms spanning implementation, tests, documentation, or multiple subsystems, allowing retrieval to be compared across different issue intents and repository structures.

The 35 retrieval testcases are divided into 28 development cases and seven held-out cases. The development partition contains four cases from every issue category and is available during formative retrieval experiments. The held-out partition contains one case from each category and is not used to tune retrieval behaviour, providing a check on whether observed behaviour extends beyond the cases that inform system development. We report results separately for the two partitions before presenting a combined summary.

Each case pairs the visible issue with a repository snapshot from before its resolution. Where verified pull-request metadata provides a base commit, that commit defines the snapshot. Otherwise, the harness uses the parent of an identified fixing or event commit or, with lower confidence, the latest available commit preceding the issue's creation time. The selected commit is materialised as a detached checkout and reused across conditions. Retrieval receives only the issue title, creation time, body, and pre-resolution repository. Later comments, issue events, fixing references, pull-request metadata, diffs, and evaluator metadata remain hidden from the system. This separation prevents retrieval from accessing the known fix or later maintainer explanations that are not available when the issue first appears.

Indexing scope is defined independently of each case's Oracle. The indexing procedure excludes version-control data, dependency directories, virtual environments, caches, coverage data, generated build output, and retrieval-system state. For TypeScript, it also excludes generated compiler-test baselines and the entire `lib` directory, as the large generated compiler and server bundles make unscoped indexing impractical; authored compiler test inputs under `tests/cases` remain searchable. Excluding `lib` also removes declaration files and therefore limits the declaration-oriented evidence available to every condition. BM25, Qdrant, and CodeGraph receive the same effective exclusion list so that they index the same eligible repository paths. Repository snapshots and exclusions remain constant across the evaluated conditions, and no path is removed based on its relevance to an individual Oracle.

## Oracle Construction

Each retrieval testcase has a withheld file-level evaluation Oracle: the ground-truth set of repository files associated with the verified resolution. It is stored separately from the visible issue input supplied to retrieval. Post-resolution artifacts are materials produced or recorded when maintainers resolve the issue, including merged pull requests, fixing commits, their changed-file lists, linked issue events, and relevant maintainer explanations. The modified files in a merged pull request or fixing commit provide the principal evidence for the Oracle. For example, the resolution of Vue 10519 modifies the production file `src/core/util/props.js` and the regression test `test/unit/features/options/props.spec.js`; these enter the Oracle as implementation and validation evidence respectively. We use issue events and maintainer discussion only to construct and verify this withheld evaluator metadata. The resulting Oracle is finalised and stored before measured retrieval begins, so no evaluated condition can influence its definition.

Oracle files are classified by their role in the verified resolution:

- **Implementation files** contain the production behaviour changed to resolve the issue.
- **Test or validation files** exercise that behaviour or encode the regression.
- **Documentation files** record a relevant user-facing or maintenance consequence.

Test, validation, and documentation files count as supporting evidence rather than substitutes for the responsible implementation. The researcher manually assigned these roles from the verified changed-file lists and resolution context. Every case included in file-ranking statistics contains at least one implementation file.

Oracle and retrieved files are matched by exact repository-relative path after normalisation and duplicate removal. For file-level ranking measures, the final ranked evidence list is collapsed into unique files. When multiple evidence items come from the same file, that file inherits the position of its highest-ranked item. The implementation and supporting categories supply the relevance assignments defined in the evaluation-measures subsection.

We additionally construct a required-evidence reference for every testcase. The fixing pull request or commit identifies the source responsibilities needed to explain or verify the resolution, but every required unit is located in the pre-resolution snapshot and defined by repository-relative path, symbol, line range, and exact source anchors. Post-resolution source is never counted as retrieved evidence. A unit is present only when final evidence exposes all of its behaviour-bearing anchors. When a unit has several anchors, an initial declaration may identify the symbol without becoming an additional behavioural requirement; the selected range must still expose every remaining anchor. Related source that omits an essential anchor is partial, and source from the same file does not otherwise satisfy the unit. A run is evidence-complete only when every required unit is present together.

The reference also records the number of distinct files containing required units and whether two or more units are connected by a source-level call, data, state, configuration, or lifecycle path. Connectedness is a testcase characteristic, not another run-level success criterion: retrieval need not label the relationship explicitly. We compare connected and independent evidence sets descriptively and report required-file count separately because connected cases more often span several files. For each run, we additionally count all files returned by final selection, how many required-evidence files they represent, and how many belong to the broader implementation Oracle.

For Workspace runs with incomplete units, successive trace stages identify the first recorded boundary at which the unit becomes unavailable after its last appearance. The standard boundaries are raw retrieval, range preparation, initial comparison, controller recovery or semantic qualification, candidate-pool construction, and final evidence selection. Here, *initial comparison* denotes the reduction from prepared ranges or structural owners to the round-zero snippets admitted for qualification. Final-selection omissions are directly recorded; earlier boundaries are inferred from the change between consecutive recorded stages and do not necessarily identify the exact internal decision responsible. Codex exposes final source ranges but not an equivalent internal lifecycle trace, so its missing units are not assigned an internal loss boundary.

Final evidence selection also produces `coverage_status` and `sufficient` outputs. These values remain the selector's own judgements rather than ground-truth labels and are analysed separately from required-evidence completeness. Both references have limitations: fixing changes can include incidental files, omit relevant unchanged context, or address more than one concern, while defining the minimum explanatory snippets requires researcher judgement. Exact source anchors, frozen pre-resolution ranges, and a generated per-run audit make those judgements inspectable and reproducible.

## Evaluated Systems and Comparison Design

The evaluation compares the five conditions summarised below. The four Workspace conditions form a two-factor design that independently varies structural graph support and adaptive exploration. Codex provides a complete-system comparison rather than a Workspace ablation. All LLM-backed stages use `gpt-5.6-luna`.

| Condition | CodeGraph | Adaptive controller | Experimental role |
| --- | ---: | ---: | --- |
| Full Workspace | Enabled | Enabled | Reference native pipeline |
| Workspace without CodeGraph | Disabled | Enabled | Structural-retrieval ablation |
| Workspace without adaptive controller | Enabled | Disabled | Adaptive-exploration ablation |
| Workspace without CodeGraph and without adaptive controller | Disabled | Disabled | Combined ablation and interaction condition |
| Codex retrieval | Not applicable | Not applicable | External complete-system comparison |

Full Workspace is the native reference condition, combining CodeGraph-based structural processing with post-round-zero adaptive exploration. Its three phases are initial evidence construction, bounded adaptive completion, and final evidence selection; Chapter 5 describes their architecture. The evaluation disables response generation but retains final evidence selection because it is part of the deployed retrieval flow and each condition can change the evidence presented to its selection model.

The first native ablation disables CodeGraph-based owner resolution, graph evidence, and graph-dependent navigation; structural operations return explicit empty results. Qdrant's lexical and semantic retrieval channels remain enabled, and retrieved ranges remain available as range-level observations for semantic qualification and adaptive exploration. Final evidence selection also remains unchanged. This contrast isolates the contribution of CodeGraph-based structural grounding.

The second native ablation disables adaptive exploration after round zero, including controller-directed follow-up retrieval and qualification. Initial retrieval and round-zero semantic qualification remain enabled, and the resulting evidence passes directly to the unchanged final-selection stages. This contrast isolates the contribution of post-round-zero controller exploration.

The combined native ablation neither resolves retrieved ranges through CodeGraph nor performs adaptive exploration after round zero. The remaining lexical and semantic evidence proceeds through the unchanged final-selection boundary. This condition completes the factorial design and allows the evaluation to determine whether the contribution of either capability depends on the presence of the other.

Codex retrieval provides the external agentic comparison. It uses the frozen `efficient` prompt profile and inspects the pre-resolution repository through its own retrieval process rather than the Workspace stages. We evaluate its evidence against the same frozen Oracles. Differences can arise from search, source inspection, context construction, navigation, stopping, or evidence selection; the comparison therefore characterises complete-system behaviour rather than isolating a single component.

All four Workspace conditions receive the same issue and pre-resolution repository and search the same eligible source files. Owner comparison, semantic qualification, and final evidence selection follow the same rules wherever those stages execute; the controller-disabled conditions simply omit the later adaptive rounds. Only CodeGraph and post-round-zero adaptive exploration vary. The table therefore provides two estimates of each capability: CodeGraph with and without adaptive exploration, and adaptive exploration with and without CodeGraph. Comparing each pair shows whether the capabilities depend on one another. Full Workspace versus Codex remains a separate complete-system comparison because the systems differ across retrieval, navigation, stopping, and evidence selection.

## Quantitative Evaluation Measures

We measure relevant-file retrieval and ranking at cutoffs of 1, 2, 5, and 10 positions in the ranked list of unique retrieved files. Let $TP_k$ denote implementation-Oracle files within the first $k$ positions, $FP_k$ denote non-Oracle or unfilled positions within that cutoff, and $FN_k$ denote implementation-Oracle files absent from the first $k$ positions. The evaluation uses three ranking measures:

1. **Precision at rank $k$** measures the concentration of responsible implementation files near the top of the result:

   $$
   P@k = \frac{TP_k}{TP_k + FP_k} = \frac{TP_k}{k}.
   $$

   The second equality follows from treating unfilled positions as non-relevant when a system returns fewer than $k$ files.

2. **Recall at rank $k$** measures recovery of the known implementation set:

   $$
   R@k = \frac{TP_k}{TP_k + FN_k}.
   $$

3. **Normalised discounted cumulative gain at rank $k$** accounts for both position and graded relevance. Implementation files receive relevance grade 2, supporting test, validation, or documentation files receive grade 1, and all other files receive grade 0. For the relevance grade $rel_i$ at position $i$:

   $$
   DCG@k = \sum_{i=1}^{k} \frac{2^{rel_i}-1}{\log_2(i+1)},
   \qquad
   NDCG@k = \frac{DCG@k}{IDCG@k}.
   $$

   $IDCG@k$ is the maximum attainable discounted gain for the same case, with implementation files ranked before supporting files. NDCG ranges from zero to one and rewards early implementation evidence most strongly while still recognising supporting evidence.

The comparison also records selected-evidence counts and the number of unique files in the ranked output, distinguishing ranking differences from result-set size. Required-evidence results report evidence-complete runs, survival of individual required units, required-file representation, and first-unavailable boundaries. Complete-run rates weight every repetition equally. Unit-survival rates treat every required unit in every repetition as an observation and therefore describe source survival rather than an equally weighted testcase average. We measure efficiency using end-to-end runtime and provider-reported retrieval-flow tokens; response-generation and index-construction costs are excluded.

As the LLM-backed stages remain potentially stochastic, each case-condition pair has four valid repetitions under a fixed configuration. Across five conditions and 35 retrieval testcases, this produces 700 valid runs. We describe run-to-run variation using the frequency of any implementation-file hit and full implementation recall, the mean pairwise Jaccard similarity of retrieved-file sets, and the population standard deviation of R@10. For every ranking and operational measure, we first average values across the four repetitions of one case and then macro-average the case means. This gives every case equal weight.

A run is valid when the intended condition and repository snapshot complete with parseable artifacts and without an infrastructure, configuration, or schema failure. A completed retrieval that returns no evidence remains valid and receives zero ranking scores. Infrastructure interruptions, unavailable services, policy-blocked tool execution, schema-invalid outputs, and incomplete artifacts remain recorded in the run ledgers but are excluded from aggregates. Collection continues until four valid repetitions are available for every case and condition. Valid runs are not replaced based on their retrieval scores, maintaining an auditable separation between execution failure handling and retrieval quality.

After corpus-wide scoring, four cases are selected purposively for diagnostic discussion. Pandas 10068 shows cross-run fragmentation of a connected three-file mechanism; pandas 16499 shows structural-owner and controller effects on three independent requirements in one file; Vue 10803 isolates repeated loss at final evidence selection; and TypeScript 16278 exposes the capacity problem of a six-file required set. The selection covers different connection, file-dispersion, component, and loss-boundary patterns rather than favouring successful configurations. It is outcome-informed rather than statistically representative, and the complete 35-case run ledger remains available in the appendix.

## Reproducibility, Validity, and Ethical Scope

Each execution produces a timestamped run directory containing enough information to identify the testcase, repository state, active configuration, and recorded stage decisions. Versioned condition files and run ledgers record accepted and failed attempts with their timing and failure reasons. A repository-local analysis script links aggregate results back to individual run IDs without placing the complete run inventory in the main thesis narrative.

The repository snapshot and indexing configuration control index reuse. BM25 and Qdrant indexes are constructed over the same eligible paths and reused across the four Workspace conditions; the ablations change the availability of CodeGraph and adaptive exploration rather than the underlying lexical or vector corpus. Repeated runs also reuse the prepared snapshot and indexes instead of rebuilding them. This removes index construction as a source of within-case variation, although reported runtime and token totals consequently describe retrieval execution rather than the cost of preparing a repository for first use.

The artifacts support audit of the reported runs and calculations, but not bit-for-bit reproduction, as hosted models, service infrastructure, and the Codex environment can change. Runtime also varies with machine load, network latency, and provider response time, so it represents this evaluation rather than a platform-independent constant.

Several validity boundaries constrain interpretation. The factorial design supports attribution to the two Workspace capabilities, whereas the Workspace-Codex contrast supports only complete-system conclusions. File-ranking measures show recovery and ordering of known fixing files. Required-evidence completeness establishes whether the defined source is jointly available, but not whether a response model understands the relationships between present snippets. The connected-versus-independent comparison is descriptive because connected cases also tend to contain more units and span more files. External validity is limited by the historical corpus, three selected open-source repositories, their language ecosystems and structures, and repository-specific exclusions.

The empirical material consists of publicly available open-source repositories, issue reports, and resolution artifacts; the study involves no recruited participants or intervention in repository communities. We do not use author identities as study variables, and the evaluation does not require private repository content or confidential research data to be submitted to model providers. We treat any generative AI output used during the research as unverified assistance, while responsibility for testcase selection, Oracle construction, experimental decisions, source verification, and analysis remains with the researcher. The Discussion examines the broader risks of unsupported repository explanations, privacy and intellectual-property exposure, and overreliance on apparently plausible output.
