# LocAgent Comparison

## Scope

This note compares the current step-2 design in this repository with the closest equivalent in LocAgent.

The comparison is based on the LocAgent source code:

- `C:\Programming\LocAgentRepo\auto_search_main.py`
- `C:\Programming\LocAgentRepo\util\prompts\pipelines\auto_search_prompt.py`
- `C:\Programming\LocAgentRepo\util\runtime\function_calling.py`
- `C:\Programming\LocAgentRepo\util\runtime\content_tools.py`
- `C:\Programming\LocAgentRepo\util\runtime\structure_tools.py`
- `C:\Programming\LocAgentRepo\plugins\location_tools\repo_ops\repo_ops.py`

## Summary

The current system now follows the same general direction that LocAgent takes in one important way:

- the model should start retrieval planning quickly
- structural search should be driven by grounded repo evidence
- lexical expansion is allowed to be broader than graph expansion

The remaining difference is that this repository still keeps a more explicit step-2 planning object, while LocAgent folds more of that reasoning directly into the prompt and tool loop.

## Current Step 2

Current step 2 now does this:

1. deterministic prompt extraction
2. LLM grounded planning
3. explicit retrieval plan creation

The resulting plan keeps these concerns separate:

- grounded prompt evidence
- LLM concept expansion
- speculative entities
- role-directed subqueries
- source priorities
- negative filters

That is stricter than the old merged intent model and closer to what we want operationally.

## LocAgent Equivalent

LocAgent does not build an explicit structured planning object like our current `WorkspaceRetrievalPlan`.

Instead:

- `get_task_instruction(...)` builds one task-focused issue-localization prompt
- `run_localize(...)` appends that prompt as the active user task
- tools are enabled immediately:
  - `search_code_snippets`
  - `get_entity_contents`
  - `explore_tree_structure`

So LocAgent effectively does:

- prompt-level decomposition
- immediate search/tool use
- graph/entity lookup before lexical fallback

It does not spend a separate phase producing a formal planning object first.

## Important Similarity

The important similarity now is this:

- lexical expansion may be broader
- structural traversal must stay grounded

That is already the direction of the current refactor here:

- speculative entities can drive lexical retrieval
- only confirmed repo symbols can become graph anchors

This is the most valuable LocAgent-like behavior to preserve.

## What We Already Cut From the Old System

Compared with the old step-2 design in this repository, the current refactor already removed or demoted:

- the initial LLM sufficiency gate
- the merged `entities / subqueries / file_hints` intent contract
- heuristic single-shot CGC query shaping from that merged object
- the assumption that LLM-produced names are immediately safe graph anchors

So the current system is already materially closer to the LocAgent direction than the old one was.

## What Still Differs From LocAgent

The current system still keeps functionality that LocAgent does not emphasize in the same way:

- an explicit typed planning object
- explicit role policy:
  - required roles
  - supporting roles
- explicit negative filters
- a more visible distinction between:
  - deterministic grounding
  - LLM expansion
  - refinement-stage graph anchoring

That means we are not copying LocAgent literally.

We are keeping more structure in step 2 because it makes the grounded/speculative split enforceable in code.

## Functionality We Intentionally Keep

Even while leaning toward LocAgent's approach, we still intentionally keep:

- typed step-2 plan data
- structured-output planning schema
- request/response logging
- bounded refinement rounds
- explicit tool validation
- explicit rule that speculative entities are lexical-only until grounded

These are not leftovers from the old merged-intent system.

They are deliberate guardrails around the new design.

## Practical Difference In One Sentence

LocAgent mostly says:

- analyze the issue and start searching immediately with graph-aware tools

The current system says:

- extract grounded evidence first, then let the LLM expand retrieval, but do not allow it to invent graph anchors

## Bottom Line

The repository is no longer following the old merged-intent step-2 model.

It now leans toward the useful part of the LocAgent approach:

- early issue analysis
- graph-aware retrieval
- structural traversal from grounded anchors

while still keeping stronger explicit contracts around:

- grounded vs speculative planning
- role-directed retrieval
- enforcement in code rather than prompt alone
