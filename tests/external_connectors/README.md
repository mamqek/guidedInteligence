# External Connector Certification Tests

These tests certify that a connected external source participates correctly in
the real retrieval flow. They are intentionally not unit tests for adapter
internals or prompt parsing.

## Test Boundary

Each certification test should provide only:

- a user prompt,
- live connector content available through the configured provider,
- a real or temporary workspace containing files the tool may resolve to,
- assertions about the final retrieval and response-generation result.

The test must not inject internal retrieval decisions such as provider queries,
selected context IDs, selected evidence IDs, file hints, symbol hints, or final
synthesis. Those must be produced by the tool pipeline.

## Certification Shape

1. Prepare connector content.

   The source should contain one relevant document and one plausible but wrong
   document. Both should be available through the same live provider path the
   product uses.

2. Prepare a workspace.

   If the external source points to code ownership, create or use a workspace
   where that owner file exists. The file exists only as retrievable workspace
   material; it is not passed as an internal hint.

3. Run the actual retrieval stage.

   Call the same retrieval surface the product uses, with normal LLM and
   connector configuration. The only semantic input should be the user prompt.

4. Assert connector participation.

   Verify the provider returned live documents, the relevant document was
   selected, and the wrong document was not selected.

5. Assert downstream resolution.

   If the relevant document identifies code ownership or another target, verify
   the retrieval result resolved that target through normal retrieval planning
   and evidence selection.

6. Run response generation.

   Use the normal response-generation path after retrieval. The response stage
   should receive the selected external-source evidence through the ordinary
   retrieval result, not through a test-only side channel.

7. Assert response traceability.

   Verify the response-generation request payload includes the selected
   external-source evidence ref, and the final response metadata records that
   evidence ref as used. The final prose does not need to quote the external
   source literally, but it should mention the resolved facts or relationships
   that came from that source.

8. Manually review generated prose.

   These tests may use Codex as the semantic reviewer. Codex should inspect the
   generated explanation and confirm that the source influenced the symptom ->
   evidence -> cause explanation, instead of merely appearing in retrieval
   metadata.

9. Assert failure visibility.

   Missing auth, missing indexes, connector failures, and empty provider results
   should fail clearly or skip behind an explicit live-test flag. They should not
   pass silently.

## What This Certifies

- the connector is configured and callable,
- live external documents are included in retrieval candidates,
- relevant external documents can affect retrieval,
- irrelevant but lexically similar documents can be filtered,
- external context can guide downstream workspace evidence selection,
- selected external evidence reaches response generation,
- final response metadata can trace generated content back to the external
  source that influenced it.

## What This Does Not Certify

- connector-specific ranking perfection,
- every possible provider schema.

Full answer quality is still partly semantic. Connector certs should run:

```text
prompt -> live retrieval -> response generation -> rendered/user-facing answer assertions
```

Automated checks should verify trace completeness. Codex can then manually judge
whether the generated explanation actually uses the connected source to explain
the symptom, evidence, and cause.

## Connector Examples

- Obsidian: live vault note search should find the good note and reject a wrong
  note with similar topic words.
- GitHub: configured repository issue or PR search should stay within the
  selected repo scope and reject unrelated issues.
- Notion: configured pages/databases should return live documents and reject
  stale or unrelated pages.
- Shortcut: configured stories should return live work items and reject
  unrelated planning artifacts.
