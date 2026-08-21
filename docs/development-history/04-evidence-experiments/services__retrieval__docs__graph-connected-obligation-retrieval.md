# Graph-First Obligation Retrieval

## Stage boundary

The active workspace retrieval path is:

1. Run one Qdrant seed search for each repository evidence obligation.
2. Map semantic seeds and exact request anchors to CodeGraph nodes.
3. Expand exact CodeGraph nodes for up to three bounded rounds, preserving every grounded candidate and edge.
4. Use path-scoped Qdrant localization only when the current CodeGraph frontier has no usable exact range.
5. Apply deterministic generated-file, provenance, and duplicate filtering after expansion.
6. Call the LLM once, after traversal stops, to select the final user-visible evidence set.
7. Assess required transitions separately. Reusing the same node for two stages does not prove forward progress.

The removed implementation performed local semantic refinement, global connected-frontier semantic search, intermediate LLM consolidation, graph/Qdrant recovery, and a second consolidation call. Those paths are not retained as fallbacks.

## Expected quality impact

- Exact calls and references survive without being replaced by semantically similar ranges.
- Intermediate candidates remain available throughout traversal; an LLM cannot reject a node before expansion finishes.
- Final evidence is selected from the completed candidate graph rather than from an early partial frontier.
- Missing CodeGraph transitions remain unresolved unless distinct evidence supplies a real graph edge or supported semantic handoff.

## Expected token impact

- Request analysis and initial Qdrant seed discovery are unchanged.
- Repeated frontier Qdrant calls are removed when CodeGraph supplies exact ranges.
- Evidence selection uses one LLM call instead of initial consolidation plus recovery consolidation.
- The final call remains proportional to the number and size of shortlisted obligation candidates.

## Regression risks

- Broad request analysis can still create noisy obligation-specific seed sets.
- CodeGraph may not represent value-flow transitions such as creating a VNode in one function and serializing its text elsewhere.
- A bounded three-round traversal can stop before a long graph path is exhausted.
- Final LLM selection remains variable, so deterministic transition validation must not treat candidate reuse as causal progress.

## Verification

Primary real case: `vuejs-vue-10803`.

- `run-20260811T040621Z` exposed the first implementation defect: 427 pre-selection candidates and only `setText` surviving the final shortlist.
- `run-20260811T040832Z` and `run-20260811T042558Z` retained both `renderDOMProps` and `setText`, selected both Oracle files, used 47-48 tool calls, zero frontier Qdrant calls, and one final-selection LLM call.
- `run-20260811T042943Z` exposed a false-positive sufficiency bug: the LLM reused the same nodes across obligations and shared-node transitions produced `strong/true`.
- `run-20260811T043219Z` is the final measured run: `partial/false`, both Oracle files selected, implementation owner rank 1, 50 tool calls, three graph rounds, zero frontier Qdrant calls, one final-selection LLM call, and 13,486 final-selection tokens. The missing serializer transition remains explicit.

The attempted `microsoft-TypeScript-35468` comparison, `run-20260811T041029Z`, did not reach retrieval. The shared Qdrant collection had been replaced by the Vue repository, so it spent the 15-minute command budget rebuilding TypeScript embeddings. This run is not evidence for or against the traversal change.

## Candidate-path replacement experiment

### Stage boundary

- Remove the fixed obligation-term overlap threshold from CodeGraph traversal. A real productive CodeGraph edge, not repeated prompt vocabulary, determines structural eligibility inside the bounded frontier.
- Keep exact owner-qualified references and their source call sites as provenance. Remove additive promotion and normalized `source_confidence` bonuses; neither is calibrated evidence quality.
- Remove evidence-role score adjustments and role-based path narrowing. Roles remain visible to final evidence assessment so tests can establish expected behavior while executable source establishes mechanisms.
- Replace the four independent shortlist winners with candidates from the connected components that cover the most obligations and retain the strongest initial semantic/request seeds. Text overlap remains only a final tiebreaker.

### Expected quality impact

- Recover code whose names differ from issue prose but is reached through an exact call, reference, import, implementation, or instantiation edge.
- Prevent unrelated code from becoming eligible merely because its symbol/path repeats common obligation words.
- Preserve exact qualified relationships without allowing arbitrary additive bonuses to crowd the shortlist.
- Present the final LLM with a coherent candidate path rather than unrelated category winners.

### Expected token impact

- Qdrant seed calls and the single final LLM call remain unchanged.
- More exact CodeGraph nodes may survive traversal, but component-first shortlisting remains capped at four candidates per obligation.
- Removing score compounding should reduce repeated utility candidates; the net candidate-graph size must be measured rather than assumed.

### Regression risks

- High-fan-out utility nodes can enlarge the structural frontier when lexical gating is removed.
- CodeGraph components may not connect cross-language or value-flow handoffs; a disconnected semantic seed must remain available rather than being discarded.
- A coherent but irrelevant seed component can still dominate if initial Qdrant grounding misses the actual owner.
- Evidence-role removal from ranking may surface more test/configuration candidates, so final role-aware support assessment must remain enforced.

### Comparison cases

- `vuejs-vue-10803`: exact same-file call continuation and missing serializer handoff.
- `microsoft-TypeScript-35468`: qualified namespace references and large-graph utility noise.
- `pandas-dev-pandas-10068`: code naming differs from issue prose while arithmetic owners are structurally connected.
- `vuejs-vue-242`: initial Qdrant seed miss; verifies that graph changes do not falsely claim to fix a pre-graph failure.
