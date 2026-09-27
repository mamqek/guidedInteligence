## 1. **Introduction** — ~1,200–1,500 words


- **Opening motivation and problem context** — establish why repository-level assistance requires inspectable project evidence rather than generic model knowledge or isolated code matches.

    - Begin with unfamiliar-codebase questions whose answers depend on several files, functions, and responsibilities.
    - Explain that locating a plausible file is useful but may leave the responsible function, caller, state transition, or downstream effect unsupported.
    - Introduce learning-oriented assistance as the motivating application: explanations and follow-up questions require source that can be inspected and traced back to the repository.
    - Do not define retrieval techniques here. Chapter 2 introduces evidence units and retrieval terminology; Chapter 3 reviews the relevant research.

- **Problem statement and research gap** — narrow the thesis problem from general repository understanding to the controlled construction and preservation of repository evidence.

    - Distinguish file localization from source-level evidence, structural-owner identification from causal explanation, and initial discovery from survival into the final bounded context.
    - Explain that flexible agentic navigation and application-controlled retrieval allocate search, validation, stopping, and evidence-selection decisions differently.
    - State the gap at the level supported by the drafted Chapter 3: prior work addresses localization, repository question answering, structural navigation, agentic exploration, and grounding, but gives limited visibility into what happens to source between initial retrieval and final selection.
    - Avoid claiming that no previous system combines these ideas unless the related-work evidence supports that stronger statement.

- **Research objective and questions** — present one overarching objective followed by three questions with distinct evidential roles.

    - **Overarching objective:** Construct and examine a controlled repository-retrieval pipeline that makes its source evidence and selection decisions inspectable for unfamiliar-codebase questions.
        - This frames the complete thesis rather than adding a fourth research question or implying measured developer learning.
        - Chapters 5 and 6 establish the implemented answer; Chapters 7 and 8 evaluate and interpret its behaviour.
        - “Support” means constructing inspectable repository evidence for downstream explanation. It does not mean that the thesis measures developer learning outcomes.
    - **RQ1:** How can retrieved source be turned into an evidence set whose support and selection history can be inspected?
        - This is the artifact and process question.
        - Answer it through the implemented evidence lifecycle, stage contracts, provenance records, bounded context construction, and formative design evidence in Chapters 5 and 6.
        - Do not present RQ1 as a causal component comparison or claim that every pipeline stage is independently validated by an ablation.
    - **RQ2:** What effects do structural resolution using CodeGraph and bounded adaptive exploration have on file retrieval quality, exact required-evidence survival, stability, and cost?
        - This is the native component question and is answered by the four-condition factorial Workspace comparison in Chapter 7.
        - The aggregate outcomes are file-level ranking and recovery, required-unit survival and joint completeness, repeated-run stability, runtime, and model-token use.
        - Workspace traces identify the first recorded boundary where incomplete units become unavailable; selected cases explain recurring or diagnostically distinct patterns without substituting for the corpus-wide audit.
    - **RQ3:** How does the complete native evidence pipeline compare with Codex retrieval in file-level localization, required-evidence completeness, stability, and retrieval cost?
        - This is a complete-system comparison rather than an ablation or a universal ranking of controlled and agentic architectures.
        - Differences may arise from several coupled decisions, including search, navigation, stopping, context construction, and final evidence selection.
        - The final selected source is scored against the same required-evidence reference, but Codex does not expose an equivalent internal lifecycle trace and therefore supports no comparable boundary analysis.

- **Research approach** — summarize the design without reproducing Chapter 4.

    - Construct Guided Intelligence as the research artifact.
    - Use formative experiments to diagnose retrieval failures and justify retained or rejected design decisions.
    - Freeze the evaluated configurations and compare four Workspace conditions and one Codex condition across 35 CodeRepoQA-derived retrieval testcases, with four valid repetitions per case-condition pair.
    - Use the factorial Workspace conditions to study CodeGraph and adaptive navigation, then compare Full Workspace with Codex as complete retrieval systems.
    - State that the primary quantitative evaluation concerns retrieved evidence rather than generated-answer similarity. Leave corpus construction, validity rules, metrics, model configuration, and statistical aggregation to Chapter 4.

- **Contributions** — state concrete outputs rather than broad aspirations.

    - A complete Guided Intelligence architecture that separates retrieval orchestration, bounded model decisions, evidence validation, response generation, and learning-oriented interaction.
    - A controlled repository-evidence pipeline with explicit evidence identities, provenance, qualification, budgets, stopping decisions, and final selection.
    - An evaluation procedure that combines file-level measures with a corpus-wide exact-source audit, standardised Workspace loss boundaries, and selected diagnostic traces, while separating infrastructure failures from valid retrieval failures.
    - Empirical findings about the effects and costs of structural resolution and bounded adaptive exploration within Workspace.
    - A complete-system comparison showing the trade-offs between native Workspace retrieval and Codex retrieval.
    - Keep detailed numerical findings in Chapter 7 and their interpretation in Chapter 8; the introduction may preview only the principal direction of the results.

- **Scope and claim boundaries** — declare exclusions before the chapter roadmap.

    - The thesis studies repository understanding, not code generation, patch production, or repair correctness.
    - Its principal empirical subject is retrieval and evidence construction, not final-answer similarity.
    - File-level Oracles support localization claims. A separate required-evidence reference establishes whether defined pre-resolution snippets survive together, but not whether a response model understands their relationships.
    - Learning-oriented interaction motivates the system design, but the study does not measure learning outcomes or compare teaching strategies with users.
    - The Codex comparison concerns the evaluated configurations and corpus, not all agentic and pipeline-based retrieval systems.

