# Workspace Retrieval Step2 Source-Grounded Planner Design

## Purpose

This note defines the future `step2` planner contract for workspace retrieval. It focuses on better initial role/objective selection for narrow bug reports and related repository questions. It is a design document only; it does not implement code.

The central change is to replace the current universal role list with an intent-specific evidence contract:

```text
request intent + specificity
  -> active evidence objectives
  -> deferred evidence objectives
  -> preferred structural relations
  -> stop contract
  -> constrained expansion policy
```

`step2` should decide what evidence is needed first. `stage.py` should execute retrieval rounds and decide whether the evidence satisfies the contract.

## Source Status

This document is based on full-text review of the following papers, not abstracts:

| Paper | Full-text source used | Used for |
|---|---|---|
| Jonathan Sillito, Gail C. Murphy, Kris De Volder, "Questions Programmers Ask During Software Evolution Tasks" | Semantic Scholar PDF mirror of FSE 2006 paper | focus-point progression, subgraph/group evidence objectives |
| Andrew J. Ko, Robert DeLine, Gina Venolia, "Information Needs in Collocated Software Development Teams" | Microsoft Research PDF | broad developer information needs, bug triage/repro/behavior/rationale needs |
| Thomas D. LaToza, Brad A. Myers, "Developers Ask Reachability Questions" | GMU author PDF | control-flow/reachability objectives and path-based expansion |
| Caitlin Sadowski, Kathryn T. Stolee, Sebastian Elbaum, "How Developers Search for Code: A Case Study" | Google Research PDF | scoped search, API/usage intent, query reformulation |
| Jian Zhou, Hongyu Zhang, David Lo, "Where Should the Bugs Be Fixed? More Accurate Information Retrieval-Based Bug Localization Based on Bug Reports" | SMU author/institutional PDF | bug reports as queries, owner-file ranking |
| Ripon K. Saha, Matthew Lease, Sarfraz Khurshid, Dewayne E. Perry, "Improving Bug Localization using Structured Information Retrieval" | author PDF | structured code fields and source-code-aware bug localization |
| Thomas Fritz, Gail C. Murphy, "Using Information Fragments to Answer the Questions Developers Ask" | UBC author PDF | heterogeneous evidence kinds and composition |
| Sonia Haiduc, Gabriele Bavota, Andrian Marcus, Rocco Oliveto, Andrea De Lucia, Tim Menzies, "Automatic Query Reformulations for Text Retrieval in Software Engineering" | USI author PDF | query-specific expansion/reduction policies |
| Fengji Zhang et al., "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation" | ACL Anthology PDF | bounded iterative retrieval from repository context |

NotebookLM MCP is authenticated and can see the 19 uploaded sources, but during this pass its `ask_question` endpoint repeatedly returned the earlier access-check response instead of answering new questions. The design below therefore uses directly extracted full-text PDFs from accessible paper sources.

### Full-Text Evidence Used

| Paper | Concrete finding used in this design |
|---|---|
| Sillito, Murphy, and De Volder, "Questions Programmers Ask During Software Evolution Tasks" | The paper organizes 44 programmer question types into finding initial focus points, building on focus points, understanding subgraphs, and questions over groups of subgraphs. This supports starting from a focused owner/objective and expanding into relations only when needed. |
| Ko, DeLine, and Venolia, "Information Needs in Collocated Software Development Teams" | The study observed developers needing information for writing code, bug triage, reproducing failures, expected behavior, design/program behavior, and causes of program state. This supports intent labels and stop contracts rather than one universal role list. |
| LaToza and Myers, "Developers Ask Reachability Questions" | The paper defines reachability questions as searches over feasible paths to target statements and reports these questions as common and time-consuming. This supports `behavior_path`, `dependent_callers`, and relation-based expansion. |
| Sadowski, Stolee, and Elbaum, "How Developers Search for Code: A Case Study" | The study found frequent scoped searches, API/example searches, query reformulation, and use of path scoping. This supports intent-specific first-pass objectives and query-specific expansion/reduction. |
| Zhou, Zhang, and Lo, "Where Should the Bugs Be Fixed? More Accurate Information Retrieval-Based Bug Localization Based on Bug Reports" | Bug reports are treated as queries over source files, with the goal of ranking likely files to fix. This supports first-class `implementation_owner` for defect localization. |
| Saha, Lease, Khurshid, and Perry, "Improving Bug Localization Using Structured Information Retrieval" | BLUiR separates class, method, variable, and comment fields and shows structured source information improves bug localization. This supports structured owner discovery instead of flat whole-file role matching. |
| Fritz and Murphy, "Using Information Fragments to Answer the Questions Developers Ask" | Developer questions often require composing multiple information domains, including source code, changes, work items, comments, stack traces, and test cases. This supports artifact promotion only when the active stop contract needs that evidence. |
| Haiduc et al., "Automatic Query Reformulations for Text Retrieval in Software Engineering" | Query performance depends on query quality; short/vague and verbose/noisy queries require different reformulation strategies. This supports specificity-driven expansion and reduction. |
| Zhang et al., "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation" | Repository context can be improved by iterative retrieval using context discovered in prior iterations. This supports bounded adaptive rounds in `stage.py`, while keeping Step2 as the policy source for allowed transitions. |

