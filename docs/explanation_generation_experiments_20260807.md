# Explanation generation experiments — 2026-08-07

## Scope

- Saved retrieval run: `run-20260806T225055Z-7ffa037b`
- Fixed input: the same user question, 14 selected evidence items, retrieval summary, and evidence graph connections for every generation.
- No retrieval was rerun.
- API control: `gpt-4.1-mini`.
- Stronger-model control: Codex CLI with `gpt-5.4-mini`.
- Prompt groups were isolated: baseline, presentation/concreteness, and reader understanding/completeness.
- Citation compaction was evaluated as a deterministic alternate rendering of each completed output.

Raw artifacts are under `.guided-intelligence/explanation-experiments/`.

## Outcome summary

| Experiment | Model | Attempts | Completed | Main result |
|---|---|---:|---:|---|
| Baseline | GPT-4.1 mini | 2 | 1 | The completed run needed flow and question repairs; the other repeated an oversized-section error after repair. |
| Presentation | GPT-4.1 mini | 4 | 0 | Three runs repeated an oversized-section error; one failed to preserve the ordered stage partition. |
| Reader understanding | GPT-4.1 mini | 4 | 0 | All four repeated an oversized-section error after repair. |
| Baseline | Codex | 4 | 3 | Two of three completed outputs chose an ordered list; one model attempt failed question evidence validation. |
| Presentation | Codex | 4 | 3 | Every completed output chose an ordered list with three or four items; one attempt failed because a connective carried evidence refs. |
| Reader understanding | Codex | 2 content runs | 2 | Both completed without flow or question repair and explicitly covered question generation. |

Three later reader retries failed before generation because the Codex CLI could not create a PowerShell shell snapshot. They are recorded as infrastructure failures and excluded from content success rates.

## Run evidence

### GPT-4.1 mini

| Artifact group | Run | Status | Elapsed | Repairs / failure |
|---|---|---|---:|---|
| `experiment-20260806T232756Z` | `baseline-api-1` | complete | 68.5 s | flow 1, question 1 |
| `experiment-20260806T232756Z` | `baseline-api-2` | failed | 50.8 s | oversized titled section after repair |
| `experiment-20260806T232756Z` | `presentation-api-1` | failed | 53.7 s | oversized titled section after repair |
| `experiment-20260806T232756Z` | `presentation-api-2` | failed | 55.7 s | oversized titled section after repair |
| `experiment-20260806T233417Z` | `presentation-api-1` | failed | 52.1 s | oversized titled section after repair |
| `experiment-20260806T233417Z` | `presentation-api-2` | failed | 54.5 s | section partition reordered after repair |
| `experiment-20260806T232756Z` | `reader-api-1` | failed | 58.4 s | oversized titled section after repair |
| `experiment-20260806T232756Z` | `reader-api-2` | failed | 55.5 s | oversized titled section after repair |
| `experiment-20260806T233417Z` | `reader-api-1` | failed | 50.8 s | oversized titled section after repair |
| `experiment-20260806T233417Z` | `reader-api-2` | failed | 55.2 s | oversized titled section after repair |

The only completed GPT-4.1 output used four sections, no rich blocks, average stage-sentence length 208 characters, and a maximum of 300 characters.

### Codex baseline

| Artifact group | Run | Status | Elapsed | Lists | Repairs / failure |
|---|---|---|---:|---:|---|
| `experiment-20260806T232756Z` | `baseline-codex-1` | failed | 255.2 s | — | question evidence validation failed after isolated repair |
| `experiment-20260806T232756Z` | `baseline-codex-2` | complete | 274.0 s | 1 | flow 1, question 1 |
| `experiment-20260806T233800Z` | `baseline-codex-1` | complete | 172.7 s | 0 | flow 1 |
| `experiment-20260806T234103Z` | `baseline-codex-1` | complete | 231.5 s | 1 | none |

Presentation selection was already variable in the Codex baseline: two completed runs used a list and one did not.

### Codex presentation/concreteness

| Artifact group | Run | Status | Elapsed | Rich output | Repairs / failure |
|---|---|---|---:|---|---|
| `experiment-20260806T232756Z` | `presentation-codex-1` | failed | 309.4 s | — | connective incorrectly carried evidence refs |
| `experiment-20260806T232756Z` | `presentation-codex-2` | complete | 233.4 s | ordered list, 3 items | flow 1 |
| `experiment-20260806T234502Z` | `presentation-codex-1` | complete | 177.1 s | ordered list, 4 items | none |
| `experiment-20260806T234502Z` | `presentation-codex-2` | complete | 307.9 s | ordered list, 3 items | flow 1 |

The presentation instruction made list selection consistent among successful Codex outputs. No run produced a table or example. The fixed question and evidence naturally supported an ordered handoff, but did not contain a strong repeated-dimensions comparison; therefore table behavior was not meaningfully exercised. The evidence did expose payload fields, but neither model considered a JSON example necessary for this question.

### Codex reader understanding/completeness

| Artifact group | Run | Status | Elapsed | Repairs | Notable behavior |
|---|---|---|---:|---:|---|
| `experiment-20260806T232756Z` | `reader-codex-1` | complete | 226.3 s | none | Explicit retrieval, explanation, and question-shaping sections; ordered list selected independently. |
| `experiment-20260806T235314Z` | `reader-codex-1` | complete | 191.9 s | none | Explicit “Question generation” section; no rich block. |

Both runs made the requested question-generation branch visible and used actor/state framing. They also added practical consequences such as explaining that intent shapes routing metadata rather than replacing evidence. Average stage-sentence length increased to about 190 characters, versus about 163 characters across completed Codex baselines, so completeness improved but concision did not.

## Citation-layout experiment

The deterministic alternate renderer moved repeated links to the end of each paragraph while retaining the original structured sentence-to-evidence mapping.

| Completed-output group | Average visible-link reduction |
|---|---:|
| GPT-4.1 baseline | 6.2% |
| Codex baseline | 23.3% |
| Codex presentation | 13.7% |
| Codex reader understanding | 13.2% |

This reduced repeated links, but often replaced them with a large cluster of four or more sources at the paragraph end and weakened the visible sentence-to-source relationship. The alternate rendering should not be adopted as-is. A narrower rule that removes only immediately repeated identical citations would preserve alignment better.

## Decisions from this experiment

1. Keep the new evidence-reference popup metadata; it reuses retrieval metadata and does not affect generation.
2. Do not add the experimental prompt groups to the GPT-4.1 first pass yet. Its structured-section compliance is too unstable to evaluate the content changes safely.
3. The presentation instruction is promising for Codex: all three successful runs selected an appropriate ordered list. Test it again on evidence that genuinely supports a comparison table or concrete request/response example before making it permanent.
4. The reader-understanding instruction is promising for Codex and covered the multi-part question twice without repair. Its next isolated experiment should add a sentence-length constraint rather than combining more changes.
5. Do not ship paragraph-level citation consolidation. Retain sentence-level evidence alignment until a less lossy display rule is tested.
