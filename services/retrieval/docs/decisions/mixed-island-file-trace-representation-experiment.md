# Mixed-island file-trace representation experiment

## Problem and fixed baseline

TypeScript acceptance runs that constructed the WatchMode-to-Helpers file trace still
returned only Builder and BuilderState. In `run-20260829T043211Z` and
`run-20260829T044424Z`, the exact WatchMode source candidate reached the final candidate
pool, but the final LLM did not select it. The later deterministic one-candidate-per-
active-island safeguard also did not restore it because the structural traversal had
merged WatchMode into an island already represented by a compiler implementation file.
The Helpers trace was consequently rejected as `source_island_not_selected`.

This experiment retains the existing one-candidate-per-island safeguard. It restores
the previously tested, bounded pending scheduler only for repository-classified test
source file handoffs: at most two pending actions, one per island, a two-round lifetime,
and at most one existing ordinary slot reserved after round 1. It adds no action slots,
rounds, graph calls, or LLM calls. The scheduler is fixed input for the representation
comparison and will not be broadened during that comparison.

## Step 1 — restore bounded test-source pending scheduling

**Boundary.** Action retention and ordinary scheduling only. Retain an enumerated,
unselected, file-seeded cross-file handoff only when its source observation has
repository-derived `artifact_role == "test"`. Revalidate active island, promotion,
unresolved obligation, uncompleted effect, and lifetime before scheduling.

**Expected effect and cost.** A starved WatchMode handoff can survive loss of its
round-one slot. There are no extra slots/calls; downstream candidates and token use may
change when the retained action executes.

**Risks.** A low-yield test handoff can displace a newly ranked action, and an unstable
island identity can expire useful debt. Bounds and lifecycle checks contain these
risks. This step is restored because the user explicitly wants it combined with the
representation repair; it is not independently reclassified as accepted by the prior
failed final-evidence results.

**Focused verification.** Repeat deterministic lifecycle, cap, deduplication,
test-source filtering, and two-slot scheduler tests twice.

## Step 2 — make deterministic representation precede file-trace eligibility

**Boundary.** Final evidence orchestration only. Candidate selection remains the same
LLM call. Deterministic preservation is applied to its accepted candidate IDs before
the unchanged file-trace eligibility and file-trace LLM stage. The file-trace stage
must run exactly once and only when at least one trace is eligible.

**Expected effect and cost.** A deterministically preserved source can satisfy the
existing exact-source gate. No candidate or file trace is automatically treated as
semantic evidence; the existing file-trace LLM still decides supportive evidence.
There are no new LLM calls beyond a trace call that becomes legitimately eligible.

**Risks.** Previously preserved candidates can now enable traces that were formerly
tested too early. This is intentional, but eligibility and selected trace counts must
remain bounded and observable.

**Focused verification.** Replay a consolidation where an implementation candidate is
selected and the exact test-source candidate is added deterministically. Verify the
trace changes from `source_island_not_selected` to eligible, without bypassing the
trace LLM, and verify the ineligible case makes no trace call.

## Step 3A — exact cross-file trace-source representation

**Boundary.** Extend deterministic active-island preservation. When a created file
trace's exact source observation belongs to a protected active island, and that source
file has no accepted candidate, reserve the best exact-source candidate even if a
different file already represents the island. Keep the global evidence cap and dedupe
by normalized source path. Do not reserve arbitrary untraced files.

**Expected effect.** Preserve WatchMode as evidence and make its already-created
Helpers trace eligible, while retaining the original one-per-island behavior for all
other islands.

**Candidate/cost effect.** At most one extra candidate per distinct traced source path,
bounded by the existing final evidence cap. It may enable the existing file-trace LLM
call; it adds no other call.

**Risk.** A structurally useful navigation source may consume an evidence slot despite
weak direct explanatory value. Exact trace provenance and active-island restriction
make this narrower than general file diversity.

## Step 3B — artifact-role representation inside mixed islands

**Boundary.** Alternative to 3A, not cumulative during comparison. For a protected
active island with accepted representation, reserve the best candidate for an
unrepresented repository-derived artifact role. Retain the original island candidate,
the global evidence cap, and deterministic ordering.

**Expected effect.** A mixed implementation/test island can retain both its compiler
implementation and test-harness perspectives. This may preserve WatchMode without
depending on a particular trace.

**Candidate/cost effect.** Bound role additions to two globally and one candidate per
missing role per island. No direct new calls, though a preserved exact source may enable
the existing file-trace call.

**Risk.** Role diversity is broader and may select a different test file from the
trace source, leaving Helpers ineligible while consuming a slot. This is the principal
comparison against 3A.

## Step 4 — retain source-related obligation provenance on a file trace

**Boundary.** File-trace construction and its existing unresolved-obligation gate.
The first live 3A run showed that the same WatchMode traversal can be scheduled for
`explain_subject`, although the historical successful traversal was scheduled for
`explain_why`. The structural trace is identical, but final eligibility currently
tests only the action's primary scheduling obligation. Record the source observation's
repository-retrieval obligation IDs on the trace and keep it eligible when at least one
of those related obligations remains partial or unresolved. Preserve the exact-source,
destination, endpoint-qualification, and file-trace LLM gates.

