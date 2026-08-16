# Agent Notes

## Project NotebookLM

- NotebookLM URL: https://notebooklm.google.com/notebook/c0db0cf8-59bb-48f9-ba0c-bf33e62f518f
- Use this notebook as the persistent project knowledge source for this repository.
- Consult it when work requires project context, architectural intent, orchestration plans, or decisions that are not obvious from the local files.

## LLM Failure Policy

- Do not silently fall back from an LLM-backed stage to a deterministic surrogate.
- If a stage requires an LLM and no LLM configuration is available, fail immediately.
- If an LLM-backed stage fails at runtime, return an explicit error response or surface the failure directly; do not substitute a hardcoded explanation.
- Do not keep legacy fallback behavior beside a replacement implementation unless the user explicitly asks for a compatibility path. Hidden fallback branches make debugging ambiguous and leave the code harder to reason about; replace the old path cleanly.

## Tool Rerun Requests

- If the user asks to rerun the tool, rerun the actual pipeline or serving command first.
- Do not substitute unit tests, fake servers, or isolated harness checks for a requested tool rerun.
- Use tests only as secondary verification after the real tool path has been exercised, or when the real tool path is unavailable and that limitation is stated explicitly.

## Dependency Manifest Maintenance

- Keep `requirements.txt` limited to direct Python packages imported by maintained project code.
- If a Python change adds a new third-party import, update `requirements.txt` in the same change.
- Do not add standard-library modules, transitive dependencies, temporary spike dependencies, or generated scratch-file dependencies to `requirements.txt`.
- Prefer removing unused package entries over preserving stale dependencies.

## Local Setup Scripts

- Fresh-clone setup scripts live in `scripts/` and are the default install surface for agents and humans:
  - Windows PowerShell: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1`
  - Linux/macOS Bash: `bash scripts/setup.sh`
- Manual web testing scripts start Qdrant, the retrieval backend, and the Vite frontend:
  - Windows PowerShell: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-dev.ps1`
  - Linux/macOS Bash: `bash scripts/run-dev.sh`
- Manual web testing defaults to backend port `8790` and frontend port `5173`; use `--backend-port <port>` and `--frontend-port <port>` when those ports are already occupied.
- The npm aliases expose the same flows:
  - Cross-platform aliases: `npm run setup`, `npm run dev:all`
  - Explicit aliases: `npm run setup:ps`, `npm run dev:all:ps`, `npm run setup:bash`, `npm run dev:all:bash`
- Setup scripts install Node packages with `npm ci`, create a repository-local `.venv`, install `requirements.txt`, copy `.env.example` to `.env` only when missing, apply `configs/web-ui/workspace.json`, and optionally pull the Qdrant Docker image.
- Do not add codec installation or codec checks to these scripts.

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

## Retrieval Experiment Run Policy

- Start retrieval-behavior experiments with focused tests, then use optional cheap smoke runs through the
  actual pipeline while debugging. A smoke run may pass both `--skip-response-generation` and
  `--skip-final-evidence-selection` to inspect retrieval, qualification, controller behavior, and the
  preselection candidate pool without paying for later LLM stages.
- Smoke runs are diagnostic only. They do not produce a valid final-evidence, `coverage_status`, or
  `sufficient` comparison and must not be counted as acceptance runs or substituted for the requested real
  pipeline verification.
- Final retrieval acceptance requires at least two actual-pipeline runs for the main benchmark case when
  runtime allows. Pass `--skip-response-generation` so explanation prose is not generated, but keep final
  evidence selection enabled by omitting `--skip-final-evidence-selection`. A retrieval change can alter the
  candidates and payload received by final selection even when it does not modify the selector itself.
- Generate the final explanation only when the experiment explicitly tests response or explanation quality.
  Otherwise, explanation-generation tokens are out of scope and should not be spent.
- Use the npm evaluation surface for both smoke and acceptance runs:
  - Diagnostic smoke: `npm run coderepoqa:evaluate:workspace -- --issue-json <case issue.json> --skip-response-generation --skip-final-evidence-selection`
  - Acceptance: `npm run coderepoqa:evaluate:workspace -- --issue-json <case issue.json> --skip-response-generation`
- Keep the model, prompts, index scope, reusable run config, and unrelated retrieval settings fixed between
  baseline and variant runs. Clearly label diagnostic artifacts so they cannot be mistaken for measured
  comparisons.

## CodeRepoQA Index Scope

- Before indexing a testcase snapshot, inspect that repository's layout and exclude directories that are
  deterministically generated, vendored, cached, or compiled and cannot contain useful issue evidence.
- Keep repository-aware exclusions explicit in the CodeRepoQA harness so the BM25, embedding/Qdrant, and
  CodeGraph indexes all receive the same paths. Record the effective list in run metadata.
- Do not infer exclusions from the hidden oracle or remove authored implementation/test sources merely to
  reduce cost. For example, TypeScript's generated `tests/baselines/reference` output is excluded, while
  authored `tests/cases` inputs and the standard-library declarations in `lib` remain searchable. Generated
  TypeScript JavaScript bundles such as `lib/typescript.js` are excluded individually rather than excluding
  the entire mixed-source `lib` directory.
- Treat any exclusion-policy change as an intentional index-signature change. Announce that the old index is
  stale before rebuilding; never silently re-index it.

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