## Problem With Current Step2

Current `step2` emits the same required roles for every workspace retrieval plan:

```text
representation
input_parsing
validation_checking
diagnostics
behavior_output
```

and the same supporting roles:

```text
tests
docs
config
```

This is too broad for narrow bug reports and too flat for relational questions. The paper evidence points to three issues:

| Issue | Evidence | Planner consequence |
|---|---|---|
| Developers often start from a focus point and then build outward into relations/subgraphs. | Sillito et al. classify programmer questions into finding initial focus points, building on focus points, understanding subgraphs, and comparing groups of subgraphs. | Step2 should choose a small initial objective set, then defer broader relation objectives until the owner/focus point is weak or incomplete. |
| Many real questions are about behavior, cause, expected behavior, design intent, program state, and reproduction, not just generic code buckets. | Ko et al. observed 21 information types across writing code, bug triage, reproducing failures, debugging, and design; they note deferred searches for design and program behavior, including why code was written, expected behavior, and causes of program state. | Step2 needs intent labels and stop contracts, not only role buckets. |
| Bug localization is explicitly an owner-file ranking problem, and structured code fields matter. | BugLocator treats bug reports as queries over source files and ranks likely files to fix; BLUiR shows class/method/variable/comment structure improves localization over flat text. | For defect localization, Step2 should prioritize `implementation_owner` and structured code-field matching before docs/config/support artifacts. |

## Step2 Output Contract

Future `WorkspaceRetrievalPlan` should carry this structured planner section:

```json
{
  "primary_intent": "defect_localization",
  "secondary_intents": ["behavior_explanation"],
  "specificity": "narrow",
  "active_objectives": ["implementation_owner", "diagnostic_surface", "verification_repro"],
  "deferred_objectives": ["behavior_path", "configuration_context", "usage_contract"],
  "preferred_relations": ["implemented_by", "emits", "tested_by"],
  "artifact_filters": {
    "prefer": ["production_source", "test_or_reproducer"],
    "defer": ["documentation", "configuration"]
  },
  "stop_contract": {
    "required": ["credible_owner", "symptom_owner_connection"],
    "one_of": ["native_reproducer", "diagnostic_or_observable_behavior"]
  },
  "expansion_policy": {
    "on_missing_owner": ["broaden_structured_code_fields", "follow_nearest_references"],
    "on_missing_causal_path": ["promote:behavior_path"],
    "on_missing_expected_behavior": ["promote:verification_repro", "promote:usage_contract"],
    "on_low_query_specificity": ["reduce_noise_terms", "keep_owner_objective_active"]
  }
}
```

This is a planning contract. It should not retrieve files itself.

### Compatibility Boundary

The first implementation should not delete the current five required roles or the three supporting roles. It should change what they mean operationally:

```text
Step2 source-grounded planner language:
  intent -> objectives -> relations -> artifact filters -> stop contract

Temporary execution compatibility:
  objectives -> legacy role aliases -> existing candidate/retrieval/refinement machinery
```

This keeps the rewrite general and avoids hardcoding repository-specific directory names. The initial behavior change should be limited to the order and activation of objectives:

| New objective decision | Temporary legacy execution |
|---|---|
| `implementation_owner` active first | Search owner-bearing production artifacts through structured code fields, then map selected evidence into whichever old role best explains the owner. |
| `behavior_path` deferred or active | Use existing graph/reference expansion and role refinement to collect path evidence; do not force all five roles to be strong first. |
| `verification_repro` promoted | Search tests/reproducers as evidence only when the prompt or stop contract calls for them. |
| `usage_contract` promoted | Search docs/examples/call sites when expected behavior or API usage remains unresolved. |
| `configuration_context` promoted | Search config/loaders/consumers when runtime settings are part of the request or path evidence points there. |

The source basis is the same as the planner rules below: BugLocator and BLUiR support owner-first localization; Sillito et al. and LaToza and Myers support relational/path objectives; Ko et al. and Fritz and Murphy support promoting tests/docs/config as needed evidence domains; Sadowski et al. and Haiduc et al. support scoped search and query-specific reformulation.

## Intent Classifier

Step2 should classify the request with a multi-label intent model. The intent controls first-pass objectives and stop criteria.

| Intent | User signal | First-pass objectives | Deferred objectives | Source basis |
|---|---|---|---|---|
| `defect_localization` | Bug, failure, regression, wrong output, stack/error symptom, failing test described by the user | `implementation_owner`, `diagnostic_surface` when an error/warning/output symptom exists, `verification_repro` when the prompt includes native repro/test evidence | `behavior_path`, `configuration_context`, `usage_contract` | BugLocator; BLUiR; Ko et al. |
| `api_or_usage_lookup` | "How do I use/call/configure this API?", examples, parameters, integration | `interface_entry`, `usage_contract`, `example_usage` | `implementation_owner`, `verification_repro` | Sadowski et al.; Ko et al. |
| `behavior_explanation` | "Why/how does this happen?", "what does this do?", "where does this value/state come from?" | `interface_entry`, `behavior_path`, `data_state`, `effects_output` | `constraints_validation`, `diagnostic_surface`, `configuration_context` | LaToza and Myers; Sillito et al.; Ko et al. |
| `change_or_impact_planning` | "Where should I change/add/refactor?", "what depends on this?", side effects | `implementation_owner`, `behavior_path`, `dependent_callers`, `verification_repro` | `configuration_context`, `usage_contract`, `diagnostic_surface` | Sillito et al.; LaToza and Myers; Sadowski et al. |
| `repository_exploration` | Architecture, subsystem boundaries, "where is X handled?", broad unfamiliar codebase exploration | `subsystem_owner`, `interface_entry`, `dependency_structure` | `usage_contract`, `verification_repro`, `configuration_context` | Sillito et al.; Ko et al.; Fritz and Murphy |
| `configuration_runtime` | Config option, defaults, environment, feature flags, runtime setup | `configuration_context`, `interface_entry`, `behavior_path`, `effects_output` | `diagnostic_surface`, `verification_repro` | Ko et al.; LaToza and Myers; Fritz and Murphy |
| `verification_analysis` | Tests, reproducers, fixtures, assertions, "how is this tested?" | `verification_repro`, `implementation_owner`, `behavior_path` | `configuration_context`, `diagnostic_surface` | Ko et al.; Fritz and Murphy; LaToza and Myers |

### Specificity Labels

Step2 should also classify request specificity:

| Specificity | Meaning | Planner behavior | Source basis |
|---|---|---|---|
| `narrow` | The request names a concrete symptom, API, behavior, symbol, user-visible output, or reproducible scenario. | Start with 2-3 active objectives and defer support artifacts. Stop once owner plus symptom connection is credible. | Sillito et al. focus-point model; Sadowski et al. targeted/scoped searches; BugLocator owner-file ranking. |
| `medium` | The request describes a behavior area but not an exact owner or path. | Start with owner plus one relational objective. Keep one controlled support objective available. | Sillito et al. building on focus points; LaToza and Myers reachability search. |
| `broad` | The request is architectural/exploratory or asks for overall understanding. | Start with subsystem/interface/dependency objectives. Do not pretend owner-file sufficiency is enough. | Sillito et al. subgraphs/groups of subgraphs; Fritz and Murphy multi-domain questions. |

## Evidence Objective Vocabulary