- **Thesis roadmap** — close with one compact paragraph that gives each later chapter a distinct role.

    - Chapter 2 defines repository-comprehension, retrieval, evidence, graph, provenance, and evaluation concepts.
    - Chapter 3 positions the work relative to localisation, repository retrieval, structural navigation, agentic exploration, grounding, and learning-oriented assistance.
    - Chapter 4 defines the research design, corpus, conditions, measures, validity rules, and analysis procedure.
    - Chapter 5 describes the final Guided Intelligence architecture and evidence lifecycle.
    - Chapter 6 explains the formative experiments and design decisions that produce that architecture.
    - Chapter 7 reports the frozen evaluation without answering the questions beyond the measured results.
    - Chapter 8 interprets the results through RQ1–RQ3 and discusses implications, limitations, and future work.
    - Chapter 9 consolidates the answers to the research questions, contributions, boundaries, and closing claim.

- **Introduction writing constraints**

    - Maintain a single progression: practical motivation → precise problem → research gap → objective and questions → approach → contributions → scope → roadmap.
    - Do not duplicate Chapter 2 definitions, Chapter 3 study-by-study discussion, Chapter 4 procedural details, Chapter 5 implementation internals, or Chapter 7 result tables.
    - Define only the minimum project-specific language needed to understand the questions; use later chapter cross-references for detail.
    - Ensure every contribution maps to at least one research question and one later chapter that supplies its evidence.

---

## 2. **Background** — ~1,500–1,800 words

- **Repository-level program comprehension** — define the problem and the evidence units used throughout the thesis.
    
    - Repository-level questions
    - Files, source ranges, snippets, symbols, and structural owners
    - Implementation evidence and supporting evidence
    - Multi-file and multi-responsibility mechanisms
    - Entry points, state changes, handoffs, and observable effects
    - Conceptual distinction between locating a relevant file and explaining a mechanism
- **Retrieving and structuring repository evidence** — introduce textual, semantic, and structural ways of locating and relating source.
    
    - Lexical and sparse retrieval
    - Embedding-based dense retrieval
    - Hybrid retrieval
    - Retrieval ranking and exact anchors
    - Abstract syntax trees and code graphs
    - Functions, methods, classes, and assignment-defined owners
    - Calls, references, containment, inheritance, and dependencies
    - Static-analysis limitations, including dynamic registration and runtime behaviour
    - Keep this treatment generic; Qdrant, CodeGraph, reciprocal-rank fusion, and the implemented Workspace pipeline belong in Chapter 5
- **From relevant source to evidence** — define the conceptual evidence lifecycle without reproducing the implemented architecture.

    1. Candidate retrieval
    2. Source and owner localization
    3. Semantic qualification
    4. Relationship or mechanism construction
    5. Final evidence selection

    - Explain that evidence can be lost or transformed after initial retrieval
    - Reserve concrete Workspace stages, states, and recovery mechanisms for Chapter 5
- **Controlled and agentic repository exploration** — alternative allocations of responsibility between application logic and model judgement.

    - Application-owned state, stages, budgets, and stopping
    - Model-directed search and navigation
    - Typed and validated actions
    - Iterative retrieval and context management
    - Provenance and auditability
    - Flexibility versus controllability
    - Provide the terminology required for RQ2 and RQ3 without comparing the evaluated systems
- **Evidence-grounded learning support** — concise conceptual foundation for the downstream interaction design.

    - Evidence-grounded explanation
    - Self-explanation
    - Generative `why` and `how` questions
    - Hints and scaffolding
    - Risks of unsupported assistance
    - Leave educational-effect findings to Chapter 3, implementation to Chapter 5, and implications to Chapter 8

---

## 3. **Related Work** — ~2,000–2,500 words

- **Developer information needs and code localization** — research on locating implementation material required for maintenance and comprehension.
    
    - Developer questions during unfamiliar-codebase work
    - Traditional code search
    - Bug and issue localization
    - Traceability between issue descriptions and source code
    - Identifier-based and semantic matching
- **Repository-level retrieval and structural navigation** — compare approaches that extend retrieval beyond a single query or file.
    
    - Multi-file context acquisition
    - Query reformulation and candidate reranking
    - Iterative source expansion
    - Repository-level retrieval-augmented generation
    - Call, dependency, symbol, and reference graphs
    - Graph-guided search and multi-hop localization
    - Structural ownership and cross-file navigation
    - Static-analysis limitations
    - Compare what each approach retrieves, which relationships it exposes, and whether relevant material survives into the final context
- **Agentic repository exploration** — systems assigning search and navigation decisions to an LLM.
    
    - Tool-using coding agents
    - Search, file inspection, and symbol navigation
    - Planning and iterative exploration
    - Agent memory and context management
    - Stopping and final evidence synthesis
- **Grounded and controllable AI assistance** — work related to explicit evidence construction and application-owned control.
    
    - Source attribution and provenance
    - Context selection
    - Evidence validation
    - Constrained tool execution
    - Auditable orchestration
    - Reliability and overconfidence
    - Distinction between citing source and preserving an inspectable account of how source enters, survives, or leaves the evidence set
- **Learning-oriented AI assistance** — research motivating Guided Intelligence’s downstream interaction design.
    
    - AI-supported programming education
    - Scaffolded learning
    - Guided questioning
    - Feedback and answer evaluation
    - Automation bias and overreliance
    - Boundaries of learning claims without a user study
- **Comparative synthesis and research gap** — compare prior work through a fixed set of dimensions and position the thesis contribution.
    
    - Retrieval unit: file, snippet, or structural owner
    - Lexical, semantic, and structural signals
    - Single-pass versus iterative exploration
    - Application-controlled versus model-controlled navigation
    - Evidence provenance and lifecycle visibility
    - Stopping and final evidence selection
    - File localization versus mechanism evidence
    - Evaluation of quality, stability, and cost
    - State the gap cautiously: existing approaches cover many individual elements, but provide limited evaluation of a controlled pipeline that combines them while exposing how evidence is admitted, transformed, recovered, and selected
    - Complete a focused literature-search pass before drafting; the current bibliography lacks sufficient repository-retrieval, graph-navigation, coding-agent, provenance, and controllable-retrieval research

