# Island evidence packet final-selection experiment

Status: controlled comparison completed; the representation is mechanically safe and has a positive, though still
small, cross-case signal. Default promotion is recommended separately from dormant-file alternatives.

## Observed problem and baseline

Across 20 completed 2026-08-30 traces, the controller produced 339 qualified candidates and the mechanism-flow reducer sent 191 to final comparison. Only 77/191 candidates participated in a multi-node flow; 114 were singleton-only hypotheses. Multi-flow candidates were selected by the final LLM 66/77 times, versus 60/114 singleton-only candidates. The post-LLM preservation pass then added 38 active-island candidates and seven file-trace source candidates that the final LLM had not compared. Navigation evidence was especially poorly represented: 69 navigation candidates existed in controller pools, none reached the LLM, and 15 were appended afterward.

The unchanged baseline is the existing global mechanism-flow selector followed by active-island and file-trace-source preservation.

## Step 1 — Deterministic island packet construction

Boundary: final-selection payload construction only.

- Group qualified candidates by their already-computed semantic island ID.
- Give a multi-candidate island an atomic base packet containing a compact connected/role-diverse candidate set.
- Reserve at most one navigation member in a connected packet only when an internal relationship or the best known
  flow grounds that member. An unconnected navigation candidate cannot displace direct evidence.
- Give every singleton island an admission unit regardless of whether another island already supports the same obligation.
- Keep navigation provenance explicit and admit navigation singletons to comparison; they remain unable to establish coverage alone.
- Spend the existing character budget on whole units. Duplicate obligation coverage is never an exclusion reason.
- Add further role-diverse candidates to admitted connected packets only with remaining budget.
- Preserve the final LLM prompt, schema, candidate snippets, qualification decisions, and output cap.

Expected quality effect: more coherent island flows reach final comparison; independently qualified singleton alternatives remain comparable.

Expected cost effect: no extra LLM call. Final-selection input may move closer to the existing character cap; trace the exact payload and tokens.

Risks: too many singleton islands can consume the budget; a deterministic packet may choose the wrong members of a mixed island; removing post-LLM preservation may reduce final file diversity if packet admission is incomplete.

## Step 2 — Move preservation before comparison

Dependency: attempt only after Step 1 proves that all intended active islands and navigation singletons reach the LLM.

In the experimental path, remove post-LLM active-island preservation. File-trace source handling remains unchanged until its exact-source dependency is measured separately.

## Verification and rollback

- Focused deterministic tests: connected packet depth, duplicate-obligation singleton admission, navigation singleton admission, atomic budget behavior, unchanged baseline.
- Actual pipeline: TypeScript 35468 twice, then pandas 10068 and Vue 242 regression runs with response generation skipped and final selection enabled.
- Compare candidate/island admission, connected-flow rate, selected files, coverage, sufficiency, final-selection tokens, and total retrieval tokens.
- Revert or leave disabled if two TypeScript runs regress selected evidence or sufficiency, or if cost grows without coherent-flow improvement.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Island packet construction | 1 | TypeScript `114956Z`: 4 implementation Oracles | TypeScript `115754Z`: 3 implementation Oracles | 122,099 / 129,142 retrieval tokens | Promising but unstable; keep opt-in | BuilderState became dormant before packet construction in repeat 2 |
| Grounded navigation reservation | 2 | TypeScript `122654Z`: 3 implementation Oracles | TypeScript `123214Z`: 3 implementation Oracles | 124,758 / 118,596 retrieval tokens | Mechanically valid; no natural activation in acceptance | Both pools contained zero navigation-qualified candidates; BuilderState again absent upstream |
| Pre-comparison preservation | 1 | Experimental requests appended zero active-island candidates after the LLM | Exact file-trace source preservation remained active | No extra LLM call | Retain only inside opt-in packet mode | Requires a stable packet input before default promotion |

## Measured result

The experiment is selectable with
`--final-evidence-selection-representation island_packets`; the unchanged default remains `mechanism_flows`.
Focused packet, qualification, obligation-retrieval, and server suites passed all 221 tests.

The first TypeScript run, `run-20260831T114956Z`, demonstrated the intended benefit: the final comparison received
coherent packets, selected BuilderState rather than losing it as an isolated candidate, and returned Builder,
BuilderState, WatchMode, and the Helpers file trace. It remained `partial/false` and used 122,099 retrieval tokens.
The immediately repeated run, `115754Z`, returned only Builder, WatchMode, and Helpers. Boundary tracing showed that
BuilderState had been retrieved, but initial owner comparison placed it in the dormant pool; eight deferred
BuilderState observations remained uninspected through all rounds. The file was therefore absent from the final
candidate pool and could not be recovered by packet construction.