**Expected effect and cost.** Remove accidental dependence on which unresolved gap
happened to schedule an otherwise identical file traversal. This may enable the one
existing file-trace LLM call when the primary action obligation is already supported;
it adds no new stage or selection slot.

**Risk.** A source retrieved for several obligations can expose a trace to a broader
set of unresolved needs. The exact accepted source and the file-trace LLM remain
mandatory, and the trace still permits only a structural-participant claim.

## Step 5 — distinguish rejected snippets from repeated structural file evidence

**Boundary.** File-trace eligibility only. Acceptance `run-20260829T061557Z`
restored all three Oracle files, accepted the exact WatchMode source, and retained
related unresolved obligations, but rejected Helpers because the localized
`verifyTscWatch` snippet was classified `reject/insufficient`. The trace independently
contained 18 direct call sites and is prohibited from claiming endpoint behavior.
Permit a rejected endpoint to reach the existing file-trace LLM only when the
controller recorded at least two direct source-to-destination call sites. A one-edge
rejected endpoint remains blocked.

**Expected effect and cost.** Preserve strong structural participation despite a
snippet-level relevance rejection. It can enable the existing file-trace LLM call but
adds no calls or evidence slots by itself.

**Risk.** Repetition can reflect generic utility usage. The exact accepted source,
unresolved related obligation, destination absence, repeated-call threshold, and LLM
supportive-evidence judgment all remain required.

## Step 6 — reserve output capacity for an accepted file trace

**Boundary.** Final evidence composition only. Acceptance
`run-20260829T062527Z` selected Helpers through every gate, but 14 snippet candidates
filled `MAX_EVIDENCE` before file traces were appended. Reserve one output slot per
accepted trace and, when trimming the lowest-priority snippet candidate, protect the
exact source candidate of each accepted trace.

**Expected effect and cost.** An accepted trace is actually emitted, without increasing
the global evidence cap or token cost. WatchMode remains present as the source that
justifies Helpers.

**Risk.** A lower-priority snippet is displaced. The cap remains fixed and only an
LLM-selected trace can reserve capacity.

## Step 7 — reserve one initial owner-comparison snippet per obligation

**Boundary.** Initial owner-comparison admission only. Repeat acceptance
`run-20260829T145414Z` retrieved BuilderState as the top file for
`explain_state_changes`, including nine exact owner ranges, but every range was placed
after the preferred input-budget crossing and excluded. The trace field
`coverage_reserved_paths` existed but was always empty. Reserve the single strongest
retrieved observation for each repository obligation, then apply the unchanged global
snippet ranking and character budget to all remaining input.

**Expected effect and cost.** Ensure every obligation contributes at least one owner to
the comparison without increasing its request budget. Lower-ranked snippets are
displaced rather than appended.

**Risk.** A weak obligation-specific top hit can displace a broadly useful recurrent
owner. The reservation is one snippet, not one full file, and the owner-comparison LLM
can still reject it.

## Comparison and acceptance

First replay the same saved mixed-island shape through 3A and 3B separately. Compare:
accepted paths, whether the exact trace source is accepted, trace eligibility, final
candidate count, and deterministic additions. Retain only the variant that repeatably
restores the exact source with the smaller irrelevant-candidate surface. Do not keep
both merely because both add diversity.

Then run an actual diagnostic TypeScript pipeline with response generation and final
selection skipped to audit scheduling and trace construction. If sound, run at least
two actual acceptance executions with response generation skipped and final selection
enabled. Keep the testcase, model, prompt profile, index, and other retrieval settings
fixed.

Acceptance requires: WatchMode present in final evidence; Helpers selected only through
an eligible LLM-approved file trace; Builder and BuilderState retained; at least three
Oracle implementation files; no ordinary-slot, round, evidence, graph-call, or trace
selection cap exceeded; and explainable token changes. Revert a representation variant
if it loses a stable Oracle, cannot repeat the exact-source restoration, or merely moves
the loss to a later gate.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Test-source pending scheduler | restored | Pass: bounded lifecycle/cap/deduplication suite | Pass: identical repeat | Zero added calls/slots; one existing ordinary slot may be reassigned | Accepted | Live activation remains input-dependent |
| Stage ordering | 1 | Pass: deterministic source preservation precedes trace eligibility | Pass in combined 214-test suite | Only newly eligible existing trace call | Accepted | LLM trace gate remains mandatory |
| Exact trace source (3A) | 1 | Pass: mixed-island replay | Final runs `150112Z` / `150534Z`: WatchMode retained with Helpers | One bounded candidate; existing cap unchanged | Accepted | Navigation source may displace a lower-priority snippet |
| Artifact role (3B) | 1 | Real replay would choose WatchMode on tie | Competing-test fixture chose the wrong test source | Up to 2 broader additions | Rejected and removed | Role does not encode trace provenance |
| Related trace obligations | 1 | Pass: primary-supported/related-partial fixture | Exercised by final runs | Existing trace call may become eligible | Accepted | Multi-obligation source breadth |
| Repeated-call rejected endpoint | 1 | Pass: 18-call positive and 1-call negative fixtures | Exercised by final runs | Existing trace call may become eligible | Accepted | Generic utility repetition remains LLM-gated |
| Trace output capacity | 1 | Pass: protected-source trimming fixture | Helpers emitted in both final runs | No cap/call change | Accepted | Displaces one low-priority snippet |
| Initial obligation reservation | 1 | Pass: 194-test focused suite | Pass: identical repeat; 214-test broader suite | Same comparison request budget | Accepted | Weak top-hit displacement |
| Combined selected variant | 1 | `150112Z`: 4 Oracles, 106,410 tokens | `150534Z`: 4 Oracles, 103,059 tokens | No new caps, slots, rounds, or unconditional calls | Accepted | Overall answer remains `partial/false` |