---

## 4. **Methods** — ~2,500–3,100 words

- **Research design and formative experimentation** — artifact-oriented research supported by incremental retrieval experiments.
    
    - Identification of a concrete evidence-loss boundary
    - Formation of a bounded hypothesis
    - Isolated implementation of one behavioral change
    - Focused deterministic verification
    - Repeated actual-pipeline runs
    - Retention or reversion according to measured results
    - Separation of formative experiments from final evaluation
- **CodeRepoQA corpus and historical case construction** — preparation of retrieval-grounded repository issues.
    
    - TypeScript, Pandas, and Vue repositories
    - Retrieval-grounded issue categories
    - Development and frozen final partitions
    - Pre-resolution repository snapshots
    - Hidden resolution artifacts
    - Leakage prevention
    - Repository-aware index exclusions
- **File Oracles and required-evidence reference** — ground truth used for file-level and exact-source evaluation.
    
    - Implementation Oracle files
    - Supporting test, validation, and documentation files
    - Exact file normalization
    - Oracle limitations
    - Exact pre-resolution source units identified from the fixing artifact
    - Present, partial, and absent unit judgements
    - Whether required units are source-connected, and the number of files they span
    - Distinction between file overlap, joint source availability, and model understanding
- **Evaluated systems and configurations** — reproducible definition of the native variants and external retrieval condition.
    
    - Narrative boundary: retain only the short three-phase summary of initial evidence construction, bounded adaptive completion, and final evidence consolidation needed to define the ablations; defer the detailed pipeline mechanics to Chapter 5
    - **Full Workspace pipeline:** complete native retrieval with round-zero evidence construction followed by bounded adaptive-controller exploration
    - **Workspace without adaptive controller:** the same initial retrieval, CodeGraph resolution, owner comparison, round-zero qualification, structural components, semantic islands, final-pool construction, and final selector, but with adaptive exploration rounds bypassed after round zero
    - **No-CodeGraph native pipeline:** Qdrant-derived source snippets without CodeGraph owner resolution or graph-dependent navigation
    - **Workspace without CodeGraph and without adaptive controller:** Qdrant-derived range evidence proceeds through round-zero semantic admission and final selection without structural graph support or adaptive exploration
    - **Codex retrieval:** external agentic repository retrieval using the declared model, prompt profile, tools, and budget
    - Shared repository snapshots, issue inputs, source exclusions, and evaluation Oracles
    - Configuration-specific models, prompts, budgets, index signatures, and run-selection rules
- **Comparison framework** — distinct comparisons corresponding to different architectural questions.
    
    - **Adaptive-controller ablation:** full Workspace pipeline versus Workspace without adaptive controller
    - **Structural-retrieval ablation:** complete native pipeline versus no-CodeGraph native
    - **Two-factor interaction comparison:** use the combined ablation to measure the CodeGraph effect with and without adaptive exploration and the adaptive-controller effect with and without CodeGraph
    - **External-system comparison:** complete native pipeline versus Codex retrieval
    - Localization quality, required-evidence completeness, stability, runtime, tool use, and token cost across all conditions
    - Separation of component-level causal comparisons from complete-system comparisons
- **Quantitative evaluation measures** — ranking, survival, efficiency, and stability metrics.
    
    - P@1, P@2, P@5, and P@10
    - R@1, R@2, R@5, and R@10
    - NDCG at the same cutoffs
    - Required-unit survival and joint required-evidence completeness
    - Standardised first-unavailable boundaries for Workspace evidence
    - Final selected-file count, required files represented, and implementation-Oracle files represented
    - Tool calls, payload characters, runtime, and tokens
    - Repeated-run variation
    - Infrastructure and schema failure rates
- **Stage-aware and qualitative analysis** — investigation of how final retrieval outcomes arise.
    
    - Raw dense and sparse retrieval
    - Canonical snippet construction
    - File admission
    - Owner comparison
    - Round-zero qualification
    - Controller discovery
    - Final evidence selection
    - First recorded unavailability boundary
    - Required-evidence completeness
    - False-completeness and honest-partial cases
- **Reproducibility, validity, and ethics** — boundaries affecting interpretation of the results.
    
    - Run IDs and configuration hashes
    - Repository commits and snapshots
    - Index construction and reuse
    - Model stochasticity
    - Mixed-model comparisons
    - File-Oracle and required-evidence-reference validity
    - Repository and language generalizability
    - Use of generative AI during research

---

## 5. **Guided Intelligence Architecture** — ~2,400–2,900 words

- **Overall system architecture** — complete request lifecycle and separation of interaction, control, retrieval, and generation.
    
    - Expand the three-phase pipeline summary introduced in Methods into the detailed lifecycle, including each phase's inputs, transformations, outputs, and transition conditions
    - Treat this chapter as the primary account of pipeline mechanics; the Methods summary exists only to provide enough context for the ablation definitions
    - User request and conversation state
    - Intent classification and routing
    - Retrieval and evidence construction
    - Explanation generation
    - Guided follow-up interaction
    - Persistent logs and state transitions
- **Intent classification, retrieval context, and source policy** — separation of task interpretation, retrieval context, and per-run source access.
    
    - Implemented intent categories
    - Response-stage selection
    - Frontend source selection and backend source-key validation
    - Mapping of selected sources to enabled adapters and allowed evidence categories
    - `retrieval_required` as an unexercised evidence-reuse boundary for future multi-turn interaction
    - Response contracts
- **Learning-oriented interaction** — user-facing explanation and follow-up flow.
    
    - Structured evidence-grounded explanation
    - Guided questions
    - Hints and partial scaffolds
    - Answer evaluation
    - Repair and deepening
    - Completion behavior
    - Assistance boundaries encoded by the intent contracts