An unchanged-selector comparison, `run-20260831T120950Z`, put BuilderState in its 30-candidate final pool but the
final LLM rejected it, returning the same three implementation Oracles at 132,511 retrieval tokens. This supports
the narrow claim that packets can improve final comparison when the relevant island reaches that boundary. It does
not support a stability claim, because two later packet runs (`122654Z`, `123214Z`) again received no BuilderState
candidate and returned three Oracles. Both respected the 45,000-character selector budget with zero overshoot. Their
candidate pools contained no navigation-qualified evidence, so natural activation of the grounded-navigation rule
remains unproven beyond focused tests.

Cross-repository actual runs did not show a new regression signal. Pandas 10068 `run-20260831T121739Z` returned zero
implementation Oracles at 104,609 tokens, within that case's existing 0/1 variability. Vue 242
`run-20260831T122149Z` retained `src/exp-parser.js`, matching recent successful runs, at 91,660 tokens.

Decision: do not make island packets the default. Keep the isolated mode for controlled comparison because it
demonstrated one real final-boundary improvement without changing the baseline. Treat dormant-owner scheduling as a
separate upstream problem; do not compensate for it by weakening packet admission or adding post-LLM evidence.

## Controlled default-promotion comparison (in progress)

This follow-up isolates packet construction from dormant-file alternatives.  Dormant-file alternatives are disabled
in every run; response generation is skipped and final evidence selection remains enabled.  The representation is
the only changed setting.  Modes are alternated rather than grouped:

| Case | Runs |
|---|---|
| TypeScript 35468 | `mechanism_flows`, `island_packets`, `island_packets`, `mechanism_flows` |
| pandas 10068 | `mechanism_flows`, `island_packets`, `island_packets`, `mechanism_flows` |
| Vue 242 | `mechanism_flows`, `island_packets` |

Promotion requires every packet run to retain every mandatory baseline seed, no repeatable Oracle regression in
either TypeScript or pandas, and no material unrelated-file noise in the final-comparison payload.  The audit also
records final-pool composition, final selection, and retrieval-token totals; packet mode must demonstrate a useful
coherent-context benefit rather than merely add prompt volume.

## Controlled comparison result (2026-09-01)

All runs used the same workspace profile, existing indexes, final evidence selection enabled, response generation
skipped, and dormant-file alternatives explicitly disabled.  The only varied setting was
`final_evidence_selection_representation`.  The pandas packet attempt `run-20260901T010828Z` is excluded: the
remote LLM closed its connection during qualification and it produced no retrieval result.  Its direct replacement
is included below.

| Case | Mechanism-flow runs | Packet runs | Outcome |
|---|---|---|---|
| TypeScript 35468 | `214651Z` (3), `005654Z` (4) | `215438Z` (4), `215941Z` (3) | Equal mean implementation-Oracle overlap: 3.5. Packet `215438Z` retained Builder, BuilderState, WatchMode, and the Helpers file trace. |
| pandas 10068 | `010423Z` (0), `011740Z` (0) | `011207Z` (0), `011424Z` (0) | No mode-specific recovery or regression. All four runs missed the upstream `core/series.py::_binop` owner; the packet runs sent only the relevant arithmetic/test context and did not add unrelated-file noise. |
| Vue 242 | `012208Z` (0) | `012458Z` (1) | Packet mode retained `src/exp-parser.js`, the implementation Oracle, alongside the compiler/directive flow; baseline did not. |

Every packet run retained every normal-flow mandatory seed in the *same run's* controller pool: 14/14 and 12/12
for TypeScript, 3/3 and 4/4 for pandas, and 8/8 for Vue.  This is the relevant safety invariant: independent runs
can have different qualified pools due to live LLM/controller decisions, but packet construction cannot discard a
candidate that unchanged mechanism-flow selection would have supplied from that pool.

There was no extra LLM stage.  Final-consolidation token totals were TypeScript 17,636/16,914 in packet mode versus
18,955/17,725 baseline; pandas 7,738/9,062 versus 11,675/12,229; Vue 13,345 versus 10,236.  Total retrieval tokens
varied chiefly with upstream controller work, so they are not evidence that packet mode itself reduces controller
cost.  They do show that the representation did not create a systematic final-selection cost increase.

Decision: the controlled comparison passes the packet-mode promotion gate.  It is reasonable to make
`island_packets` the default final-selection representation, while retaining `mechanism_flows` as an explicit
diagnostic override.  This decision does **not** claim to resolve pandas 10068: its loss occurs before final-pool
construction, when the relevant `core/series.py::_binop` owner remains unqualified and therefore absent from both
representations.
