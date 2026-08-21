# Backend-Owned Repository Scope Experiment

## Stage boundary

The change is limited to request-analysis obligation construction. Backend
`_StagePolicy.evidence_source` determines whether an obligation enters repository
retrieval. The stage-requirement LLM still supplies the request-specific
proposition, anchor references, and evidence boundary, but an `external` boundary
does not convert a repository-policy stage into an external-only obligation.

Retrieval query construction, Qdrant fusion, CodeGraph traversal, deterministic
shortlisting, final evidence assessment, and transition validation are unchanged.

## Expected quality impact

- Repeated runs of the same intent contract execute the same repository-stage
  topology even when the LLM disagrees about whether the repository proves the
  complete behavior or only a boundary.
- TypeScript `explain_resulting_effect` and `explain_why` cannot disappear before
  repository retrieval merely because the stage-requirement LLM mistakes the
  target repository's compiler for an external dependency.
- The preserved boundary still prevents local evidence from being described as
  proof of external internals.

## Expected token and runtime impact

Cases whose repository-policy stages were previously classified `external` gain
one initial Qdrant query and the associated bounded graph work per stage. The
TypeScript historical comparison predicts six initial repository queries instead
of four. Cases already classified local or local-to-external should be unchanged.

## Regression risks

- A request genuinely asking a repository to explain another dependency's
  internals may now perform a local search that finds only the handoff or no useful
  evidence.
- Additional obligation candidates can increase final-selection tokens even
  though the per-obligation candidate cap is unchanged.
- Stable scope does not guarantee stable query wording, Qdrant ranking,
  shortlisting, or final LLM decisions.

## Comparison

Run `microsoft-TypeScript-35468` twice with `lib` and `tests/cases` excluded.
For each run record evidence source/boundary for all six explain obligations,
initial Qdrant query count, builder-file presence in the final shortlist/request,
Oracle overlap, `coverage_status`, `sufficient`, retrieval tokens, and index reuse.
Keep the change only if both runs execute the same six repository obligations and
do not show a repeated quality regression.

## Result and decision

The scope mechanism worked but failed the quality gate:

- `run-20260811T164149Z` produced six repository obligations and six initial
  Qdrant queries. It had zero Oracle overlap, neither builder file reached the
  deterministic shortlist, coverage was `partial/false`, retrieval used 10,458
  tokens, and the warm index reported `rebuilt=false`.
- `run-20260811T164430Z` again produced six repository obligations and six initial
  queries even though `explain_resulting_effect` and `explain_why` had external
  boundaries. It also had zero Oracle overlap, neither builder file reached the
  shortlist, coverage was `partial/false`, retrieval used 11,617 tokens, and the
  warm index reported `rebuilt=false`.

The historical comparison had implementation Oracle overlap 0/1; this pair was
0/0. Offline reconstruction also showed that chain, responsibility, and
corroboration rankings recovered no TypeScript Oracle file in either run's top
ten. Stable stage count did not stabilize proposition/query content: all six
paired queries differed and mean token Jaccard was 0.409.

The behavior was initially reverted under the isolated experiment's quality
gate. It is now retained as one half of the follow-up combined experiment at the
user's direction: stable repository scope is useful independently, while a
deterministic base-query strand addresses the proposition variation exposed by
these runs. No testcase names, paths, stages, or Oracle files are encoded in the
scope rule.