- **Repository retrieval capabilities** — lexical, semantic, structural, and exact-source operations available to the evidence pipeline.
    
    - Qdrant dense and sparse retrieval
    - Hybrid result construction
    - Exact source inspection
    - CodeGraph owner and relationship operations
    - Intended CodeGraph contribution: structural owner identity, verified relationships, and graph-dependent cross-file navigation
    - Exact graphless boundary: retention of Qdrant/BM25 ranges and non-graph stages while CodeGraph startup, resolution, graph evidence, and graph-dependent actions are disabled
    - Language-routed AST and source analysis
    - Assignment-defined structural owners
- **Initial evidence construction** — transformation of raw Qdrant results into qualified round-zero snippets.
    
    - Per-obligation Qdrant search
    - Global exact-range deduplication
    - CodeGraph range resolution
    - Canonical snippet construction
    - Cost-aware global file admission
    - Grouped owner comparison
    - Global round-zero snippet selection
    - Source disclosure and qualification
- **Controller evidence completion** — bounded iterative discovery of missing owners, handoffs, and relationships.
    
    - Evidence coverage and unresolved claims
    - Deferred and verified leads
    - Typed action construction
    - Action-novelty suppression
    - Run-local structural memoization
    - Deterministic scheduling and execution
    - Qualification of newly materialized snippets
    - Evidence-island and relationship construction
    - Stopping and final evidence selection
- **Provenance, control, and auditability** — cross-cutting representation of evidence decisions and retrieval behavior.
    
    - Canonical snippet identity
    - Dense, sparse, query, obligation, and source provenance
    - Selected, deferred, dormant, rejected, and final states
    - Payload and action budgets
    - Source-materialization telemetry
    - Explicit failures and stop reasons
    - Traceable LLM and deterministic decisions
        - Explain that intent classification records a short textual justification for the selected labels. Treat it as audit information for an LLM decision, not as an input that controls retrieval or response generation.
    - Implemented, experimental, rejected, and future boundaries

---

## 6. **Retrieval Design Rationale and Evolution** — ~1,900–2,400 words

- **From generic role coverage to implementation ownership** — transition from retrieving plausible explanatory roles to identifying the concrete implementation owners responsible for an issue.
    
    - Early evidence-role retrieval
    - Weak correspondence between roles and implementation responsibility
    - Implementation-role filtering
    - File- and owner-oriented retrieval
    - Exact source-range grounding
    - Structural owner identity
- **From repeated candidate processing to canonical evidence admission** — simplification and stabilization of the initial retrieval stages.
    
    - Early per-obligation file admission
    - Representative and held ranges
    - Repeated aggregation and canonicalization
    - Post-comparison deterministic clipping
    - Candidate lifecycle losses
    - Global range resolution before admission
    - Single canonical snippet pool
    - Cost-aware file admission
    - Grouped owner selection
    - Exhaustive lifecycle partitioning
- **From owner discovery to source-aligned qualification and candidate survival** — preservation of relevant structural owners through later pipeline stages.
    
    - Owner-aligned source previews
    - Complete source disclosure after selection
    - Assignment-defined owners
    - Deferred and dormant evidence
    - Verified source-grounded leads
    - Qualification of controller discoveries
    - Final-selection survival
    - First-unavailable-boundary observability
- **From repeated exploration to bounded controller discovery** — control of iterative source navigation and relationship discovery.
    
    - Repeated high-level and structural requests
    - Run-local deterministic memoization
    - Structured action-novelty ledger
    - Pre-slot suppression of duplicate effects
    - Typed action validation
    - Evidence-gain telemetry
    - Explicit no-gain and materialization-loss stopping
- **From implementation localization to mechanism-chain completion** — emergence of downstream causal connection as the principal unresolved retrieval problem.
    
    - TypeScript Builder, BuilderState, and WatchMode localization
    - Missing watcher, project-reference, wildcard, direct-import, and diagnostic handoffs
    - Pandas `_binop` and arithmetic-factory localization
    - Missing generated-method registration and public-operation contrast
    - Vue parser and DOM-property localization
    - Missing caller, diagnostic, and serialization transitions
    - Correct Oracle retention with incomplete final evidence
- **CodeGraph hypothesis and ablation motivation** — why structural resolution was expected to improve ownership and connected-mechanism evidence, and why unexpectedly strong graphless localization requires a separate measured explanation.
    
    - Expected contribution of owner resolution and verified graph relationships
    - Expected contribution of graph-dependent controller navigation
    - Possibility that direct lexical/semantic ranges already localize issue-relevant files well
    - Risk that structural expansion introduces candidate competition or dilution
    - Need to distinguish early ranking and file overlap from structural grounding and required-evidence completeness
    - Reserve approximately 150–250 words here; state hypotheses and design motivation, not evaluation conclusions
- **Controlled and agentic retrieval experiments** — comparison of alternative allocations of navigation and consolidation responsibility.
    
    - Full native adaptive controller
    - Frozen round-zero pipeline without adaptive exploration
    - Rejected agent-planned native controller experiment as evidence about responsibility allocation
    - Full external agentic retrieval
    - Flexible source inspection and search
    - Repeated exploration and context growth
    - Weak stopping and final consolidation
    - Native lifecycle and execution strengths
    - Complementary failure boundaries
- **Consolidated design principles and rejected alternatives** — retained lessons from successful and unsuccessful experiments.
    
    - Structural resolution before file admission
    - Single canonical identity construction
    - Explicit evidence lifecycle
    - Source-grounded semantic qualification
    - Bounded comparison and action budgets
    - Deterministic validation and execution
    - Agentic judgment limited to semantic action selection
    - Rejected evidence regions
    - Rejected expanded deferred recovery
    - Rejected residual materialization
    - Rejected speculative dynamic-registration relationships
    - Incomplete-source inspection as a separately evaluated experiment

---

## 7. **Evaluation** — ~3,000–3,700 words plus tables and figures

