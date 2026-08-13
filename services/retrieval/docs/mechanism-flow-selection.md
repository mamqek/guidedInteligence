# Mechanism Flow Selection

## Stage boundary

This implementation replaces connected explanation bundle construction and the
final evidence assessment after semantic retrieval and CodeGraph expansion.
Initial retrieval still performs one
Qdrant query per obligation, but every query now includes deterministic terms
owned by its intent stage so an unstable generated proposition cannot erase
mechanism concepts such as mutation, signature, invalidation, or handoff.

The replacement treats a candidate explanation as a directed mechanism flow. It
keeps exact CodeGraph call and qualified-reference direction, and may add two
explicitly lower-confidence source-derived relationships between already grounded
exact functions:

- a dynamically invoked collection callback whose argument is compatible with a
  semantically grounded callback function; and
- a write to an object field followed by a read of the same field in the same
  repository subsystem.

Before selection it can also localize missing exact functions through:

- a two-hop CodeGraph call-connected implementation-file frontier followed by
  obligation-specific Qdrant search inside only those files;
- exact same-file named callees found in visible source, for two rounds; and
- explicit `Owner.member(...)` calls when `Owner` equals the target filename
  stem and exactly one grounded member matches.

File-level connectivity is discovery scope only. It is never emitted as a
candidate-to-candidate evidence edge. The obligation that discovered a candidate
is retained as provenance, but no longer limits how the candidate may support the
final explanation.

### Candidate-facts boundary

`GroundedCandidate` is the single record enriched across retrieval stages. Its
`CandidateFacts` payload contains only deterministic observations already
available from the retrieval process: per-obligation Qdrant rank/score and
matched terms; source-local visible calls, callable defaults, returned names,
and field reads/writes. It deliberately does **not** classify a node as a
semantic owner, causal transition, or relevant endpoint.

This replaces repeated ad-hoc parsing of candidate snippets in later graph
stages. A narrow bridge may use these facts only to decide whether a bounded
exact CodeGraph lookup is justified. The final LLM still evaluates whether a
verified or source-inferred relationship actually explains the issue.

No CommonJS export assignment or prototype-assigned function recovery is included
in this experiment.

## Selection policy

- Qdrant provenance establishes and strengthens flow roots but never excludes a
  graph-valid continuation.
- Candidate paths are extended in edge direction rather than grown as undirected
  connected components.
- Node responsibility terms come only from the exact symbol and owner path, not
  from body vocabulary copied from callees.
- Every retained seed receives a fair per-seed flow-generation allowance before
  the global flow cap is applied. A highly branching early seed therefore cannot
  prevent later state-owner seeds from producing any hypothesis.
- Paths are scored by prompt/obligation responsibility, direct semantic
  grounding, exact transition quality, and newly established mechanism terms.
  Repeated direct discovery strengthens a concise root, but does not assign
  ownership of that evidence to an obligation.
- Parallel descriptions of the same exact directed endpoint pair compete. The
  stronger relationship is retained. Reverse edges, different targets, and
  paths with different intermediate nodes do not compete and may coexist.
- Raw edge count, component size, and the number of novel file paths provide no
  positive score.
- Root hypotheses are ranked by the root's own semantic/recurrence strength, not
  by repeatedly inheriting the score of a shared path prefix. After each
  selection, a positive connectivity bonus promotes roots whose candidates or
  bidirectional recorded file provenance connect to the selected mechanism.
- An obligation, root file, or candidate file is never consumed as a slot.
  Several outgoing branches from one function can survive when they add
  distinct exact endpoints or substantive causal nodes. Incoming and outgoing
  branches are always distinct.
- The final LLM selects one request-level causal mechanism and at most fourteen
  indispensable snippets globally. It then maps those snippets many-to-many to
  the obligations their visible source actually supports. There is no
  per-obligation evidence quota and discovery provenance is not an eligibility
  restriction.
- Obligations are assessed after mechanism selection as `prompt_grounded`,
  `repository_supported`, `jointly_supported`, `partial`, or `unresolved`.

## Expected impact

Quality:

- TypeScript watch/project-reference roots should retain the directed builder and
  builder-state invalidation branches through final assessment.
- Vue SSR should retain `renderNode -> renderElement -> renderStartingTag`, the
  registered server DOM-props callback, `setText`, and the `children` mutation.
- Semantically similar but context-incompatible paths should not win merely because
  they are large or highly connected.

Tokens:

- Initial retrieval keeps the same number of obligation queries. Connected
  semantic localization adds deterministic tool calls but no LLM call.