## Actual-pipeline results and decision

Diagnostic `run-20260829T060303Z` reconstructed the historical traversal naturally:
the controller selected the WatchMode file handoff in round 1 and aggregated 18 direct
WatchMode-to-Helpers calls. Intermediate runs then exposed distinct downstream loss
boundaries rather than random retrieval absence:

- `run-20260829T060847Z` restored WatchMode, but the trace used a primary scheduling
  obligation that was already supported.
- `run-20260829T061557Z` retained all three prior Oracle files, but Helpers was blocked
  by its rejected localized endpoint despite the independent 18-call structural trace.
- `run-20260829T062527Z` passed every trace gate and the trace LLM selected Helpers, but
  the existing 14-item evidence cap was already full before trace append.
- `run-20260829T063022Z` emitted all four target files after trace-capacity reservation.
- Repeat `run-20260829T145414Z` emitted Helpers but lost BuilderState before owner
  comparison: raw retrieval ranked BuilderState first for `explain_state_changes` and
  resolved nine exact owners, but global preferred-budget admission excluded all nine.
  That audit motivated the one-per-obligation initial reservation in step 7.

The final unchanged-profile acceptance pair kept final evidence selection enabled and
skipped response generation:

- `run-20260829T150112Z`: `partial/false`, 14 evidence items, Builder, BuilderState,
  WatchMode, and Helpers all present; Helpers emitted at rank 14; 106,410 retrieval
  tokens.
- `run-20260829T150534Z`: `partial/false`, 12 evidence items, the same four files all
  present; the pending WatchMode handoff executed in round 2 and Helpers emitted at
  rank 11; 103,059 retrieval tokens.

Both Helpers decisions were structural-only: the trace LLM treated the file as a
supportive participant and did not claim knowledge of its internal behavior. The
selected implementation is retained. It combines bounded test-source pending
scheduling with exact trace-source representation; the broader artifact-role variant
is removed. The controller still has the same action slots and round limit, final
evidence still has the same cap, and file traces still require an unresolved related
obligation, exact selected source, absent destination, sufficient repeated structure
when the endpoint snippet was rejected, and explicit LLM selection.

## Cross-repository regression runs

Actual Vue `vuejs-vue-242` and Pandas `pandas-dev-pandas-10068` runs used the same
workspace profile, kept final evidence selection enabled, and skipped response
generation. Initial attempts `run-20260829T153616Z` and `run-20260829T153646Z` are
invalid and excluded: the invoking shell selected Node without `node:sqlite`, so both
failed at CodeGraph initialization before retrieval. They were rerun with the bundled
Node 24 runtime:

- Vue `run-20260829T153748Z`: `partial/false`, ten evidence items, one of two Oracle
  files (`src/exp-parser.js`, final file rank 3), one implementation overlap, and
  92,801 retrieval tokens. The pending scheduler remained empty in all three rounds.
  One ordinary compiler-to-`src/text-parser.js` trace was LLM-selected as navigation-
  only structural evidence. No rejected-endpoint override or exact trace-source
  preservation was needed.
- Pandas `run-20260829T154053Z`: `partial/false`, three evidence items, two of three
  Oracle files (`pandas/core/series.py` and `pandas/tests/test_series.py`), the sole
  implementation Oracle, and 76,670 retrieval tokens. The pending scheduler remained
  empty in all four rounds. One Series-to-`pandas/core/ops.py` trace was LLM-selected
  as navigation-only structural evidence. No rejected-endpoint override or exact
  trace-source preservation was needed.

The per-obligation initial comparison reservation did activate in both repositories.
It used the unchanged 100,000-character input budget; Vue compared 140 candidates
across 22 groups at 60,050 total input characters, and Pandas compared 83 candidates
across 12 groups at 60,128 characters. These single regression runs do not prove a
general quality improvement, but they show no Oracle regression relative to the most
recent recorded Vue/Pandas runs: Vue moved from 0/2 to 1/2 overlap, while Pandas moved
from 1/3 to 2/3. Input and LLM variability prevent attributing those gains solely to
this change.