- **Evaluation setup and comparison conditions** — empirical scope and frozen configurations.
    
    - CodeRepoQA repositories and categories
    - Development and final partitions
    - Full Workspace pipeline with adaptive controller
    - Workspace without adaptive controller
    - No-CodeGraph native pipeline
    - Workspace without CodeGraph and without adaptive controller
    - Codex retrieval
    - Historical and current model cohorts
    - Index and source-exclusion conditions
    - Run-selection and failure criteria
- **Initial localization and evidence survival** — retrieval and retention of relevant implementation material across the native pipeline.
    
    - File-level P/R/NDCG
    - Dense and sparse Oracle retrieval
    - Canonical-pool Oracle coverage
    - File-admission survival
    - Structural-owner resolution
    - Owner-comparison decisions
    - Round-zero qualification
    - Controller candidate survival
    - Final evidence ranking
    - First-unavailable-boundary distribution
- **Adaptive-controller contribution ablation** — effect of bypassing adaptive exploration after unchanged round-zero evidence construction.
    
    - Shared initial evidence
    - Frozen round-zero candidate, component, and island state
    - Controller rounds, proposed actions, and executed actions present only in the full condition
    - Explored files, owners, and relationships
    - Duplicate and subsumed exploration
    - Newly discovered evidence
    - Mechanism-chain completion
    - Stopping behavior
    - Final evidence
    - Runtime, token cost, and repeated-run stability
    - Controller contribution with CodeGraph enabled versus disabled, using the combined ablation
- **CodeGraph contribution ablation** — effect of structural ownership and graph-dependent navigation.
    
    - Qdrant localization with and without structural resolution
    - Resolved owners versus unresolved source snippets
    - Canonical identity and candidate merging
    - Source disclosure and qualification
    - Cross-file navigation
    - Graph-dependent controller actions
    - Oracle survival and first-unavailable boundaries
    - Required-evidence completeness
    - Indexing, runtime, and token cost
    - CodeGraph contribution with adaptive exploration enabled versus disabled, using the combined ablation
    - Aggregate contrast between unexpectedly competitive graphless localization and any loss of structural grounding or mechanism-chain evidence
    - Representative traces that test candidate dilution, direct lexical/semantic matching, and first-unavailable-boundary explanations
    - Reserve approximately 300–450 words plus a shared comparison table; keep full per-case results in the appendix
- **Native-versus-Codex comparison** — comparison between the complete native pipeline and external Codex retrieval.
    
    - File and owner localization
    - Required-evidence completeness
    - Retrieval flexibility
    - Evidence grounding and provenance
    - Navigation and stopping
    - Final evidence consolidation
    - Tool use
    - Runtime and token cost
    - Repeated-run stability
    - Complementary failure boundaries
- **Required-evidence completeness and pipeline sufficiency** — evaluation of whether all defined pre-resolution source units survive together.

    - Present, partial, and absent required units
    - Connected versus independent evidence layouts as a descriptive case characteristic
    - Required-file count and final selected-file count
    - Complete runs and per-unit survival
    - First recorded unavailability across standardised Workspace boundaries
    - `coverage_status` and `sufficient`
    - Differences between selector confidence and independently scored completeness
- **Cross-configuration component and efficiency analysis** — combined reporting of structural capability, adaptive-controller contribution, and system-level cost.
    
    - Contribution of CodeGraph
    - Contribution of adaptive action selection
    - Interaction between CodeGraph and controller behavior
    - Candidate and file counts
    - Owner-comparison and qualification payloads
    - Controller and final-selection cost
    - Index construction and reuse
    - Action memoization and suppression
    - Failure and retry rates
- **Representative case analysis** — source-backed explanation of major outcome patterns.
    
    - Successful localization and complete mechanism construction
    - Successful localization with missing causal handoffs
    - Genuine raw-retrieval absence
    - Intermediate candidate loss
    - Relevant controller discovery
    - Repeated or unproductive navigation
    - CodeGraph-dependent owner or relationship recovery
    - Divergence between native and Codex retrieval paths
    - Select pandas 10068, pandas 16499, Vue 10803, and TypeScript 16278 after corpus-wide scoring to cover cross-run fragmentation, structural ownership, final-selection loss, and result-set capacity
    - State explicitly that this purposive selection is diagnostic rather than statistically representative
    - Place all 35 case-by-condition run tables in the appendix

---

## 8. **Discussion** — ~1,900–2,400 words

- **Interpretive frame: localisation, availability, and understanding** — establish the vocabulary used throughout the discussion before answering the research questions.

    - File overlap establishes localisation of a known fixing file.
    - Required-evidence completeness establishes that every defined pre-resolution source unit is jointly available in final evidence.
    - Neither measure establishes that a response model correctly understands the relationships among those units.
    - Structural-owner recovery and graph relationships provide additional navigation and identity evidence, but are not causal explanations by themselves.
    - Selector-produced `coverage_status` and `sufficient` values remain system outputs rather than independent truth.
    - Use this distinction once here, then apply it consistently instead of repeatedly re-explaining it under every RQ.

- **RQ1: Constructing auditable repository evidence** — answer the artifact question through the final architecture, formative evidence, and corpus-wide lifecycle audit without redescribing Chapter 5.

    - Stable source identity, provenance preservation, semantic qualification, bounded state transitions, and separate final evidence selection make intermediate evidence handling inspectable.
    - The audit demonstrates that missing source is not exclusively a raw-retrieval problem; it can first become unavailable during comparison, qualification or recovery, candidate-pool construction, or final selection.
    - Final-selection omissions are directly recorded. Earlier first-unavailable boundaries are inferred from consecutive stage observations and locate a boundary rather than proving the exact internal rejection decision.
    - RQ1 is therefore answered as a demonstrated capability for inspecting evidence construction, not as proof that every semantic decision is correct or that every item's full lineage is attached to the final evidence object.
    - Relate this interpretation to provenance and grounded-assistance literature from Chapter 3 without repeating the literature review.

