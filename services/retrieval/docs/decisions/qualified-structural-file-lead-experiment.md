# Qualified structural file-lead experiment (deferred)

## Hypothesis

A semantically qualified source owner can expose an exact owner-qualified call into a file that initial retrieval did
not admit. That call should create an unqualified structural lead for later inspection without inheriting semantic
support from the caller.

Example shape:

```text
qualified builder.ts owner
  -> exact call BuilderState.updateShapeSignature
  -> target file builderState.ts
  -> preferred target updateShapeSignature
  -> later typed inspection
  -> ordinary source qualification
```

## Proposed first experiment

- Create the lead only from visible, semantically qualified source and an exact owner-qualified call.
- Resolve and retain the target file, exact target node, source candidate, supported obligation, and call-site
  provenance.
- Promote the lead into the controller's eligible and prioritized inspection frontier; do not alter the target file's
  earlier Qdrant/file-admission rank and do not create an evidence candidate yet.
- Let the typed controller action inspect the exact target first, then another owner in the same file only when the
  exact target is unavailable or insufficient.
- Route the action through existing typed validation, novelty suppression, scheduler accounting, and trace logging.
- Qualify disclosed target source normally. No support is inherited from the caller.

This intentionally bypasses the completed initial owner-comparison boundary rather than trying to keep the target file
alive inside it. A pre-comparison file-rank boost would act on unqualified source, increase the comparison payload, and
make high-fan-out utilities substantially more dangerous. The later qualified lead is therefore expected to have
higher precision but one-round latency and possible competition for bounded controller actions. The experiment must
measure whether prioritized scheduling reliably offsets that latency before considering an earlier admission boost.

## Utility and role controls

Candidate suppression should use measurable properties such as distinct calling files, distinct calling owners,
target-node indegree, qualifier-wide fan-out, repository calling proportion, and whether a qualifier exposes many
unrelated members. Tests remain eligible, but their qualified obligation support and later target qualification keep
them within the evidence role they actually establish.

## Status

Recorded for a later isolated experiment. No implementation is active.