Step2 should emit objectives, not the current hardcoded role buckets.

| Objective | Meaning | Current role replacement | Source basis |
|---|---|---|---|
| `implementation_owner` | The source artifact most likely to own the behavior or bug fix. | New objective; not equivalent to any one current role. | BugLocator; BLUiR. |
| `interface_entry` | Public API, handler, command, lifecycle hook, parser entry, callback, or external trigger. | Partly `input_parsing`, partly `behavior_output`. | Sadowski et al.; Ko et al. |
| `behavior_path` | Calls, dispatch, events, data/control reachability, and causal path between trigger and effect. | New objective replacing implicit broad role coverage. | LaToza and Myers; Sillito et al. |
| `data_state` | Data structures, models, fields, state transitions, mutations. | Refines `representation`. | LaToza and Myers; Sillito et al. |
| `constraints_validation` | Guards, invariants, semantic checks, defaults, and rejection paths. | Refines `validation_checking`. | Sillito et al.; Ko et al. |
| `effects_output` | Return values, rendered output, emitted events, persistence, side effects. | Refines `behavior_output`. | LaToza and Myers; Sadowski et al. |
| `diagnostic_surface` | Error messages, logs, warnings, stack traces, and observable failure surfaces. | Refines `diagnostics`. | Ko et al.; Fritz and Murphy. |
| `verification_repro` | Tests, fixtures, assertions, repro programs, and native reproduction steps from the user/request. | Replaces artifact-only `tests`. | Ko et al.; Fritz and Murphy. |
| `configuration_context` | Config definitions, defaults, loaders, consumers, and runtime setup. | Replaces artifact-only `config`. | Ko et al.; LaToza and Myers. |
| `usage_contract` | Docs, examples, call sites, API expectations, compatibility behavior. | Replaces artifact-only `docs`. | Sadowski et al.; Fritz and Murphy. |
| `example_usage` | Minimal examples/call sites showing how an API is used. | A specialization of `usage_contract`. | Sadowski et al. |
| `dependent_callers` | Callers, references, downstream/upstream dependencies, impact surface. | Part of `behavior_path`, but important enough for change planning. | LaToza and Myers; Sillito et al. |
| `subsystem_owner` | Representative files that define subsystem boundaries and responsibility. | New objective for broad exploration. | Sillito et al.; Ko et al. |

## Planner Rules

Every rule below is intended to be general. None depends on hardcoded directory names.

| Rule | Planner decision | Source basis |
|---|---|---|
| R1: Owner first for defect localization | If `primary_intent=defect_localization`, activate `implementation_owner` in round 1 and require `credible_owner` in the stop contract. | BugLocator frames bug localization as ranking source files to fix from a bug report; BLUiR shows structured source fields improve candidate ranking. |
| R2: Support artifacts are deferred for narrow bugs | For `narrow defect_localization`, put docs/config in deferred objectives unless the user request itself is about docs/config or runtime setup. | Sadowski et al. show searches are often scoped and targeted; Sillito et al. show developers start with focus points before broader subgraphs; BugLocator/BLUiR focus first on relevant source files. |
| R3: Tests are evidence, not a role bucket | Treat tests/reproducers as `verification_repro`; activate them only when the prompt asks for verification, includes native repro/test evidence, or expected behavior is ambiguous. | Ko et al. discuss reproducing failures and bug triage as information needs; Fritz and Murphy include test cases as one domain among several composable information fragments. |
| R4: Behavior questions require paths, not just files | If the request asks "why/how/what path/what causes", activate `behavior_path` and relations such as `calls`, `emits`, `reads`, `writes`, `configures`, or `tested_by`. | LaToza and Myers define reachability questions as searches over feasible program paths; Sillito et al. include subgraph and group-of-subgraph questions. |
| R5: API/usage intent starts with contracts/examples | If the request asks how to use an API or integrate behavior, activate `interface_entry`, `usage_contract`, and `example_usage`; defer implementation unless usage evidence is insufficient. | Sadowski et al. found API/example search was the largest category in their survey responses; Ko et al. observed developers using API documentation and example code. |
| R6: Query specificity controls expansion/reduction | If a query is very short or vague, expand only within the active objective; if verbose/noisy, reduce to discriminative symptom/API/behavior terms before broadening objectives. | Haiduc et al. show query performance depends on query properties and that single-term and verbose queries need different reformulation strategies. |
| R7: Structured code fields should guide owner discovery | For owner discovery, prefer matches in structured code fields such as class/type, method/function, variable/field, and comments/docstrings over flat whole-file matching. | BLUiR explicitly models class, method, variable, and comment fields; Saha et al. show these fields appear in bug reports and improve localization. |
| R8: Multi-domain evidence is composed only when needed | Do not retrieve every artifact kind up front. Promote documentation, config, history, stack traces, or tests only when the active stop contract cannot be satisfied from owner/path evidence. | Fritz and Murphy show many questions require composing different information domains, but the model lets the user specify what to integrate rather than manually traversing everything. |
| R9: Iteration is bounded and evidence-driven | Step2 should emit expansion conditions; stage should run additional rounds only when evidence is weak, contradictory, or missing a required stop-contract component. | RepoCoder shows iterative retrieval can bridge a gap between initial retrieval context and target; Haiduc et al. and Sadowski et al. support reformulation based on result/query state. |
| R10: Do not use verification-only issue comments as retrieval anchors | Use only native request content and allowed repository artifacts. Keep benchmark verification comments out of retrieval seeding. | This is a project validity rule, not paper-derived. It preserves native retrieval conditions and avoids leakage from benchmark verification material. |

