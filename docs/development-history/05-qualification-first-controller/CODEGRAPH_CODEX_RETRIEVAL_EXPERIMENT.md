# CodeGraph For Codex Retrieval Experiment

## Scope

This experiment evaluates whether exposing the project-local CodeGraph MCP tool to Codex retrieval reduces discovery work without lowering evidence quality. It does not enable CodeGraph in the production Codex retrieval command or prompt.

The experiment used temporary `codex exec` configuration overrides with user configuration ignored. No global or project Codex MCP configuration was written.

## Tool Recognition

The CodeGraph MCP server initialized successfully and exposed one read-only tool, `codegraph_explore`. A direct Next-check query returned 15,048 characters of source and relationships in 0.10 seconds.

A forced Codex recognition probe called `codegraph_explore` once, made no shell calls, and returned a broadly correct backend-to-UI flow. It used 37,714 input tokens and completed in 23.36 seconds. This proves compatibility, not a production benefit.

## A/B Results

### Cross-language Next-check flow

Prompt: trace how `next_check_requirement` reaches `NextChecksBox`.

| Arm | Retrieval calls | Input tokens | Time | Quality |
| --- | ---: | ---: | ---: | --- |
| Baseline | 22 shell calls | 404,987 | 76.35s | Complete flow, including response builder, control layer, API payload, and UI extraction. |
| CodeGraph, natural MCP guidance | 8 MCP calls | 262,331 | 55.86s | Lower token/time cost, but omitted part of the serialization/API handoff. |
| CodeGraph, explicit bounded guidance | 1 MCP + 7 shell calls | 168,431 | 80.07s | Lowest token count, but still repeated ordinary retrieval and remained less complete than baseline. |

CodeGraph reduced tokens for this broad cross-language question, but Codex did not reliably stop after the graph result and quality was less complete.

### Evidence-graph implementation flow

Prompt: trace how `build_evidence_graph` combines the JavaScript CodeGraph bridge, structural edges, semantic edges, and final coverage validation.

| Arm | Retrieval calls | Input tokens | Time | Quality |
| --- | ---: | ---: | ---: | --- |
| Baseline | 10 shell calls | 106,413 | 60.06s | Correct ordered flow and correct JavaScript bridge path. |
| CodeGraph with explicit first query | 5 MCP calls | 152,972 | 70.69s | More expensive and slower; reported the bridge under an incorrect directory. |

The direct CodeGraph CLI query itself found the Python implementation, JavaScript bridge, structural conversion, and validation in one 0.1-second result. The regression came from Codex repeatedly querying and interpreting the MCP result, not from index speed.

## Decision

Do not enable CodeGraph in production Codex retrieval yet.

Production Codex retrieval uses `--ignore-user-config`, so globally configured MCP servers are not inherited by the retrieval subprocess. The experimental CodeGraph access existed only through temporary command-line overrides used by the measurements above.

Codex recognizes and can use the tool, but current behavior is unstable by task shape:

- it may call the same broad tool five to eight times;
- it does not consistently treat returned source as already read;
- cross-language questions may save tokens but omit important transport stages;
- focused symbol-flow questions can cost more than normal `rg` and targeted reads;
- an incorrect path appeared in one CodeGraph answer despite the correct file being indexed.

The project-local CodeGraph package is used by native workspace retrieval for exact structural search and by the post-retrieval evidence graph. It is not exposed as a tool to Codex retrieval. A future Codex retrieval experiment should first constrain MCP calls mechanically or provide a smaller purpose-built result surface, then repeat representative A/B runs before integration.