- **RQ2: Contributions of structure and adaptive exploration** — interpret file-level and required-evidence results together because neither alone captures the component effects.

    - Adaptive exploration provides modest improvements in file ranking and required-unit survival while accounting for most of Workspace's additional model-token cost.
    - CodeGraph produces small aggregate file-ranking changes but contributes conditionally through owner identity, exact structural navigation, and source survival in particular cases.
    - Graphless Workspace remains competitive in early file ranking, showing that direct lexical and semantic retrieval already performs substantial localisation.
    - Avoid a universal CodeGraph benefit claim: the aggregate ranking effect is mixed, and structural candidates can still create competition or noise.
    - Interpret the connected-versus-independent comparison cautiously. Connected cases also contain more required units and more often span multiple files, so connectedness cannot be isolated as the cause of lower joint completeness.
    - Use pandas 16499, Vue 10803, and pandas 10068 only to explain the aggregate patterns already established in Chapter 7.
    - Refer to Chapter 7's values rather than reproducing its tables.

- **RQ3: Controlled versus agentic retrieval** — interpret Full Workspace and Codex as complete systems with different allocations of search, navigation, stopping, and consolidation responsibility.

    - Codex achieves stronger file recall and required-evidence completeness and returns broader evidence sets.
    - Full Workspace more often places an implementation file first, uses substantially fewer model tokens, and exposes its internal evidence lifecycle.
    - Codex's lower elapsed time despite higher token use shows that runtime and provider-reported token cost describe different operational trade-offs.
    - Codex's universal `strong` and `sufficient` outputs are not externally confirmed: the required-evidence reference finds substantially fewer complete runs.
    - Codex exposes final source ranges but no comparable internal lifecycle trace, so the evaluation cannot assign its omissions to first-unavailable boundaries.
    - Frame the result as a trade-off in the evaluated configurations, not as a universal ranking of controlled and agentic retrieval.

- **Implications for repository assistance and learning** — move from the RQ answers to what they imply for system behaviour while keeping retrieval as the empirical subject.

    - Evaluate and expose intermediate evidence survival rather than treating a final file hit as sufficient support.
    - Preserve uncertainty when required source is partial, and avoid generating complete causal explanations from incomplete evidence.
    - Treat broader result sets as an opportunity for greater coverage, not as proof of better prioritisation or understanding.
    - Evidence-grounded responses and understanding checks remain designed learning-support features; the evaluation does not establish that they improve learning.
    - The evaluated system handles independent requests. Multi-turn evidence reuse, refresh, and invalidation remain unvalidated.

- **Validity and generalisability** — consolidate the limitations that qualify the RQ answers, without repeating Chapter 4's procedure.

    - **Required-evidence construct:** the reference is researcher-constructed from fixing artifacts and pre-resolution source. Exact paths, ranges, anchors, and hashes are reproducible, but there is no independent annotator agreement and six cases retain judgment-sensitive scope choices.
    - **Boundary inference:** final-selection losses are direct records, whereas earlier first-unavailable boundaries are inferred from successive stage observations and do not prove the precise decision responsible.
    - **Connectedness comparison:** number of units and required files confound the descriptive connected-versus-independent result.
    - **System comparison:** Workspace and Codex differ in more than navigation policy, and Codex provides no comparable internal trace.
    - **Stochastic and reproducibility limits:** repeated runs estimate variation, but hosted models and service infrastructure prevent bit-for-bit reproduction.
    - **External validity:** three repositories, their languages and issue categories, static-analysis limits, and repository-specific exclusions constrain generalisation.
    - **Learning boundary:** no participants or learning outcomes are evaluated.

- **Ethics and responsible use** — reflection on ethical issues arising from the research artifact, evaluation, and thesis process.
    
    - Disclosure and responsible use of generative AI during research and writing
    - Student authorship and verification of all claims, citations, analyses, and submitted prose
    - Privacy, confidential-source, intellectual-property, and repository-licensing considerations
    - Risk of plausible but unsupported repository explanations and overconfident causal claims
    - Mitigation through source grounding, provenance, explicit uncertainty, and honest partial outcomes
    - Limits of using evidence-grounded explanations in learning contexts without directly measuring learning outcomes
- **Priorities for future work** — include only directions supported directly by the observed limitations.
    
    1. Independent annotation and response-level assessment of whether models correctly interpret relationships between jointly available snippets.
    2. Per-snippet lifecycle lineage attached directly to each final evidence item, replacing reconstruction across distributed trace events.
    3. Stronger source-span preservation and final evidence-selection methods, especially for multi-file requirements.
    4. Dynamic relationship and data-flow recovery beyond static CodeGraph coverage.
    5. More efficient adaptive exploration with clearer quality-to-cost gains.
    6. User studies of evidence-grounded explanations and understanding checks.
    7. Multi-turn evidence reuse, refresh, and invalidation.

    - Relate findings to prior work within the relevant RQ and implication sections rather than isolating that comparison at the end.
    - End by returning to the thesis claim: inspectable evidence construction improves what can be evaluated and qualified, but does not itself guarantee understanding.

---

## 9. **Conclusion** — ~650–850 words

- **Research outcome** — restate the problem, artifact, and evaluation in one short opening that follows directly from Chapter 8.

    - Repository understanding as construction of auditable evidence rather than plausible file matching
    - Controlled evidence-construction artifact
    - Evaluation across 35 cases, five conditions, and 700 accepted runs
    - Corpus-wide required-evidence audit across 78 exact source units
    - Do not repeat background, pipeline mechanics, or result tables
- **Answers to the research questions** — one concise paragraph per research question.
    
    - **RQ1:** The explicit evidence lifecycle makes source identity, qualification, bounded transitions, final selection, and the first recorded unavailability boundary inspectable. It does not make semantic decisions deterministic or prove understanding.
    - **RQ2:** Adaptive exploration provides modest ranking and source-survival gains at substantial token cost. CodeGraph has mixed aggregate ranking effects but conditionally improves owner grounding and required-source survival; neither capability guarantees multi-file completeness.
    - **RQ3:** Codex provides stronger file recall and required-evidence completeness with broader, more expensive evidence sets. Workspace provides stronger first-rank precision, lower model-token use, and greater lifecycle visibility. The comparison does not isolate agentic navigation as the cause.
    - Preserve the distinction between file localisation, demonstrated required-source availability, and model understanding in all three answers.