## Intent-To-Objective Mapping

Step2 should choose active and deferred objectives as follows.

| Intent and specificity | Active objectives | Deferred objectives | Stop contract |
|---|---|---|---|
| `defect_localization:narrow` | `implementation_owner`; `diagnostic_surface` if an error/output symptom exists; `verification_repro` if native repro/test evidence exists | `behavior_path`; `configuration_context`; `usage_contract` | `credible_owner` and `symptom_owner_connection`; plus one observable symptom, diagnostic, or native repro link |
| `defect_localization:medium` | `implementation_owner`; `behavior_path`; one of `diagnostic_surface` or `verification_repro` | `configuration_context`; `usage_contract`; `dependent_callers` | owner plus supported cause/effect path or bounded explanation of missing path |
| `api_or_usage_lookup:any` | `interface_entry`; `usage_contract`; `example_usage` | `implementation_owner`; `verification_repro`; `configuration_context` | callable contract plus one grounded usage example |
| `behavior_explanation:narrow_or_medium` | `interface_entry`; `behavior_path`; `effects_output`; optionally `data_state` | `constraints_validation`; `diagnostic_surface`; `configuration_context` | path from trigger/entry to externally visible behavior |
| `change_or_impact_planning:any` | `implementation_owner`; `behavior_path`; `dependent_callers`; `verification_repro` | `configuration_context`; `usage_contract`; `diagnostic_surface` | owner plus bounded impact surface and at least one validation path |
| `repository_exploration:broad` | `subsystem_owner`; `interface_entry`; `dependency_structure` | `usage_contract`; `verification_repro`; `configuration_context` | coherent subsystem map with explicit boundary evidence |
| `configuration_runtime:any` | `configuration_context`; `interface_entry`; `behavior_path`; `effects_output` | `diagnostic_surface`; `verification_repro` | setting/default/loader-to-consumer-to-effect chain |
| `verification_analysis:any` | `verification_repro`; `implementation_owner`; `behavior_path` | `configuration_context`; `diagnostic_surface`; `usage_contract` | assertion/repro linked to implementation behavior |

## Expansion Policy

Step2 should not directly loop. It should emit allowed transitions for `stage.py`.

