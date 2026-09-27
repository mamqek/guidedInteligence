# Thesis integration of the required-evidence audit

This note fixes how the corpus-wide exact-source audit is used in the thesis.
It prevents later chapter revisions from redefining the measure, choosing only
favourable cases, or repeating the 700-run inspection manually.

## Measured construct

The required-evidence reference defines the minimum pre-resolution source
snippets needed to explain or verify each testcase's resolution. The fixing
commit or pull request identifies the relevant responsibility, but only source
from the pre-resolution snapshot can satisfy a unit. A run is complete only
when all required units are present together in final selected evidence.

Connections between units are recorded as a testcase characteristic. They do
not add another success condition, and the audit does not infer that a model
understands a relationship merely because both endpoints are present.

For every run, report together:

- the status of each required unit: present, partial, or absent;
- whether the complete required set survives;
- the number of distinct required files;
- the total number of files returned by final selection;
- the number of required files and implementation-Oracle files represented;
- the first recorded Workspace boundary at which the unit becomes unavailable.

The standardised initial-comparison boundary is the reduction from prepared
ranges or structural owners to round-zero snippets admitted for qualification.
Final-selection omissions are directly recorded. Earlier boundaries are
inferred from changes between successive stage observations and do not
necessarily identify the exact internal decision responsible. Codex exposes
final source ranges but no comparable internal lifecycle trace, so its missing
units receive no internal loss assignment.

## Corpus-wide results

The reference contains 78 units. Four repetitions produce 312 unit
observations per condition.

| Condition | Complete runs | Required units present | Mean final files | Mean required files represented |
|---|---:|---:|---:|---:|
| Full Workspace | 23/140 (16.4%) | 113/312 (36.2%) | 3.89 | 1.01 |
| Without CodeGraph | 17/140 (12.1%) | 84/312 (26.9%) | 3.81 | 0.98 |
| Without controller | 19/140 (13.6%) | 96/312 (30.8%) | 3.24 | 0.91 |
| Without either | 10/140 (7.1%) | 62/312 (19.9%) | 3.25 | 0.89 |
| Codex | 55/140 (39.3%) | 183/312 (58.7%) | 6.49 | 1.36 |

Required-file dispersion constrains joint completeness. Full Workspace
completes 19 of 80 one-file runs and 4 of 36 two-file runs, but none of the 24
runs requiring three or more files. Codex completes 39 of 80 one-file runs, 12
of 36 two-file runs, and 4 of 16 three-file runs; it does not complete the five-
or six-file cases. File count is not sufficient by itself: some runs return as
many files as the reference requires but select the wrong combination or expose
only partial ranges.

Seventeen cases have connected required units and 18 have no inter-unit source
connection. Connected cases have lower whole-set completion but slightly higher
unit survival in Full Workspace and Codex. Do not interpret that difference as
a causal effect of connectedness because connected cases also contain more
units and more often span several files.

For Full Workspace's 199 absent or partial unit observations, the first
decisive losses are raw retrieval (54), initial comparison (19), recovery or
qualification (31), candidate-pool construction (66), and final evidence
selection (29). Missing evidence is therefore not solely a raw-retrieval
problem.

## Main-text case selection

Chapter 7 uses four cases selected after corpus-wide scoring. The selection is
purposive and diagnostic, not statistically representative:

- pandas 10068 shows cross-run fragmentation of three connected units in three
  files: Full Workspace finds every unit somewhere across four repetitions but
  never retains all three together;
- pandas 16499 shows three independent requirements in one file and isolates
  the effects of structural-owner recovery and later controller stabilisation;
- Vue 10803 shows a one-file final-selection loss in which the correct file is
  returned but a required helper snippet is omitted;
- TypeScript 16278 shows the capacity and composition problem of six required
  units across six files.

These cases cover connection, file dispersion, component behaviour, and loss
boundary. The appendix contains all 35 cases and all 700 run-level judgements,
so the examples explain corpus results rather than serving as their basis.

## Placement and claim boundaries

- Chapter 3 may claim that the thesis evaluates file localisation, exact
  required-source survival, and joint required-evidence completeness.
- Chapter 4 defines reference construction, scoring, file counts, loss
  boundaries, aggregation, and purposive case selection.
- Chapter 5 describes the implemented evidence lifecycle only. Its claim that
  missing evidence can be traced to a lifecycle boundary is supported by the
  Workspace audit and requires no new evaluation prose in that chapter.
- Chapter 7 reports the compact aggregate tables and four diagnostic cases.
- The generated manuscript appendix carries the complete per-case and per-run
  ledger, including each unit definition and whether the displayed run-level
  boundary is direct, inferred, or unavailable.
- Chapter 8 may interpret why the systems differ, but must not restate source
  availability as proof that a model understood a causal mechanism.

The authoritative numerical source is `corpus-required-evidence-audit.json`.
Regenerate every dependent table and claim after any revision to the required-
evidence reference.
