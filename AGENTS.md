# Agent Notes

## Project NotebookLM

- NotebookLM URL: https://notebooklm.google.com/notebook/c0db0cf8-59bb-48f9-ba0c-bf33e62f518f
- Use this notebook as the persistent project knowledge source for this repository.
- Consult it when work requires project context, architectural intent, orchestration plans, or decisions that are not obvious from the local files.

## LLM Failure Policy

- Do not silently fall back from an LLM-backed stage to a deterministic surrogate.
- If a stage requires an LLM and no LLM configuration is available, fail immediately.
- If an LLM-backed stage fails at runtime, return an explicit error response or surface the failure directly; do not substitute a hardcoded explanation.