| Evidence state after a retrieval round | Allowed transition | Source basis |
|---|---|---|
| No credible owner found for a defect | Broaden structured owner discovery across class/function/variable/comment fields; keep support artifacts deferred. | BLUiR; BugLocator. |
| Owner found but symptom connection missing | Promote `behavior_path` and traverse nearest structural relations from the owner. | LaToza and Myers; Sillito et al. |
| Path found but expected behavior unclear | Promote `verification_repro` or `usage_contract`, depending on whether the request is test/repro-like or API/usage-like. | Ko et al.; Sadowski et al.; Fritz and Murphy. |
| Path is dominated by config/runtime ambiguity | Promote `configuration_context` and require loader/consumer/effect evidence. | Ko et al.; LaToza and Myers. |
| Query has too many generic terms or noisy prose | Apply query reduction to discriminative terms while preserving active objectives. | Haiduc et al. |
| Query is too short or lacks owner candidates | Apply query expansion within the same active objective before adding new objectives. | Haiduc et al.; Sadowski et al. |
| Broad/exploration request keeps finding isolated files | Promote `dependency_structure` or `subsystem_owner`, not docs/config by default. | Sillito et al.; Fritz and Murphy. |
| Marginal evidence gain is low after a promoted objective | Stop with explicit partial status instead of retrieving all remaining objectives. | Sadowski et al. short focused sessions; RepoCoder bounded iterative retrieval evidence. |

## Step2 Schema Changes

Add these fields to the planner output schema:

```json
{
  "primary_intent": "defect_localization",
  "secondary_intents": ["behavior_explanation"],
  "specificity": "narrow",
  "active_objectives": [],
  "deferred_objectives": [],
  "preferred_relations": [],
  "artifact_filters": {
    "prefer": [],
    "allow": [],
    "defer": []
  },
  "stop_contract": {
    "required": [],
    "one_of": [],
    "sufficient_when": ""
  },
  "expansion_policy": {}
}
```

Keep compatibility aliases from old roles during migration:

| Old role | Compatibility objective |
|---|---|
| `representation` | `data_state` |
| `input_parsing` | `interface_entry` |
| `validation_checking` | `constraints_validation` |
| `diagnostics` | `diagnostic_surface` |
| `behavior_output` | `effects_output` |
| `tests` | `verification_repro` artifact kind |
| `docs` | `usage_contract` artifact kind |
| `config` | `configuration_context` artifact kind |

## Migration Plan

1. Add intent/objective metadata to Step2 output without changing retrieval behavior.
2. Log the selected intent, specificity, active objectives, deferred objectives, and stop contract for each benchmark run.
3. Add compatibility mapping from old roles to new objectives.
4. Enable objective-narrowing for `defect_localization:narrow` only.
5. Compare against current workspace retrieval on at least the batch-2 cases and one prior batch where workspace was competitive.
6. Record run IDs, `coverage_status`, `sufficient`, retrieval tokens, owner-file rank/recall, and noise share.
7. Expand to API/usage and behavior-explanation intents only after defect localization shows stable quality.

## Implementation Attempt Log

### 2026-06-24 Step1-Step3 partial implementation

Implemented:

- Step2 planner metadata fields for `primary_intent`, `secondary_intents`, `specificity`, `active_objectives`, `deferred_objectives`, `preferred_relations`, `stop_contract`, `expansion_policy`, and deterministic `prompt_signal_flags`.
- Deterministic normalization for narrow defect plans so diagnostic/repro/config objectives are active only when supported by native prompt signals.
- A gated Step3 behavior flag, `objective_role_selection_enabled`, threaded through the CodeRepoQA workspace run config.
- Narrow defect objective-to-legacy-role mapping:
  - `implementation_owner` maps to first-pass `behavior_output` and `validation_checking`.
  - `verification_repro`, `configuration_context`, and `usage_contract` map to deferred support roles `tests`, `config`, and `docs`.
- `configs/testing/workspace.json` enables the gated Step3 path for workspace evaluation runs.

Verification completed:

- `.venv\Scripts\python.exe -m py_compile` passed for the edited Step2, stage, config, run-case, and test files before the local Python launcher became unusable for new direct invocations.
- `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives` passed with 4 tests.
- `.venv\Scripts\python.exe -m unittest tests.test_coderepoqa_retrieval` passed with 8 tests.

Known unrelated/pre-existing test issue:

- `.venv\Scripts\python.exe -m unittest tests.test_workspace_retrieval` failed in 17 tests that patch `services.retrieval.tools.cgc`; the package currently raises `AttributeError: tools` through `services.retrieval.__getattr__`. These failures were not caused by the objective planner fields but still need separate cleanup if the full workspace test suite is required as a gate.

Blocked verification:

