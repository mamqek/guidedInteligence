# Incremental Experiment Execution Protocol

## Purpose

Use this protocol for non-trivial experimental changes that affect more than one stage, contract, heuristic, prompt,
or model decision. Its purpose is to prevent several individually plausible changes from being implemented together
and then evaluated as one opaque result.

The core workflow is:

1. decompose the experiment into independently observable changes;
2. order them by dependency;
3. implement and test one change at a time;
4. require repeatable evidence before moving on;
5. limit iteration so one uncertain idea cannot consume the entire experiment;
6. preserve exact failure evidence;
7. test the combined system only after the individual boundaries are understood;
8. report accepted, incomplete, and rejected behavior separately.

This is an execution protocol, not a reason to implement an experiment without user authorization.

## When to use it

Use this protocol when any of the following applies:

- a proposed change contains two or more independently meaningful behaviors;
- a change crosses stage boundaries, such as analysis, retrieval, structural resolution, ranking, qualification,
  scheduling, final selection, or response generation;
- multiple prompts, schemas, model calls, algorithms, or payload representations will change;
- a regression could plausibly originate at several points in the pipeline;
- the expected benefit may be hidden by stochastic model behavior;
- the experiment changes token usage or candidate volume enough that downstream behavior may change indirectly.

A small deterministic fix with one obvious input/output contract does not need the full protocol, but it should still
receive focused tests proportional to its risk.

## 1. Write the experiment plan before implementation

Create a temporary or decision-specific experiment document before modifying behavior. The document must state:

- the observed problem, with a concrete artifact or trace;
- the unchanged baseline behavior;
- the proposed changes, separated into distinct steps;
- the stage boundary of every step;
- dependencies between steps;
- the intended quality effect of each step;
- expected token, runtime, and candidate-volume effects;
- known regression risks;
- isolated verification for each step;
- combined acceptance testing;
- rollback criteria;
- a result ledger to update during implementation.

Do not describe a collection of changes as one experiment merely because they serve the same final goal. If one
behavior can be changed, tested, accepted, or reverted independently, it is a separate step.

## 2. Order steps by data flow and dependency

Order the plan from the earliest changed boundary to the latest. A typical order is:

1. input analysis or prompt generation;
2. query/candidate production;
3. deterministic transformation or structural resolution;
4. payload representation;
5. LLM decision over that payload;
6. downstream qualification, scheduling, or selection;
7. end-to-end integration.

An earlier accepted step becomes a fixed input contract for the next step. Do not modify it again while diagnosing a
later step unless evidence shows that its contract is insufficient. If that happens, return explicitly to the earlier
step, count a new attempt there, and rerun every dependent verification afterward.

## 3. Define a narrow stage boundary for every step

For each step, write down:

- what code, prompt, schema, or contract may change;
- what must remain unchanged;
- the exact input used for testing;
- the exact output being judged;
- which later pipeline stages must not run yet;
- whether the input is live or replayed from a saved real artifact.

Use the cheapest real boundary capable of proving the intended behavior. Examples:

- Test request analysis without running retrieval when only generated questions changed.
- Replay saved retrieval results when testing deterministic grouping or serialization.
- Invoke only the relevant real LLM stage when testing its prompt or decision contract.
- Stop before final selection when testing qualification payload construction.

Do not run the whole pipeline merely because it is available. End-to-end output is poor evidence for an isolated
stage when several downstream decisions can obscure the result.

## 4. Preserve a reproducible baseline

Before changing a step, save enough information to compare it fairly:

- exact input or testcase;
- repository snapshot and index signature when relevant;
- model, prompt profile, schema, and generation settings;
- relevant stage input and output artifacts;
- candidate/ranking details rather than only final output;
- token use, runtime, tool-call counts, and payload size;
- current success and failure examples.

Keep unrelated settings fixed. If an index, model, prompt profile, or testcase changes, treat it as a new comparison
and identify it explicitly.

Saved real output may be replayed into a downstream stage to isolate that stage. Label it as replayed input. Never
silently replace an LLM-backed stage with deterministic fake behavior.

## 5. Use a maximum of three implementation attempts per step

An **attempt** is one implementation variant, not one execution of that variant.

For each step:

1. Implement the smallest plausible change.
2. Run the focused verification.
3. If it fails, inspect the exact input/output and identify a concrete cause.
4. Modify only that step and count the modification as the next attempt.
5. Stop after at most three variants.

Do not make three speculative modifications at once and call them one attempt. Each attempt must have a recorded
hypothesis explaining why it should improve the observed failure.

## 6. Require two repeatable successful runs

A stochastic or LLM-backed step is not accepted from one favorable output. The chosen variant must satisfy its
focused acceptance criteria in at least two runs under unchanged conditions.

The two runs should test the same intended contract. When overfitting is a realistic risk, add a small regression
fixture from another repository or behavior, but do not replace the required two main checks with unrelated cases.

For deterministic stages, run the same fixture twice when concurrency, ordering, batching, caching, or external tool
behavior could vary. Otherwise, byte-for-byte deterministic tests plus one real boundary execution may be enough if
the experiment plan explains why.

## 7. Decide what happens after three unsuccessful attempts

After the third variant, compare all attempts with the unchanged baseline.

### Retain the best attempt only when

