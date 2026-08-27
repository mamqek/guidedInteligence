# Owner-comparison shortlist experiment (planned)

## Historical audit

The audit parsed 95 grouped owner-comparison calls from August 25–26. Among 310 file groups from which the LLM
selected at least one owner, 585 owners were selected. A hard first-ten prefix retained 443 selections (75.7%) and
retained every selected owner in only 195 groups (62.9%). There were 142 selected owners below position ten.

Reordering the same candidates using only currently serialized navigation signals did not solve the loss:

| Ten-item policy | Selected owners retained | Groups retaining every selection |
|---|---:|---:|
| Existing order prefix | 443 / 585 | 195 / 310 |
| Best retrieval rank, then support | 434 / 585 | 187 / 310 |
| Dense/sparse and obligation agreement, then rank | 437 / 585 | 186 / 310 |
| Four rank leaders + four agreement leaders + ordered fill | 444 / 585 | 194 / 310 |

Deep selections included `invalidateProjectAndScheduleBuilds`, `queueReferencingProjects`,
`forEachReferencingModulesOfExportOfAffectedFile`, `Project::updateGraph`, and issue-relevant test scenarios. In the
measured TypeScript run `run-20260826T141453Z`, `builderState.ts` owners `updateShapeSignature` and
`updateExportedModules` occupied positions 11 and 12 and both became qualified final evidence. A deterministic
ten-item prefix would therefore have removed the second implementation Oracle from that run.

## Proposed isolated experiment

Construct at most ten candidates per file from explicit, auditable strata rather than a single scalar sort:

- best retrieval-supported owners;
- owners supported by both dense and sparse channels;
- distinct retrieved source regions;
- distinct callable, state, diagnostic, and test-scenario responsibilities;
- exact request anchors and exact structural target hints;
- at most one candidate from a substantially redundant structural-owner family.

The experiment must replay saved comparison payloads before any actual pipeline run and report retention of prior
semantic selections, payload characters, per-file candidate concentration, and every previously final owner omitted
by the shortlist. Simple rank/support-only variants are rejected by the historical audit and must not be retried as
the proposed semantic-diversity shortlist.

## Status

Planned, not implemented.
