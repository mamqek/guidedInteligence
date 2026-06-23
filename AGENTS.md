# Agent Notes

## Project NotebookLM

- NotebookLM URL: https://notebooklm.google.com/notebook/c0db0cf8-59bb-48f9-ba0c-bf33e62f518f
- Use this notebook as the persistent project knowledge source for this repository.
- Consult it when work requires project context, architectural intent, orchestration plans, or decisions that are not obvious from the local files.

## LLM Failure Policy

- Do not silently fall back from an LLM-backed stage to a deterministic surrogate.
- If a stage requires an LLM and no LLM configuration is available, fail immediately.
- If an LLM-backed stage fails at runtime, return an explicit error response or surface the failure directly; do not substitute a hardcoded explanation.

## Tool Rerun Requests

- If the user asks to rerun the tool, rerun the actual pipeline or serving command first.
- Do not substitute unit tests, fake servers, or isolated harness checks for a requested tool rerun.
- Use tests only as secondary verification after the real tool path has been exercised, or when the real tool path is unavailable and that limitation is stated explicitly.

## Run Configs And Commands

- Centralized run profiles live under `configs/`.
- Web UI profiles live under `configs/web-ui/` and are workspace config templates. Apply one before starting the server:
  - `npm run config:web:workspace`
  - `npm run config:web:codex`
  - `npm run config:web:codex:efficient`
  - `npm run config:web:codex:responsibility-complete`
  - `npm run retrieval:server`
- CodeRepoQA testing profiles live under `configs/testing/`. Use the npm scripts as the default run surface:
  - `npm run coderepoqa:evaluate:workspace -- --issue-json <case issue.json>`
  - `npm run coderepoqa:evaluate:codex -- --issue-json <case issue.json>`
  - `npm run coderepoqa:evaluate:codex:efficient -- --issue-json <case issue.json>`
  - `npm run coderepoqa:evaluate:codex:responsibility-complete -- --issue-json <case issue.json>`
  - `npm run coderepoqa:batch:workspace`
  - `npm run coderepoqa:batch:codex`
- Do not create a separate config file for every testcase. Keep reusable run policy in config files
  and pass testcase paths with `--issue-json`, unless a batch profile intentionally lists `cases`.
- Avoid reverting to long ad hoc CodeRepoQA commands with repeated `--retrieval-mode`, model, timeout,
  test-root, and shared-repo flags. Those CLI flags remain only as explicit overrides/debugging tools.
- Low-level `testing/codeRepoQA/run_case.py prepare-index` and `run-case` remain valid internal commands
  for prepared snapshots and focused debugging, but they are not the default benchmark interface.
- Codex prompt/schema contracts live under `services/retrieval/codex/profiles/<profile>/`; do not embed
  prompt variants or output schemas in `services/retrieval/codex/provider.py`. `efficient` is the default
  restored baseline, while `responsibility-complete` is the measured higher-cost quality experiment. Select
  them through
  `codex_prompt_profile` in testing configs or `retrieval.codex_prompt_profile` in web UI configs.

## Retrieval Pipeline Changes

- For non-trivial retrieval pipeline changes, document the implementation framework before or with the change:
  - intended stage boundary,
  - expected quality impact,
  - expected token impact,
  - known regression risks,
  - how results will be compared.
- After changing retrieval behavior, measure real retrieval tokens from actual pipeline runs and compare results against prior runs. Prefer at least two runs for the main benchmark case when runtime allows.
- Record run IDs, `coverage_status`, `sufficient`, retrieval token totals, and notable quality changes in the retrieval changelog or the relevant decision note.
- Do not leave a retrieval behavior change in place only because it reduces tokens. If two real-run comparisons show quality regression or unstable sufficiency, revert or disable the behavior and document the failed experiment.
