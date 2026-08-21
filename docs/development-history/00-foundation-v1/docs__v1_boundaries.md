# V1 Boundaries

## Purpose

V1 freezes the minimum behavior for the Guided Intelligence System before any framework, RAG, or Open SWE code is added.

The target user is a junior developer onboarding to an unfamiliar codebase. The system should provide scaffolded, evidence-grounded assistance that supports reasoning and understanding instead of directly completing the work for the user.

## Supported V1 User Flow

1. The user asks for help understanding code or project behavior.
2. The system explains first using grounded project evidence and ends that response with a knowledge-check question.
3. The system may continue the reasoning check in the `ask` stage to verify or deepen the user's understanding.
4. The system may provide a hint only after the explanation/ask path has been followed.

The stage sequence for v1 is:

```text
explain -> ask -> hint
```

Direct solution requests and stage-skipping attempts are treated as policy violations. The stage does not advance or change on those violations; the system explains the active stage expectation, explains why the request violates it, and offers the user a choice to either follow the current stage or return to explanation. There is no separate shortcut stage in v1.

## Allowed Source Categories

V1 responses may be grounded only in indexed, project-specific artifacts from these source categories:

- Source code
- Documentation
- Issue trackers
- Pull requests

The system must prefer project-specific evidence over generic pretrained model knowledge whenever it produces an explanation, question, or hint.

## Policy Violations

The following behaviors are explicit v1 policy violations:

- Direct solution requests
- Stage skipping
- Unsupported source usage
- Ungrounded answers that rely on generic pretrained knowledge instead of project artifacts

Policy violations should be represented explicitly in later code and logs, rather than handled only through prompt wording.

## Minimum Required Logs

V1 logging must capture enough information to make orchestration behavior auditable and reproducible:

- Stage decision
- Retrieval/source plan
- Evidence IDs or source references used
- Prompt or response payload
- Model settings if a model is used later
- Policy violations

These logs should describe what the system decided, what sources were allowed or used, and what response path was taken.

## V1 Exclusions

The following are intentionally out of scope for v1:

- No MCP adapter
- No Open SWE integration yet
- No real RAG implementation yet
- No automated task completion
- No fine-tuning
- No polished UI

The architecture may remain compatible with these later, but they should not shape the first implementation beyond keeping the core boundaries modular.

## Missing Decision Comment Format

When context or a design decision is missing, add a comment block using this exact format:

```md
<!-- DESIGN_DECISION_REQUIRED
Question: What needs to be decided?
Why it matters: One sentence explaining the implementation impact.
Expected format: The exact format the answer should use, such as a list, enum, table, or short paragraph.
Default for now: The temporary assumption used by v1.
-->
```

Use these comments sparingly. Only add them where implementation would otherwise require guessing.