- **Contributions and boundaries** — consolidate the tangible outcomes and the central limitations without creating a second findings section.
    
    - Guided Intelligence artifact
    - Controlled repository-evidence pipeline
    - Explicit evidence lifecycle
    - Bounded adaptive exploration
    - File-level and exact required-evidence evaluation framework with a complete 700-run appendix
    - CodeGraph ablation findings
    - Adaptive-controller ablation findings
    - Native-versus-Codex findings
    - Central boundary: even exact required-source availability does not establish complete causal understanding.
    - Required-evidence definitions involve researcher judgement, most early unavailability boundaries are inferred, and Codex has no comparable lifecycle trace.
    - Connectedness is confounded with evidence-set and file count, and learning outcomes remain unmeasured.
- **Closing perspective** — finish with the principal thesis claim and only the highest-priority future directions.
    
    - Repository understanding should not be reduced to finding plausible files.
    - Trustworthy assistance should preserve how source becomes evidence, expose what remains unresolved, and avoid presenting incomplete localisation as complete understanding.
    - Mention only independent validation of evidence/understanding, stronger multi-file evidence preservation, and user evaluation as future priorities; Chapter 8 owns the detailed list.
    - End with the contribution actually established: an inspectable retrieval process provides stronger grounds for evaluating and qualifying repository assistance, even though it cannot guarantee that the resulting explanation is correct.
    

---

## **Appendices**

- **Implemented Intent Contract Registry**
    
    - Retrieval purposes, evidence expectations, and stopping conditions
    - Required semantic response stages and their purposes
    - Question prerequisites, allowed question forms, and permitted assistance
- **Experiment and configuration ledger**
    
    - Accepted experiments
    - Rejected and reverted experiments
    - Run IDs and configuration hashes
    - Prompts, schemas, and index signatures
- **CodeRepoQA corpus and Oracles**
    
    - Case inventory
    - Repository snapshots and commits
    - Implementation Oracles
    - Supporting Oracles
    - Exact required-evidence units and their source-connection classification
- **Complete evaluation results**
    
    - Full Workspace adaptive-controller runs
    - Workspace without adaptive-controller runs
    - No-CodeGraph native runs
    - Combined no-CodeGraph/no-adaptive-controller runs
    - Codex runs
    - File-ranking statistics
    - Full required-evidence reference for all 35 cases
    - All 700 run-level present, partial, and absent judgements
    - Required-file and selected-file counts
    - Workspace first-unavailable boundaries
    - Stage-level Oracle survival
    - Required-evidence completeness results
    - Component and controller comparisons
    - Category and repository breakdowns
- **Efficiency and stability results**
    
    - Candidate and evidence counts
    - Payload sizes
    - Token usage
    - Tool calls
    - Runtime
    - Repeated-run variation
    - Infrastructure and schema failures
- **Reproducibility material**
    
    - Source exclusions
    - Calculation procedures
    - Run-selection rules
    - Index-build and reuse records
    - Selected detailed trace analyses
---

## **Cross-Chapter Narrative Control: The CodeGraph Inner Story**

This is a secondary narrative thread inside the main thesis story. It must remain continuous across chapters without turning into a separate repeated mini-thesis. Each chapter has a distinct responsibility, and later chapters should refer back rather than redescribe the same architecture or repeat the same numbers.

1. **Architecture — capability and boundary.** Explain what CodeGraph provides by design: structural owner identity, exact symbol/range resolution, verified calls/references/dependencies, and graph-dependent navigation. Define the graphless condition precisely: Qdrant/BM25 ranges and the non-graph semantic stages remain, while CodeGraph indexing, resolution, graph evidence, and graph-dependent actions are disabled. Do not introduce outcome claims here.
2. **Retrieval Design Rationale — hypothesis and surprise.** Explain why structural resolution was expected to improve grounded ownership and connected mechanisms. Motivate the ablation as a test of that expectation. Introduce the alternative possibility that direct lexical/semantic retrieval already handles file localization well and that structural expansion can create candidate competition. Do not resolve the alternatives before presenting results.
3. **Evaluation — measured contrast.** Report full Workspace versus graphless ranking, Oracle survival, candidate/file counts, first-unavailable boundaries, mechanism evidence, sufficiency, runtime, and tokens. Use the combined no-CodeGraph/no-adaptive-controller condition to separate structural effects from controller compensation and to estimate their interaction. Distinguish directly recorded final-selection omissions from earlier boundaries inferred through successive stage observations. Describe graphless as “surprisingly competitive in localization” only where the measurements support it.
4. **Discussion — explanation and scope.** Interpret why graphless may perform strongly on file-ranking measures while lacking owner identity and graph navigation. Use the complete 2×2 comparison to determine whether adaptive exploration compensates for missing graph support or depends on CodeGraph-derived owners and relationships. Separate localization quality from connected causal evidence. Test reduced dilution and strong direct-match explanations against recorded traces. Do not infer that CodeGraph is unnecessary from aggregate P/R/NDCG alone.
5. **Conclusion — qualified finding.** State the final empirical answer in two or three sentences: where CodeGraph helped, where graphless remained competitive, which costs changed, and which mechanism-level claims the evidence did or did not establish.

Word-count control: approximately 150–250 words in Design Rationale, 300–450 words plus one shared table in Evaluation, 300–450 words in Discussion, and two or three sentences in Conclusion. Recover this space by describing configurations once in Methods, moving full case tables and trace ledgers to appendices, and avoiding numerical restatement in Discussion.

---

## **Selected Formative Experiments for the Thesis Narrative**

