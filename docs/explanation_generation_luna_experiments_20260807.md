# GPT-5.6 Luna explanation-generation experiments

## Scope

- Explanation generation only; retrieval was not rerun.
- API model: `gpt-5.6-luna` through the existing Chat Completions path.
- Codex results are reused from `docs/explanation_generation_experiments_20260807.md`; Codex was not rerun.
- Paragraph-level citation relocation was not rerun.
- The main comparison reused the 14 evidence items from `run-20260806T225055Z-7ffa037b`.
- Two curated evidence fixtures test patterns that the main case does not naturally contain:
  - `testing/fixtures/explanation_table_case.json`
  - `testing/fixtures/explanation_json_case.json`

## Main saved-evidence case

Question: `Where is intent classification handled, and how does it flow into retrieval, explanation structure, and question generation?`

Artifacts: `.guided-intelligence/explanation-experiments/experiment-20260807T002125Z`

| Variant | Luna valid runs | Ordered-list use | Mean stage-sentence characters | Flow repairs | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 2/2 | 2/2 | 180.3 | 0/2 | 22.7 s |
| Presentation-focused | 2/2 | 2/2 | 126.5 | 1/2 | 25.8 s |
| Reader-focused | 2/2 | 2/2 | 198.8 | 0/2 | 18.0 s |

Both baseline runs already selected an ordered list and covered classification, retrieval, explanation structure, and question generation. The presentation-focused instructions shortened sentences substantially and consistently produced a five-step list, but they were not needed to make Luna recognize the sequence. The reader-focused instructions preserved explicit question coverage and actor/state framing, but sentence length increased, repeating the earlier Codex result.

## Comparison with reused Codex results

| Variant | Luna | Prior Codex | Practical difference |
| --- | --- | --- | --- |
| Baseline | 2/2 valid; lists in 2/2 | 3/4 valid; lists in 2/3 valid runs | Luna was more structurally reliable and selected the list more consistently. |
| Presentation-focused | 2/2 valid; lists in 2/2; 126.5 mean characters | 3/4 valid; lists in 3/3 valid runs; 156.2 mean characters | Both followed the ordered-list trigger; Luna produced shorter stage prose. |
| Reader-focused | 2/2 valid; 198.8 mean characters | 2/2 content runs valid; 190.3 mean characters; three additional CLI infrastructure failures | Both improved explicit framing but made prose longer; the extra reader instruction is not justified as a concision improvement. |

Codex runtimes were roughly 3–5 minutes per successful run in the earlier experiment. Luna completed the main runs in roughly 18–33 seconds. This latency comparison includes different provider paths and is descriptive, not a pure model-speed benchmark.

## Table case

Question explicitly requests an API-versus-Codex comparison across provider selection, model choice, transport or credentials, token settings, and timeout.

Artifacts: `.guided-intelligence/explanation-experiments/experiment-20260807T002345Z`

| Variant | Valid | Produced a table | Repairs | Observation |
| --- | ---: | ---: | ---: | --- |
| Baseline | 2/2 | 2/2 | 0/2 | The existing production prompt was sufficient. Both outputs used two provider rows. |
| Presentation-focused | 2/2 | 2/2 | 0/2 | One run used a clearer five-dimension table, but both also added a list and one added an unrelated configuration example. |

Decision: keep the existing content-aware table rule. Do not add the whole presentation-focused instruction block for table selection; explicit user intent plus suitable evidence already triggers tables, while the stronger block can over-format the answer.

## JSON example case

Question explicitly requests the workspace generation configuration as JSON. The evidence contains the exact outer `generation` object.

Initial artifacts: `.guided-intelligence/explanation-experiments/experiment-20260807T002458Z`

- Baseline and broad presentation instructions produced zero structured `examples` blocks in 4/4 runs.
- One baseline run placed a JSON code fence directly inside stage prose, and other runs represented the object as prose or a one-item list.
- Therefore the general instruction to use examples when helpful was too weak, even with Luna.

Focused experimental artifacts:

- `.guided-intelligence/explanation-experiments/experiment-20260807T002640Z`
- `.guided-intelligence/explanation-experiments/experiment-20260807T002700Z`
- `.guided-intelligence/explanation-experiments/experiment-20260807T002917Z`

An explicit example-only instruction demonstrated that Luna can produce the structured block, but exact-shape reliability was incomplete: one output omitted the outer `generation` key, and one repaired output changed the JSON into a list. Inspection showed that the generic explanation repair prompt did not preserve explicitly requested presentation formats.

Production v5 artifacts: `.guided-intelligence/explanation-experiments/experiment-20260807T003100Z`

| Production prompt | Valid | Structured JSON example | Complete outer object | Repairs |
| --- | ---: | ---: | ---: | ---: |
| v5 baseline | 2/2 | 2/2 | 2/2 | 0/2 |

The shipped v5 rule treats an explicitly requested, evidence-supported JSON format as required and forbids embedding it in prose or disguising it as a list. The repair prompt now preserves such a block when repairing unrelated fields.

## Decisions

| Idea | Result with Luna | Decision |
| --- | --- | --- |
| Ordered lists for real sequences | Worked in every main-case run, including baseline | Keep the existing production trigger; the broad extra presentation block is unnecessary for list selection. |
| Tables for repeated dimensions | Worked 4/4 when the question and evidence naturally supported comparison | Keep the existing production table rule. |
| Explicit JSON examples | Failed 4/4 under general guidance; passed 2/2 after the targeted v5 and repair changes | Keep the targeted explicit-format rule and repair preservation. |
| Broad presentation-focused appendage | Shortened sentences, but sometimes added unnecessary blocks | Do not ship as one bundle. Isolate sentence-length guidance if tested further. |
| Reader-oriented appendage | Covered the question, but baseline already did; sentences became longer | Do not ship as-is. Retain the existing semantic-flow rules instead. |
| Paragraph-level citation relocation | Not rerun; earlier result weakened claim-to-source alignment | Keep rejected. |

## Changed defaults and contracts

- Web UI generation profiles and the repository-local active config now default explanation generation to `gpt-5.6-luna`.
- New configurations created by `RuntimeState` default `generation.api_model` to `gpt-5.6-luna`.
- `testing/replay_explanation_experiments.py` defaults API experiments to `gpt-5.6-luna`, accepts curated case files, records expectations, and makes citation compaction opt-in.
- `testing/publish_explanation_experiments.py` publishes completed saved-evidence replays as clearly labeled standard run-history entries without rerunning retrieval.
- Explanation prompt template ID advanced to `intent_composed_explanation_v5` for the explicit JSON-example behavior.

## UI history publication

The comparison artifacts were published into `.guided-intelligence/runs` as 16 normal history entries:

- 6 intent-flow runs: baseline, presentation, and reader variants repeated twice.
- 4 table runs: baseline and presentation variants repeated twice.
- 4 pre-fix JSON runs labeled `format miss`.
- 2 final v5 JSON runs with successful structured examples.

Every published entry states that saved evidence was reused and retrieval was not rerun. The original experiment result is preserved as `experiment-result.json` in its run directory.