- Requested real vue Step3 run could not be completed in this turn because local Python launchers are broken:
  - `npm run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json` failed because PowerShell blocked `npm.ps1`.
  - `npm.cmd run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json` reached the package script but failed on the script's `python` command with `The system cannot execute the specified program`.
  - `.venv\Scripts\python.exe testing/codeRepoQA/run_case.py evaluate-case ...` and `.venv\Scripts\python.exe -m testing.codeRepoQA.run_case evaluate-case ...` failed because `.venv\pyvenv.cfg` points to the missing WindowsApps Python target `C:\Users\mukha\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe`.
  - Alternate discovered Python environments either pointed to missing WindowsApps Python 3.10 launchers or lacked required project dependencies such as `langgraph`.

Next retry should first restore or recreate the repo `.venv` from a real Python installation, then rerun:

```powershell
npm.cmd run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json
```

Compare the new run against baseline `testing/codeRepoQA/batch-runs/002-20260623T102552Z/vuejs-vue-10803/workspace/run-20260623T112023Z`, which had elapsed time `408.270416`, `overlap_count=1`, oracle owner file `src/platforms/web/server/modules/dom-props.js` at rank 2, and the old universal required roles.

### 2026-06-24 runtime retry

Attempted to unblock the real vue Step3 run without changing retrieval logic:

- Rechecked `.venv\pyvenv.cfg`; it still points to missing WindowsApps Python 3.11 target.
- Checked common Python install paths under `C:\Python*`, `C:\Program Files\Python*`, and `C:\Users\mukha\AppData\Local\Programs\Python\Python*`; no usable Python install was present.
- Tried running the pipeline with Android NDK Python plus `.venv\Lib\site-packages` on `PYTHONPATH`; it failed importing `ssl` because that Python lacks `_ssl`.
- Checked for Conda/Mamba/Micromamba; none were installed.
- Requested and received approval to run `winget install --id Python.Python.3.11 --source winget --accept-package-agreements --accept-source-agreements`.
- First `winget install` attempt timed out after 2 minutes.
- Second `winget install` attempt timed out after 5 minutes.
- After timeout, `winget` and `python-3.11.9-amd64.exe` installer processes were still running from temp, but no usable Python executable appeared in common install locations.

Status: real vue run remains blocked by local Python runtime repair. The retrieval implementation remains in place and gated. Do not revert it solely because the environment cannot currently launch the pipeline.

### 2026-06-24 final runtime check

Checked the environment again after the prior timeout:

- `winget.exe` and two `python-3.11.9-amd64.exe` installer processes were still running from temp.
- `python` still resolves only to the broken WindowsApps alias.
- `py` is still unavailable.
- No usable Python executable exists in common install paths such as `C:\Users\mukha\AppData\Local\Programs\Python\Python311\python.exe`, `C:\Program Files\Python311\python.exe`, or `C:\Python311\python.exe`.
- `.venv\Scripts\python.exe` still fails because `.venv\pyvenv.cfg` points to the missing WindowsApps Python target.

Final status for this retry: blocked by local Python runtime/install state after three recovery attempts. The next useful action is external: finish/cancel the stuck Python installer or install a real Python 3.11, then recreate `.venv` and rerun the vue workspace evaluation.

### 2026-06-24 Step3 verification after Python repair

Python became usable again after the Python 3.11 installer completed. The npm wrapper still resolved to the global `python` without project dependencies, so real pipeline verification used the repo virtualenv directly:

```powershell
.venv\Scripts\python.exe testing/codeRepoQA/run_case.py evaluate-case --run-config configs/testing/workspace.json --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json
```

Accepted run:

- Run ID: `run-20260624T013101Z`.
- Baseline compared against: `run-20260623T112023Z`.
- `coverage_status=partial` and `sufficient=false`, same as baseline.
- Oracle overlap remained stable: `implementation_overlap_count=1`, `overlap_count=1`.
- Owner file `src/platforms/web/server/modules/dom-props.js` was found at rank 3, compared with baseline rank 2.
- Retrieved source files dropped from `6` to `5`.
- Tool calls dropped from `513` to `394`.
- Role subqueries dropped from `8` to `5`.
- Retrieval LLM total tokens dropped from `24,239` to `16,856`.
- Uncached prompt plus completion tokens dropped from `23,215` to `15,832`.

Accepted Step3 behavior:

