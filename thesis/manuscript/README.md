# Thesis manuscript workspace

This directory is the working Markdown manuscript area. It will eventually contain the complete thesis, organized as one Markdown file per chapter. The university LaTeX template remains unchanged in `../template/` and will be used only when the student-authored final text is converted for submission.

The files in this directory distinguish three kinds of material:

- **Working chapter draft:** complete chapter prose developed from the project evidence and intended for independent rewriting and verification by the student.
- **Evidence scaffold:** verified claims, source pointers, tables, and paragraph logic used while a chapter is still being developed.
- **Open item:** information that is incomplete, still being measured, or requires a decision.

The student independently rewrites and verifies the final submitted prose. Working drafts should retain enough source provenance to audit technical and empirical claims during that process.

## Structural editing rules

- Reorder first, then compress. Once chapters or subsections are in their intended sequence, reassess the transitions and remove explanations that serve only to recover context across the previous, misplaced order. Retain any context that the new sequence still requires.
- Do not vary paragraph or sentence length as an end in itself. Remove repeated explanatory templates and group ideas whose relationship is clearer when they are discussed together; let differences in purpose and complexity produce natural variation in length.

## Prose and notation rules

- Use present tense throughout the manuscript, including accounts of superseded experiments. Express chronology through explicit sequencing rather than shifts into past tense.
- Prefer active constructions such as “we use,” “we construct,” and “we evaluate” when they identify responsibility more clearly than passive voice.
- Present categorical definitions as lists when this makes their boundaries easier to inspect. Give substantial mathematical definitions as displayed equations rather than embedding them in long sentences.
- Name an internal file only when the filename materially supports reproducibility or a concrete case analysis.
- Define “retrieval testcase” at its first use; “case” thereafter means a retrieval testcase, not a software use case.
- Choose causal connectors for clarity. “Because” is acceptable in academic prose, while “as” or a restructured sentence may read more cleanly for secondary explanations.
- Define every project-specific term at first use. Cite external systems and research; define our own components and cross-reference their architectural descriptions.
- Expand compressed compounds when their words do not tell a new reader what object, stage, or scope they denote.
- Replace subjective acceptance language with observable criteria and measurements.

## Planned chapter files

1. `01-introduction.md`
2. `02-background.md`
3. `03-related-work.md`
4. `04-research-method.md`
5. `05-guided-intelligence-architecture.md`
6. `06-retrieval-design-rationale.md`
7. `07-evaluation.md`
8. `08-discussion.md`
9. `09-conclusion.md`

Chapter files are created when work on that chapter begins, avoiding empty placeholders and unnecessary structure.

## Appendix files

- `appendix-implemented-intent-contract-registry.md`