The thesis should not catalogue every implementation attempt. Include the following experiments because each establishes a reusable design lesson or directly supports an RQ. Keep the detailed run ledger in the appendix and limit the main-text treatment of each experiment to its problem, isolated change, decisive evidence, and resulting decision.

1. **CGC-to-CodeGraph replacement — retained structural foundation (RQ1/RQ2; ~120–160 words).**
    
    - Problem: the previous structural backend could time out and mixed heuristic matching with structural claims.
    - Intervention: assign exact owners and verified relationships to project-local CodeGraph while leaving conceptual retrieval to Qdrant.
    - Evidence: the historical TypeScript timeout case completed with a useful implementation owner, and the Vue case reduced structural indexing time and retrieval noise while moving the implementation owner from rank 2 to rank 1.
    - Lesson: CodeGraph made structural retrieval feasible and auditable, but did not by itself guarantee complete supporting or causal evidence.
    - Placement: Design Rationale; refer to it briefly in Architecture and connect it to the graphless ablation in Evaluation.

2. **Canonical snippet pool and snippet-first admission — retained initial-evidence redesign (RQ1; ~180–220 words).**
    
    - Problem: per-obligation/file processing repeatedly represented the same source, allowed large files to consume comparison capacity, and obscured where candidates disappeared.
    - Intervention: resolve ranges globally, construct one canonical snippet identity with merged provenance, and admit globally ranked snippets before grouped owner comparison.
    - Evidence: saved-input replays exposed substantially more files within a smaller bounded comparison payload while preserving previously selected owners; actual runs improved the visibility of Builder/BuilderState/WatchMode evidence even though downstream sufficiency remained incomplete.
    - Lesson: canonical identity and global admission improve auditability and competition between evidence, but do not remove later semantic-selection instability.
    - Placement: Design Rationale, supporting RQ1; architecture contains the final mechanism only.

3. **Evidence-region and preferred-size admission variants — rejected compression lesson (RQ1; combined ~120–160 words).**
    
    - Problem: initial owner-comparison payloads were large and structurally repetitive.
    - Interventions: group owners into evidence regions, then separately test a smaller quality-prefix admission boundary.
    - Evidence: regions reduced top-level units by about 14% but did not reduce tokens and failed the unchanged selection contract on repeat; the smaller prefix roughly halved comparison tokens and selected relevant owners but again violated the existing per-file response contract.
    - Lesson: deterministic compression or a cheaper prefix cannot be accepted merely for token savings when representation contracts and repeatability fail.
    - Placement: one compact rejected-alternatives paragraph in Design Rationale; detailed measurements in the appendix, not Discussion.

4. **Agent-planned native controller — rejected responsibility allocation (RQ2; ~180–220 words).**
    
    - Problem: determine whether one model planner per round could replace separate qualification, coverage, and scheduling decisions while retaining deterministic execution.
    - Intervention: a bounded planner classified new observations, updated coverage, and chose typed actions; grounding, execution, and final selection stayed application-owned.
    - Evidence: planner decision tokens fell by roughly one third, but two unchanged actual runs regressed from the native strong/sufficient reference to partial/insufficient results. The same `_binop` observation survived upstream stages but was inconsistently promoted, placing its first recorded unavailability at planner qualification.
    - Lesson: fewer calls/tokens did not justify unstable destruction of central evidence; semantic autonomy requires explicit lifecycle safeguards and repeatable quality.
    - Placement: Design Rationale and a short RQ2 interpretation in Discussion. It is formative evidence, not one of the five final evaluated configurations.

5. **Mixed-island file-trace representation — retained mechanism-connection repair (RQ1; ~180–220 words).**
    
    - Problem: WatchMode and the Helpers handoff were discovered but lost across island representation, trace eligibility, final selection, and the fixed evidence cap.
    - Intervention: preserve exact trace sources, keep trace eligibility tied to unresolved related obligations and repeated structural calls, and reserve capacity only for an LLM-accepted trace.
    - Evidence: two final TypeScript runs retained Builder, BuilderState, WatchMode, and Helpers without increasing action, round, graph-call, or evidence caps, while still reporting `partial/false`.
    - Lesson: evidence can be present yet lost at several post-retrieval boundaries; restoring a structural participant does not establish complete mechanism sufficiency.
    - Placement: Design Rationale and representative stage-loss case in Evaluation.

6. **Island packets and dormant-file recovery — retained bounded survival mechanisms with explicit limits (RQ1/RQ2; ~220–260 words total).**
    
    - Problem: coherent evidence islands and already-retrieved but initially unqualified owners could disappear before final comparison.
    - Interventions: baseline-seeded island packets preserve every normal-flow seed while adding coherent companions; `InspectDormantFileAlternatives` spends one existing action opportunity on a bounded batch from one zero-qualified file.
    - Evidence: the controlled packet comparison preserved every mandatory baseline seed and produced a positive cross-case signal without a systematic final-selection cost increase. Dormant inspection recovered Pandas `Series::_binop`, but ranking variants and two-file batching were rejected when gains were unstable or TypeScript fell below its safety floor. The retained exact-anchor correction treats ambiguous identifiers as search leads rather than exact authority and repeated the Pandas implementation recovery twice.
    - Lesson: bounded recovery can preserve evidence without hidden fallback behavior, but upstream qualification and candidate ordering remain stochastic and must be reported as limitations.
    - Placement: Design Rationale; Evaluation should use only the most representative traces, with the full experiment chain in the appendix.

Together these treatments consume approximately 1,000–1,240 words, leaving roughly half of the Design Rationale chapter for the broader problem-to-principle synthesis. The CodeGraph hypothesis budget above overlaps the first experiment rather than adding another independent block.

The adaptive-controller and CodeGraph ablations are final evaluation conditions, not formative experiments to narrate as design successes. Their implementation boundaries belong in Methods; their completed campaign results belong in Evaluation and Discussion.