- `primary_intent=defect_localization`.
- `specificity=narrow`.
- Active objectives were `implementation_owner`, `behavior_path`, and `effects_output`.
- `diagnostic_surface` was deferred because the prompt had expected-vs-actual output but no concrete error, warning, exception, traceback, or diagnostic text.
- Required roles narrowed from all five legacy roles to `behavior_output`, `validation_checking`, and `representation`.
- Deferred support roles remained available through the current compatibility bridge. This is not the final adaptive-loop design, but it was necessary for this case until Stage can promote deferred objectives only after an evidence check.

Rejected intermediate attempts:

- `run-20260624T012539Z` regressed after expected-vs-actual output was incorrectly allowed to activate `diagnostic_surface`; it missed the oracle owner file. The fix was to split `has_diagnostic_surface` from `has_output_symptom` and map wrong output to `effects_output`.
- `run-20260624T013551Z` regressed after initial supporting roles were restricted to active objectives only; it reduced retrieval tokens further to `12,705` but missed the oracle owner file. That stricter support deferral was reverted. A real promote-on-failure loop is required before support roles can be removed from the initial compatibility execution path.

Verification after the accepted code state:

- `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval` passed 13 tests.
- `.venv\Scripts\python.exe -m py_compile services/retrieval/workspace/stage.py services/retrieval/workspace/step2/step2.py services/retrieval/workspace/step2/prompts.py tests/test_workspace_step2_objectives.py` passed.

## Expected Effects

Expected quality impact:

- Better owner-file precision for narrow bug reports because owner discovery is first-class.
- Less early noise from docs/config/generic diagnostics.
- Better behavior explanations because control/data reachability is explicit.
- Cleaner handling of tests/docs/config as evidence kinds rather than universal support roles.

Expected token impact:

- Lower first-pass retrieval tokens for narrow bugs.
- Similar or higher total tokens only when evidence-driven expansion is necessary.
- Better cost observability because every expansion is tied to a stop-contract failure.

Regression risks:

- Intent misclassification could over-narrow retrieval.
- Deferring docs/config/tests can miss cases where those artifacts are the true owner.
- New objective names may duplicate old roles unless compatibility mapping is explicit.
- Query reduction can remove rare but important terms if done aggressively.

Mitigations:

- Keep compatibility aliases during migration.
- Require stage-level evidence checks before stopping.
- Allow one controlled fallback broadening round when owner confidence is low.
- Log all deferred-objective promotions for benchmark comparison.

## Source Links

- Sillito, Murphy, and De Volder, "Questions Programmers Ask During Software Evolution Tasks": https://doi.org/10.1145/1181775.1181779
- Ko, DeLine, and Venolia, "Information Needs in Collocated Software Development Teams": https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/icse07_ko.pdf
- LaToza and Myers, "Developers Ask Reachability Questions": https://people.cs.gmu.edu/~tlatoza/papers/icse2010.pdf
- Sadowski, Stolee, and Elbaum, "How Developers Search for Code: A Case Study": https://research.google.com/pubs/archive/43835.pdf
- Zhou, Zhang, and Lo, "Where Should the Bugs Be Fixed? More Accurate Information Retrieval-Based Bug Localization Based on Bug Reports": https://soarsmu.github.io/papers/research/Zhou2012WhereShouldTheBugsBeFixed.pdf
- Saha, Lease, Khurshid, and Perry, "Improving Bug Localization using Structured Information Retrieval": https://mattlease.com/papers/saha-ase13.pdf
- Fritz and Murphy, "Using Information Fragments to Answer the Questions Developers Ask": https://www.cs.ubc.ca/~fritz/papers/icse10_infofrag_web.pdf
- Haiduc et al., "Automatic Query Reformulations for Text Retrieval in Software Engineering": https://people.lu.usi.ch/bavotg/papers/icse2013_QueryReformulation.pdf
- Zhang et al., "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation": https://aclanthology.org/2023.emnlp-main.151/
> Historical retrieval-planner design. The `primary_intent` and `secondary_intents` fields shown below were removed on 2026-08-06; active workspace retrieval consumes the central task `IntentContext` and does not reclassify intent. The objective/role material remains retrieval-internal research, not the task-intent contract.
