# Codex Retrieval Prompt Profiles

Each profile owns the complete contract sent to `codex exec`:

- `prompt.md` contains retrieval instructions and exactly one `{{USER_PROMPT}}` placeholder.
- `evidence.schema.json` defines the strict JSON output accepted from Codex.

Available profiles:

- `efficient`: the original compact contract used before the 2026-06-23 responsibility-complete experiment. This is the default.
- `responsibility-complete`: the quality-oriented experimental contract that asks Codex to classify evidence roles and report coverage gaps. It produced better owner-file targeting but substantially higher token use and latency in the measured batch.

Select a profile through `codex_prompt_profile` in a testing config or `retrieval.codex_prompt_profile` in a web UI config. Do not embed prompt or schema variants in Python or testcase-specific configs.
