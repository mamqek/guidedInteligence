# Corpus-wide required-evidence audit

This report scores the 700 runs in the final September campaign against exact pre-resolution evidence requirements. File presence alone never satisfies a unit. Connections classify cases but are not separately scored at run level.

## Overall results

| Condition | Complete runs | Required-unit survival | Mean final files | Mean required files represented | Mean implementation-Oracle files represented | Mean other files | Capacity-shortfall runs |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full Workspace | 23/140 (16.4%) | 113/312 (36.2%) | 3.89 | 1.01 | 1.08 | 2.81 | 12/140 |
| Without CodeGraph | 17/140 (12.1%) | 84/312 (26.9%) | 3.81 | 0.98 | 1.06 | 2.76 | 8/140 |
| Without controller | 19/140 (13.6%) | 96/312 (30.8%) | 3.24 | 0.91 | 0.94 | 2.29 | 20/140 |
| Without either | 10/140 (7.1%) | 62/312 (19.9%) | 3.25 | 0.89 | 0.96 | 2.29 | 18/140 |
| Codex | 55/140 (39.3%) | 183/312 (58.7%) | 6.49 | 1.36 | 1.49 | 5.00 | 0/140 |

## Connected versus independent required evidence

| Evidence layout | Condition | Cases | Complete runs | Required-unit survival |
|---|---|---:|---:|---:|
| Connected | Full Workspace | 17 | 7/68 (10.3%) | 39.8% |
| Connected | Without CodeGraph | 17 | 8/68 (11.8%) | 31.9% |
| Connected | Without controller | 17 | 5/68 (7.4%) | 33.3% |
| Connected | Without either | 17 | 3/68 (4.4%) | 24.1% |
| Connected | Codex | 17 | 19/68 (27.9%) | 60.2% |
| Independent | Full Workspace | 18 | 16/72 (22.2%) | 28.1% |
| Independent | Without CodeGraph | 18 | 9/72 (12.5%) | 15.6% |
| Independent | Without controller | 18 | 14/72 (19.4%) | 25.0% |
| Independent | Without either | 18 | 7/72 (9.7%) | 10.4% |
| Independent | Codex | 18 | 36/72 (50.0%) | 55.2% |

## Required-file count

| Required files | Condition | Cases | Complete runs | Mean final files | Mean required files represented |
|---:|---|---:|---:|---:|---:|
| 1 | Full Workspace | 20 | 19/80 (23.8%) | 3.67 | 0.60 |
| 1 | Without CodeGraph | 20 | 10/80 (12.5%) | 3.33 | 0.59 |
| 1 | Without controller | 20 | 15/80 (18.8%) | 2.99 | 0.57 |
| 1 | Without either | 20 | 7/80 (8.8%) | 3.06 | 0.59 |
| 1 | Codex | 20 | 39/80 (48.8%) | 6.09 | 0.86 |
| 2 | Full Workspace | 9 | 4/36 (11.1%) | 4.19 | 1.28 |
| 2 | Without CodeGraph | 9 | 7/36 (19.4%) | 4.39 | 1.31 |
| 2 | Without controller | 9 | 4/36 (11.1%) | 3.94 | 1.31 |
| 2 | Without either | 9 | 3/36 (8.3%) | 3.47 | 1.11 |
| 2 | Codex | 9 | 12/36 (33.3%) | 6.14 | 1.64 |
| 3 | Full Workspace | 4 | 0/16 (0.0%) | 4.31 | 1.81 |
| 3 | Without CodeGraph | 4 | 0/16 (0.0%) | 4.25 | 1.62 |
| 3 | Without controller | 4 | 0/16 (0.0%) | 2.94 | 1.19 |
| 3 | Without either | 4 | 0/16 (0.0%) | 3.38 | 1.44 |
| 3 | Codex | 4 | 4/16 (25.0%) | 6.38 | 2.19 |
| 5 | Full Workspace | 1 | 0/4 (0.0%) | 2.00 | 0.00 |
| 5 | Without CodeGraph | 1 | 0/4 (0.0%) | 5.00 | 0.00 |
| 5 | Without controller | 1 | 0/4 (0.0%) | 1.75 | 0.00 |
| 5 | Without either | 1 | 0/4 (0.0%) | 3.00 | 0.00 |
| 5 | Codex | 1 | 0/4 (0.0%) | 18.50 | 1.75 |
| 6 | Full Workspace | 1 | 0/4 (0.0%) | 5.50 | 4.75 |
| 6 | Without CodeGraph | 1 | 0/4 (0.0%) | 5.50 | 4.25 |
| 6 | Without controller | 1 | 0/4 (0.0%) | 4.50 | 3.75 |
| 6 | Without either | 1 | 0/4 (0.0%) | 4.75 | 3.75 |
| 6 | Codex | 1 | 0/4 (0.0%) | 6.25 | 5.25 |

## Interpretation boundary

These measurements establish whether the exact required snippets survive together. Final-selection omissions are directly recorded. Earlier boundaries are inferred by comparing the last recorded stage where a unit is visible with the next stage where it is unavailable; they locate the boundary but not necessarily the exact internal decision responsible. The measurements do not establish that the response model understood a connection merely because both endpoints were present. Connectedness and required-file count are therefore explanatory case characteristics, not additional success criteria.

Detailed per-case and per-run results are generated in appendix-required-evidence-audit.md.