- During this experiment there is no aggregate serialized-character limit on
  mechanism candidates, flows, or connections. Test runs still call the final
  evidence-consolidation LLM, which selects at most fourteen snippets globally;
  only the later prose explanation LLM is explicitly skipped. This measures the
  evidence decision that the mechanism graph is designed to feed while avoiding
  unrelated explanation-generation cost.
- Removing path-diversity bundle fill is expected to reduce unrelated source text.
- Candidate facts add compact structured metadata to the final consolidation
  request. They add no LLM call and no new source text, but can increase payload
  size modestly; runs record the complete serialized size for comparison.

## Regression risks

- Dynamic callback inference is source-derived rather than a compiler-proven call
  edge and can connect callbacks with generic parameter names.
- Field write/read inference can over-connect common fields such as `value` or
  `name`; it is therefore restricted by subsystem compatibility, semantic support,
  and field dispersion.
- A repository whose mechanism is primarily declarative or uses unsupported
  CommonJS/prototype function definitions may still produce only a partial flow.
- Directed traversal can omit a necessary upstream owner when no qualified-call or
  state-flow relation is available. Direction-neutral discovery remains intact so
  such candidates are still auditable in the ledger.
- Global selection can over-concentrate on one compelling mechanism and leave a
  narrative obligation unsupported. The post-selection obligation assessment
  makes that gap explicit instead of filling it with weak evidence.
- Independent semantic retrieval still changes which exact functions exist in
  the candidate inventory. The allocator cannot construct an Oracle handoff
  whose endpoint an upstream run never localizes. The ledger now distinguishes
  that absence from a later selection rejection.
- Without an aggregate character limit, a normal consolidation request can
  exceed a model context window or become noisy. This is intentional only while
  mechanism selection is being measured; a justified limit must be introduced
  after the structural policy is stable.
- Syntax facts can be true but irrelevant. They must only bound deterministic
  exploration and must never become automatic relevance or responsibility
  labels.

## Comparison

Focused tests cover exact calls, qualified owner calls, two-round named-callee
localization, callback dispatch, state write/read flow, exact directed endpoint
competition, preservation of reverse/different-target branches, and the absence
of file-diversity rewards. Real measurements and limitations are recorded in
`retrieval-changelog.md`.
# File-node call localization experiment

## Stage boundary

This experiment changes only the boundary between CodeGraph expansion and grounded
candidate creation. CodeGraph `file` nodes remain usable as transient structural
hints, but they are never evidence candidates. For TypeScript and JavaScript
`calls` edges owned by a file node, the source is parsed and the strongest call
site is localized to its outermost named executable owner (function, method,
constructor, or accessor). If no named owner can be established, the relationship
is discarded.

Candidate identity remains the complete named executable and retains its full
range and graph identity. Candidate source text is a compact excerpt around the
chosen call anchor. Nested containment and the direct call remain separate facts;
the implementation does not rewrite containment into an exact direct call.

## Expected quality impact

- Remove whole-file placeholder candidates and their repeated 100-line prefixes.
- Preserve precise named callers that were previously hidden behind aggregate
  file-level CodeGraph edges.
- Reduce duplicate candidates by keeping one primary, structurally reliable call
  anchor per named owner.

## Expected token impact

The candidate pool and any later evidence-selection payload should shrink because
raw file snippets are removed and oversized owners use bounded excerpts. The AST
localization itself is deterministic and adds no LLM tokens.

## Known regression risks

- A repository-relevant call that exists only inside anonymous top-level callbacks
  will be discarded unless it is found independently by semantic retrieval.
- A coarse file edge may represent several legitimate callers; selecting one
  primary anchor can omit a weaker alternative.
- TypeScript/JavaScript are the only languages supported by this first adapter.

## Comparison method

Run `microsoft-TypeScript-35468` with final evidence selection and response
generation disabled. Compare the pre-selection candidate count, raw file-node
candidate count, per-file repetition, Oracle-file presence, localized owner
decisions, and candidate source sizes against the most recent saved workspace run.
Every localization result records the matched decision code, all considered call
sites, and the chosen reliability tier.

The first two real comparisons showed unstable watch-side Oracle recall, but
neither run retrieved the relevant `watchMode.ts` aggregate node. That does not
establish that file-node exclusion caused the instability. Raw file nodes are
therefore rejected unconditionally: they are neither evidence nor expansion
seeds. A file-level `calls` edge receives one immediate AST-localization attempt;
successful named owners become candidates and unresolved edges are discarded.
