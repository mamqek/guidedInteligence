# Guided Intelligence Development History

This directory is a chronological reading set for understanding how the system
developed.  Its numbered folders are ordered from oldest to newest.  Every file
inside them is an unmodified copy of a source document from the repository at
the time this directory was assembled; the filename encodes the original path
with `__` in place of path separators.

Use this directory as the source of truth for **development history and design
lineage**.  It is not a substitute for implementation, tests, and active
configuration when establishing present runtime behavior.

## How to read the map

- **Horizontal direction:** time, from older at left to newer at right.
- **Vertical direction:** workstreams operating in parallel during a period:
  retrieval; intent/explanation; evaluation; and product/foundation.
- **Columns:** development eras, not formal product releases.
- **Green:** retained/current decision or continuing record. **Amber:** a
  scoped experiment or measured result. **Grey:** historical design. **Red:**
  explicitly deferred, disabled, or superseded work.

```mermaid
flowchart LR
  classDef current fill:#d1fae5,stroke:#059669;
  classDef history fill:#e5e7eb,stroke:#6b7280;
  classDef experiment fill:#fef3c7,stroke:#d97706;
  classDef deferred fill:#fee2e2,stroke:#dc2626;

  subgraph A["00 · Apr–May 2026 · Foundation / V1"]
    direction TB
    A1["V1, build, project and harness plans"]:::history
    A2["Initial CodeRepoQA plans"]:::history
  end
  subgraph B["01 · Jun 2026 · Retrieval generations"]
    direction TB
    B1["v1 → v1.5 → v2 → v3\nretrieval and ranking decisions"]:::history
    B2["MCP / web UI / connector decisions"]:::history
  end
  subgraph C["02 · Jul–04 Aug · Research + explanation beta"]
    direction TB
    C1["Adaptive-loop / planner research"]:::history
    C2["Explanation design + changelog"]:::history
  end
  subgraph D["03 · 06–08 Aug · Intent milestone"]
    direction TB
    D1["Intent System Design"]:::current
    D2["Evidence Plan\ndeferred"]:::deferred
    D3["Explanation experiments"]:::experiment
  end
  subgraph E["04 · 11–14 Aug · Evidence experiments"]
    direction TB
    E1["Shortlisting, provenance, obligations"]:::experiment
    E2["Candidate-file triage\ndisabled"]:::deferred
    E3["Final evidence / mechanism selection"]:::experiment
  end
  subgraph F["05 · 15–16 Aug · Qualification-first controller"]
    direction TB
    F1["Controller: Step 1 implemented\nlater steps planned"]:::current
    F2["Corpus + statistics"]:::experiment
  end

  A1 --> B1 --> C1 --> D1 --> E1 --> F1
  A2 --> F2
  C2 --> D3
  D1 --> E1
  E3 --> F1

  R0["Retrieval changelog\ncreated 07 Jun"]:::current -->
  R1["updated through Jun"]:::current -->
  R2["updated Jul–04 Aug"]:::current -->
  R3["updated 05–08 Aug"]:::current -->
  R4["updated 11 & 14 Aug"]:::current -->
  R5["updated 15 & 16 Aug\ncontinuing"]:::current
```

The bottom row represents one continuing document, not six documents:
`services/retrieval/docs/retrieval-changelog.md`.  Its copied snapshot is in
`05-qualification-first-controller/` because that is the latest dated era in
this history set.

## Folder guide

| Folder | Period and purpose | Copies |
| --- | --- | ---: |
| `00-foundation-v1` | Original V1, orchestration, project-map, harness, and early CodeRepoQA planning. | 11 |
| `01-retrieval-generations` | Ordered v1–v3 retrieval designs, redesign decisions, and early connector/product direction. | 18 |
| `02-research-explanation-beta` | Adaptive retrieval/planner research alongside the explanation beta and its changelog. | 6 |
| `03-intent-milestone` | The intent rewrite contract, related explanation experiments, and the separately deferred Evidence Plan. | 5 |
| `04-evidence-experiments` | Candidate, provenance, obligation, and final-evidence experiments; includes the disabled/superseded records for honest lineage. | 11 |
| `05-qualification-first-controller` | Current controller decision, continuing retrieval changelog, CodeGraph notes, corpus definition, and measured statistics. | 11 |

## Important interpretation notes

- A document placed later is newer in Git history; it is not automatically a
  replacement for every older document.
- Plans, spikes, and experiments are retained because they explain decisions,
  even when they did not become current behavior.
- The `04-evidence-experiments` folder intentionally keeps disabled and
  superseded work so a reader can see what was tried and rejected.
- The active source paths remain authoritative for future edits.  This reading
  set is deliberately copy-only and should be regenerated when the historical
  corpus needs to include later commits.
