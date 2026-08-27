# AST-owned callable recovery compatibility

## Boundary and hypothesis

Vue run-20260827T104818Z disclosed and qualified assignment-defined functions but the qualified-call recovery gate
rejected their `source_owner` identity prefix as a non-callable kind. Its JavaScript call tool also required a
persistent graph ID. These are two parts of one adapter-compatibility defect (QFL-1), not a relevance decision.

Keep initial retrieval, owner comparison, qualification prompts, 60,000-character preferred admission, final flow
filtering, scheduler priority, caps, and index scope unchanged. Resolve the actual callable kind from the existing
language AST adapter at the recovery boundary, independently of the synthetic ID prefix. Validate exact identity,
path, range and name against current source before examining calls. The JavaScript tool must accept that validated
source owner without fabricating a graph node; Python definitions/lambda assignments use the same contract.

## Sequence

1. Extend the language-routed source-call operation to validate AST-source identities, preserve actual callable kind
   in its result, and inspect the exact owner body. Do not include neighboring or independently nested callables.
2. Permit that validated source kind through qualified-lead discovery, keeping visible-call, unique graph-target,
   utility, novelty, and qualification checks intact. Record the actual source callable kind in lead provenance.
3. Focused JS/Python fixtures for ordinary/assignment owners, nested/sibling isolation, stale/spoofed range/name,
   non-callable source, and out-of-workspace paths. Replay saved Vue source through actual tools twice; log old gate
   exclusions and new calls/eligible targets. Then two actual Vue 242 runs, final selection on, explanation off,
   unchanged model/config/index. No new indexing or full TypeScript benchmark is needed for this adapter boundary.

Expected impact: recover previously unreachable source-grounded leads; no extra LLM stage, but newly inspected
owners can increase downstream token use. Risks: misidentifying enclosing owners, nested-call leakage, ambiguous
targets, and low-value callees consuming existing slots. At most three variants; retain only a verified compatibility
improvement without repeated attributable quality regression. Unknown targets remain unknown, not fabricated edges.

## Ledger

Implementation variant 1: the recovery boundary keeps existing qualification-card metadata unchanged and obtains
`source_kind` from validated AST call inspection, retaining it as `source_callable_kind` in lead provenance. Thus
identity (`source_owner:...`) is not mistaken for executable kind. No SourceHandle or initial qualification payload
contract changes were needed. JS dispatch accepts source metadata only for AST identities and validates exact source
identity/range/name before examining the body, without opening or manufacturing a persistent source graph node.
Python validates definitions and direct lambda assignments via the same router, and excludes nested callable bodies.

110 focused AST, CodeGraph, discovery, qualification and action-policy tests pass. Actual saved Vue round-zero
replays `ast-owner-repeat-1` and `ast-owner-repeat-2` are identical: 9 structural requests, zero LLM tokens. The formerly
blocked checkPriorityDir and Directive.parse now reach call inspection as assigned_function. Visible utils.attr/warn
targets fail unchanged unique graph resolution; undisclosed string-method calls fail the visibility check. Zero
eligible leads is not a failed source-owner fix: the first loss boundary demonstrably moves to existing target/
visibility checks. Target-side AST-only resolution, alias inference and nested callback tracing remain out of scope.

Baseline Vue 242 run-20260827T104818Z:
partial/false, 1 implementation Oracle, 8 final items / 4 files, 64,936 retrieval tokens, zero verified-call executions.
The separate helper-flow and preferred-size-prefix concerns are not modified in this experiment.

First complete live run (`115408Z`): AST-owned `CompilerProto.createBinding` (source_owner:src/compiler.js:690:738)
is inspected at trace 183 with 12 calls; bindDirective (641:685) at 201 with 9; parseDirective (623:636) at 286 with 4.
All return source_kind=assigned_function and source_identity_kind=ast_source_owner. This is real source inspection,
not merely additional logging of the old rejection. Zero eligible new leads and zero verified executions: existing
target resolution and the shared eight-target budget still block candidates. Utility/instance-method ambiguity was
not overridden. The run uses three rounds versus the baseline's two; 79,757 versus 64,936 retrieval tokens is not an
isolated cost estimate for the adapter change, since source selection and qualification/coverage batches also differ.
Stage tokens: context 1,316; initial comparison 25,985; qualification 25,723; coverage 15,902; final selection 10,831.

