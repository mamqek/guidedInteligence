# Thesis outline review

Date: 2026-09-04

Status: planning guidance, not thesis prose.

## Overall assessment

The outline is detailed enough to begin writing. Its planned chapter budget is approximately 17,300-21,700 words, excluding tables, figures, references, and appendices. The evaluation chapter is the largest single chapter at 3,000-3,700 words, but remains about 17% of the planned main-text total rather than dominating it.

The central story is coherent: repository understanding progresses from initial retrieval, through structural localization and evidence qualification, to bounded navigation and final mechanism evidence. The four-system comparison can support this story if the two ablations are named and interpreted precisely.

## Required correction before drafting

The outline originally defined the controller comparison as an agentic controller versus a deterministic controller. The implemented fourth condition described in the 2026-09-04 retrieval changelog and `services/retrieval/docs/decisions/graphless-and-controller-ablation-plan.md` is an adaptive-controller ablation: retain initial retrieval, CodeGraph owner resolution, owner comparison, round-zero qualification and coverage, structural components, semantic islands, final-pool construction, and final evidence selection; bypass adaptive exploration after round zero.

These are different experiments. The thesis plan now uses these labels:

- Full Workspace pipeline
- Workspace without adaptive controller
- Workspace without CodeGraph
- Codex retrieval

The ablation boundary has been implemented and verified by two actual TypeScript runs with zero controller rounds/actions and unchanged final selection. The 35-case, four-run campaign was still in progress at the time of this update, so conclusions about the adaptive controller's quality contribution must remain open until that campaign is complete.

## Story and chapter boundaries

Keep each chapter responsible for a different question:

- **Methods:** what was compared, how cases and Oracles were constructed, which metrics were calculated, and how validity/reproducibility were protected.
- **Architecture:** how the implemented full Workspace pipeline works. Describe each important stage once, including its inputs, outputs, decisions, provenance, and failure behavior.
- **Design rationale and evolution:** why the retained architecture exists, which observed failure boundaries motivated changes, and which alternatives were rejected. This should be an analytical reconstruction, not a chronological lab diary.
- **Evaluation:** what the measurements and trace analyses show. Report before interpreting.
- **Discussion:** why the results matter, how they answer the RQs, how they relate to prior work, and what the validity and ethics boundaries are.

The largest overlap risks are Architecture versus Design Rationale, Methods versus Evaluation setup, and Evaluation cross-configuration analysis versus Discussion. Enforcing the responsibilities above will prevent repeated pipeline descriptions and repeated result summaries.

The note that “failed attempts go to Discussion” should be narrowed. Include a failed or reverted experiment only when it supplies evidence for an RQ, explains a retained design decision, or establishes a limitation. Put the concise interpretation in Design Rationale or Discussion as appropriate and move the detailed experiment ledger to an appendix. The manual explicitly warns against presenting the thesis as a chronological log of the research process.

The university manual explicitly calls for an ethical reflection in the thesis discussion. The current plan mentions ethics under Methods but not clearly under Discussion. Add a short ethics-and-responsible-use subsection to Discussion, including generative-AI disclosure, data/privacy considerations if applicable, and the risk of unsupported repository explanations. This can replace part of the current “learning-oriented implications” budget rather than increasing the total.

The student contribution should also be stated explicitly in the Introduction, distinguished from prior work in Related Work, and restated as tangible contributions in the Conclusion.

## Incorporating the no-CodeGraph finding

Do not turn the ablation into a separate chapter and do not weave result claims into every pipeline stage. Use one recurring contrast with different roles:

- **Architecture:** explain what CodeGraph contributes by design and define exactly what the graphless boundary removes. Do not report outcome claims here.
- **Design rationale:** state the hypothesis that structural ownership and graph navigation should improve grounded connection and mechanism completion, and motivate the ablation.
- **Evaluation:** report the aggregate ranking, survival, sufficiency, cost, and selected stage-trace/case results for full Workspace versus graphless.
- **Discussion:** explain why graphless can rank well even though it lacks structural owners and graph navigation. Candidate explanations to test against traces include reduced candidate dilution, strong direct lexical/semantic matches, and a mismatch between file-ranking metrics and mechanism-chain completeness.
- **Conclusion:** give only the final qualified finding in two or three sentences.

The current aggregate results justify a nuanced “surprisingly competitive localization” claim, not “CodeGraph was unnecessary.” Across four runs on 35 cases, graphless has stronger early-rank precision and NDCG than full Workspace, similar R@5, fewer mean files, and lower mean flow-token use. Full Workspace retains a somewhat higher full-Oracle rate. Both conditions have almost no `sufficient` outcomes, so the existing aggregate alone does not demonstrate mechanism completion. Stage traces and representative cases are necessary before attributing gains or losses to CodeGraph.

This treatment can fit the existing word budget. Reserve roughly 150-250 words in Design Rationale, 300-450 in Evaluation in addition to a shared comparison table, 300-450 in Discussion, and two or three sentences in the Conclusion. Recover that space by removing repeated configuration descriptions, moving full per-case tables to an appendix, and letting the Discussion reference Evaluation results rather than restating every value.

## Research-question alignment

RQ2 currently asks what hybrid retrieval, structural resolution, semantic qualification, and controller navigation each contribute. The planned configurations causally isolate CodeGraph and controller rounds, but do not isolate hybrid retrieval or semantic qualification. Either add corresponding ablations or narrow RQ2. A more defensible version is:

> What do CodeGraph-based structural resolution and bounded controller navigation contribute to localization quality, evidence survival, mechanism completeness, stability, and cost?

Hybrid retrieval and semantic qualification can remain parts of the artifact described for RQ1 without claiming that their individual effects were isolated empirically.

## Recommended writing order

1. Create the thesis skeleton, bibliography, terminology list, evidence ledger, and figure/table placeholders.
2. Draft Methods while the no-adaptive-controller campaign is pending; freeze configuration names and evaluation rules before interpreting results.
3. Draft Architecture from the implemented system and traces.
4. Draft Design Rationale and Evolution from the decision notes and retrieval changelog, organized by problem and retained principle rather than date.
5. Complete the no-adaptive-controller runs, generate tables, and write the factual Evaluation results.
6. Draft Background and Related Work, then use them to sharpen the comparative claims.
7. Write Discussion as direct answers to the RQs, including validity and ethics.
8. Write Conclusion.
9. Rewrite Introduction so its promises exactly match the finished thesis.
10. Write the Abstract last, then perform a complete consistency, citation, layout, and rubric pass.

Within each chapter, write tables/figures and their one-sentence takeaways first, then supporting prose. This keeps the narrative tied to evidence and makes it easier to stay within the word budget.