- it is measurably better than baseline on the intended intermediate behavior;
- its remaining limitation is explicitly understood;
- it introduces no observed regression severe enough to erase the benefit;
- downstream work can still be interpreted correctly with that limitation;
- it is labeled `best-effort retained`, not `accepted`.

### Revert the step when

- none of the three variants improves the baseline;
- improvements are not repeatable;
- the change merely moves the failure to a later stage;
- token/runtime growth is not justified by behavior;
- the mechanism relies on testcase-specific hardcoding;
- the result cannot be distinguished from random model variation.

After either decision, document:

- all three variants;
- exact observed outputs;
- what failed and at which boundary;
- why the best variant was retained or why everything was reverted;
- a plausible future direction, if one remains;
- whether dependent steps should continue, change, or stop.

## 8. Keep changes independently reversible

Structure implementation so each step can be removed without deleting accepted work from other steps.

- Prefer one cohesive patch or commit-sized unit per step.
- Keep stage responsibilities behind clear contracts.
- Avoid leaving legacy and replacement behavior active together unless compatibility was explicitly requested.
- Do not hide an experimental difference inside an unrelated refactor.
- Use temporary diagnostics where necessary, but remove noisy instrumentation or move it to traces before final
  acceptance.

If temporary experiment switches are needed for comparison, keep them on the testing surface rather than creating
permanent ambiguous production branches. Remove them once a decision is made.

## 9. Measure intermediate behavior, not only final success

For each changed boundary, inspect the evidence that proves how behavior changed. Depending on the stage, record:

- generated questions, classifications, anchors, or structured fields;
- raw channel results and exact ranks;
- grouping, deduplication, admission, and held alternatives;
- structural resolution counts and unresolved inputs;
- serialized fields, source visibility, truncation, and payload size;
- LLM selections, rejections, and stated reasons;
- created, scheduled, executed, and blocked actions;
- stop reasons and pending work;
- final evidence and coverage decisions;
- token use broken down by changed LLM stage;
- runtime and non-LLM tool calls.

Do not report that evidence was “not found” merely because it was absent from the final result. Audit every boundary
from raw retrieval through final selection and distinguish exact-owner absence from a present textual or structural
lead that was later hidden, demoted, rejected, or never executed.

Hidden-Oracle overlap is a regression signal, not the sole definition of relevance. Inspect whether non-Oracle
results are logically part of the requested mechanism and whether irrelevant lexical matches were correctly removed.

## 10. Test interactions only after individual steps are understood

After all viable steps have isolated decisions:

1. Run a cheap actual-pipeline diagnostic with expensive unrelated stages disabled when the project policy permits.
2. Inspect every changed boundary in one trace.
3. If that trace is mechanically and semantically sound, run the required full acceptance path.
4. Keep final evidence selection enabled when retrieval changes can alter its input.
5. Skip explanation generation unless explanation quality is the experiment.

For retrieval experiments, follow the repository's run policy in `AGENTS.md`: normally at least two actual-pipeline
acceptance runs for the main case, with explanation generation disabled and final evidence selection enabled.

If combined behavior regresses despite individually successful steps, disable or revert one step at a time against
the same inputs. Identify the interaction rather than tuning several stages simultaneously.

## 11. Reporting format

Lead with the behavioral conclusion, then provide enough evidence to reproduce it.

### Per-step report

- **Change:** what behavior changed, in plain language.
- **Boundary:** what was and was not executed.
- **Attempts:** variants tried, up to three.
- **Repeatability:** the two focused runs and whether both passed.
- **Observed behavior:** concrete input/output differences.
- **Cost:** tokens, runtime, payload/candidate growth.
- **Regressions:** observed failures and untested risks.
- **Decision:** accepted, best-effort retained, or reverted.

### Final experiment report

- accepted steps;
- best-effort retained steps and their limitations;
- reverted ideas and why they failed;
- combined actual-pipeline results;
- behavior at important intermediate boundaries;
- total and stage-specific cost changes;
- unresolved or naturally unexercised cases;
- clear recommendation: keep, revise later, or avoid.

Do not present diagnostic smoke runs as acceptance results. Do not call an unexercised edge case solved. Do not hide a
failed variant merely because a later attempt worked.

## 12. Result ledger template

Create this table in the experiment-specific plan and update it during work:

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Step name | 1–3 | Pass/fail + artifact | Pass/fail + artifact | Measured value | Pending/accepted/best-effort/reverted | Exact limitation |

For a failed or unstable step, also record:

| Attempt | Hypothesis | Exact change | Observed failure | Root cause | Future option |
|---:|---|---|---|---|---|
| 1–3 | Why it might work | Stage-local modification | Concrete trace evidence | Known/inferred, labeled | Next non-implemented idea |

## Completion checklist

Before calling the experiment finished, verify that:

- [ ] Every independently meaningful change had its own step.
- [ ] Every step had a defined boundary and baseline.
- [ ] No step exceeded three implementation variants.
- [ ] Every accepted stochastic step passed twice under unchanged conditions.
- [ ] Failed variants and unresolved cases were documented.
- [ ] Steps with no improvement were reverted.
- [ ] Intermediate evidence and costs were inspected.
- [ ] Combined behavior was tested through the real pipeline when required.
- [ ] Interaction regressions were traced to a specific step.
- [ ] The final report distinguishes accepted, best-effort, reverted, and untested behavior.