| Run | Status | Result |
|---|---|---|
| run-20260827T115315Z | Invalid, excluded | initial_owner_comparison_invalid_global_selection before changed code, 24,671 retrieval tokens |
| run-20260827T115408Z | Complete | partial/false, 1 implementation Oracle, 8 items / 4 files, 79,757 retrieval tokens |
| run-20260827T115536Z | Invalid, excluded | Same upstream owner-comparison validation failure, 23,220 retrieval tokens; changed recovery never ran |
| run-20260827T115757Z | Complete | partial/false, 0 implementation Oracles, 5 items / 3 files, 38,184 retrieval tokens |

Second complete run (`115757Z`) did not exercise the changed source-owner path: both discovery batches made zero
tool calls (trace 80/122). Qualification marked all five resolved initial owners navigation_only, with zero
supported obligations (70); the only initial direct evidence was an unresolved on.js range. Later qualification
again marked Directive.parse/Directive navigation_only and rejected parseFilter (109). The unchanged direct-evidence
gate therefore prevented source-call inspection. It stopped after one round with no_evidence_gain (130).

The missing implementation Oracle was not lost by this fix: exp-parser.js:88-102 appeared in raw sparse results
(38/43), resolved to makeGetter:93-101 (54), and its file was admitted (56). All 28 files fitted, using 45,458
comparison-input characters; stopping_reason was ranking_exhausted. Owner comparison considered makeGetter but
left it dormant (61), selecting six snippets from three other files. It was absent from subsequent qualification,
controller final candidates (130/131), and final evidence (143-147). Thus the first exclusion was owner comparison,
before recovery, not admission size or final filtering. The caller defineExp's parser handoff remained visible but
navigation_only, so this direct-evidence-only recovery policy did not pursue it. No claim of raw lead absence is made.

Decision: retain the narrow source-owner compatibility correction, not a claim of improved final retrieval quality.
Focused fixtures and two identical real-source replays establish the corrected boundary; one complete live run
exercised it, the other did not reach it. Final quality was unstable (1/0 Oracle files versus baseline 1), but the
second run's loss preceded the changed boundary and no new recovery actions ran in either run. Do not attribute
the lower token total to the fix or broaden target resolution/direct-evidence eligibility to rescue these results.
Target-side AST-only identities, instance/alias resolution, lookup-budget ordering, and final helper-flow survival
remain separate experiments. Neither existing upstream validator failure was hidden or counted as acceptance.

Reproducibility: `testing/codeRepoQA/qualified-file-lead-replays/ast-owner-acceptance.json` contains per-run metrics,
trace-line discovery audits, scheduling, final items and stage token totals. The two `ast-owner-repeat-*` directories
contain identical deterministic replay results. All actual runs reused the existing index (trace 9, rebuilt=false),
kept final selection enabled and skipped explanation generation. Config/model/prompts and early stages were unchanged.

Runs/replays use the existing bundled Node v24.16.0 through process-local PATH. One combined test invocation omitted
that PATH override and failed the graph fixture on the shell Node's missing node:sqlite; it was rerun with the
compatible runtime. No production code or dependency change was made for that environment-only failure.

## Adjacent proposals, not implemented

- Final-flow selection: getReferencedByPaths receives supporting from `_mechanism_candidate_roles` because it has
  neither a mutation/name-pattern match nor another recognized causal role. It is a read-only dependency lookup,
  despite qualification's direct support. Test allowing semantically qualified, source-connected reader snippets
  to compete in final selection without automatic role-based exclusion; retain budget/deduplication controls. Do not
  solve this by adding a special-case symbol keyword or admitting all generic helpers.
- Initial file admission: do not raise the preferred limit yet. The observed Pandas prefix used 20,356 characters
  and stopped before a large file, rejecting all later files. A separate fixed-budget replay should measure what a
  skip-and-continue admission policy would admit and displace, including deferred recovery; raising the target alone
  does not address this early-stop behavior. No 100,000-character preferred target was enabled.
