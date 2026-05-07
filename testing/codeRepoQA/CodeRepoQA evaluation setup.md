# CodeRepoQA Evaluation Setup

## Purpose

This document describes the evaluation system that should be built around the current Guided Intelligence policy core. It intentionally does not require CodeRepoQA-specific temporal visibility, hidden dossiers, model comparisons, or scoring logic to be encoded in the current runtime implementation.

The evaluation harness should test whether the system can produce a grounded, learning-oriented explanation path from a historical issue and a pre-resolution repository snapshot. The main target is guided understanding, not direct patch generation or answer matching.

## Case Preparation

Each CodeRepoQA issue should become one evaluation case with these prepared artifacts:

- `raw/issue.json`: original CodeRepoQA issue data.
- `snapshots/repo-pre/`: repository checkout before the resolving change.
- `snapshots/repo-post/`: repository checkout after the resolving change.
- `prepared/initial-context.md`: visible initial package for the tool run.
- `prepared/hidden-resolution-dossier.md`: evaluator-only package built after the run.
- `run/`: model prompts, traces, responses, and policy logs.
- `evaluation/`: human or LLM-assisted comparison notes and scorecard.

The initial visible package should include only:

- Repository owner/name.
- Issue number and title.
- Issue creation date.
- Initial issue body.
- Pre-resolution repository snapshot metadata.

The hidden resolution dossier should include only evaluator-side material:

- Full issue discussion.
- Linked pull requests or commits.
- Post-resolution repository snapshot.
- Changed files and diff summary.
- Tests added or changed.
- Maintainer rationale and rejected alternatives.

Snapshot resolution should use this order:

1. Use `fixed_by` if present.
2. Use same-repository PRs or commits from `cite` / `cited_by`.
3. Search issue and PR references for the issue number and title keywords.
4. If no resolving artifact is found, use the latest commit before `created_at` as `repo-pre` and the latest commit before `closed_at` as `repo-post`, then mark case confidence lower.

## Stage-Aware Source Policy

The evaluation harness should pass a caller-controlled `SourcePolicy` into `V1PolicyEngine` for each run. The runtime should only know the allowed source categories; the harness owns temporal visibility and hidden-context rules.

Recommended Stage 1 policy for `EXPLAIN`:

```python
SourcePolicy(
    allowed_categories=(
        SourceCategory.ISSUE_TRACKER,
        SourceCategory.SOURCE_CODE,
    ),
    policy_name="coderepoqa_explain_initial",
)
```

This means the first tool run may use only the initial issue body and pre-resolution source code. It must not use later issue comments, linked PRs, diffs, or post-resolution files.

Later evaluator or reveal stages may use broader policies, for example:

```python
SourcePolicy(
    allowed_categories=(
        SourceCategory.ISSUE_TRACKER,
        SourceCategory.SOURCE_CODE,
        SourceCategory.DOCUMENTATION,
        SourceCategory.PULL_REQUEST,
    ),
    policy_name="coderepoqa_hidden_evaluator",
)
```

The harness should still enforce snapshot and visibility metadata separately from `SourceCategory`. Do not add CodeRepoQA-specific visibility enums to the current core until the evaluation harness proves the shape is stable.

## Retrieval And Indexing

Start with sparse retrieval over the initial issue body and pre-resolution repository text. BM25 is a good first implementation because historical code issues often depend on exact identifiers, keywords, diagnostics, and file names.

Add dense retrieval later for natural-language matching across issue prose, docs, and comments. Add reranking only after traces show systematic retrieval misses. A hybrid sparse plus dense pipeline with reranking is a later optimization, not a v1 requirement.

Every `EvidenceItem` returned by the evaluation retrieval service should include metadata like:

```json
{
  "case_id": "microsoft-TypeScript-6",
  "snapshot": "pre_resolution",
  "commit": "<sha>",
  "path": "src/compiler/checker.ts",
  "line_range": "Lx-Ly",
  "visibility": "visible_initial",
  "source_policy": "coderepoqa_explain_initial",
  "retrieval_reason": "Class instantiation checks are relevant to abstract class construction errors."
}
```

The retrieval log should record the query, source policy, ordered sources, selected evidence IDs, ranks, and snapshot metadata. This keeps the run replayable and makes future leakage checks possible.

## Model Providers

Define model configuration as data so university API models and local models can run through the same harness:

```json
{
  "provider": "university_api",
  "model": "<model-name>",
  "base_url": "<api-base-url>",
  "api_key_env": "UNIVERSITY_LLM_API_KEY",
  "temperature": 0,
  "max_tokens": 2000
}
```

Use these provider categories:

- `university_api`: remote models provided by the university API.
- `ollama`: local model serving for first local Gemma experiments.
- `llama_cpp`: later local serving when GGUF-level control, benchmarking, or lean deployment matters.
- `vllm`: later GPU serving when batching, throughput, or larger hosted local deployment matters.

For local Gemma, use Ollama first. Google documents direct Gemma support through Ollama, including Gemma 3 model tags such as `gemma3:4b`, and this is the fastest setup path for local experiments. Use `llama.cpp` later if you need direct GGUF control or lower-level benchmarking. Use `vLLM` only if the project needs serving throughput or GPU batching.

Keep decoding deterministic where supported:

- `temperature`: `0`
- fixed model identifier
- fixed prompt template version
- fixed retrieval index version
- logged token limits and provider settings

## Evaluation Runs And Scoring

Each run should store:

- Input prompt or structured `ConversationState`.
- `SourcePolicy` name and allowed categories.
- Retrieval plan and selected evidence.
- Prompt payload sent to the model.
- Response payload.
- Model provider settings.
- Policy violations.
- Final scorecard.

The scorecard should focus on guided explanation quality:

- Historical alignment: does the explanation path point toward the later maintainer/fix direction?
- Source-policy compliance: did the run avoid hidden future context?
- Evidence grounding: are claims tied to retrieved project artifacts?
- Uncertainty calibration: are confirmed facts separated from hypotheses?
- Architecture understanding: does it identify relevant subsystems?
- Issue-to-code linkage: does it connect issue requirements to concrete files or symbols?
- Non-solution behavior: does it avoid direct patch output?
- Guided learning quality: does it ask or prompt the developer to reason?
- Trace completeness: can the run be replayed from logs?

Use RAG metrics such as context precision, context recall, and faithfulness only as optional diagnostics. They are useful for retrieval quality, but they are not the primary success measure because this evaluation is about staged, evidence-grounded guidance.

## References

- Project NotebookLM guidance: scaffolded learning, deterministic orchestration, explicit source control, retrieval traces, and model settings.
- OpenAI trace grading: https://platform.openai.com/docs/guides/trace-grading
- OpenAI agent evals: https://platform.openai.com/docs/guides/agent-evals
- Google Gemma overview: https://ai.google.dev/gemma/docs/core
- Google Gemma with Ollama: https://ai.google.dev/gemma/docs/integrations/ollama
- llama.cpp: https://github.com/ggml-org/llama.cpp
- Ragas evaluation metrics: https://docs.ragas.io/en/v0.1.21/getstarted/evaluation.html
