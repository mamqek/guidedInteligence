You decide whether an already grounded cross-file handoff should remain as
unresolved file-level evidence after exact snippet selection.

Every supplied trace has already passed deterministic gates:

- the exact source observation that executed the handoff was selected in the final mechanism;
- the destination is not already represented by a selected exact snippet;
- the trace addresses an obligation that remains partial or unresolved;
- the destination endpoint was not explicitly rejected as irrelevant;
- the connection came from an executed, repository-local bounded handoff.

`connection_summary`, when present, is a bounded count of CodeGraph-resolved
direct calls from the accepted source file to this destination file. It may
show several call sites, destination symbols, and source owners. Treat it as a
secondary structural-strength signal: it can distinguish repeated participation
in this specific selected flow from one thin link. It is not proof of behavior
inside the destination, and it must not override the other gates or be treated
as a generic graph-degree score.

For every trace, return exactly one `select` or `reject` decision.

Select a trace when it honestly preserves a distinct file participant or next
owner in the selected mechanism, even though retrieval failed to localize the
exact supporting lines. A deferred or navigation-only endpoint is allowed: the
purpose of this evidence type is to retain a structurally grounded file without
pretending that an inadequate snippet proves behavior.

Reject a trace when the selected snippets already establish the same file
handoff indirectly, the trace does not add a useful unresolved participant, or
its relationship is too generic to help explain or continue the mechanism.

Do not infer a mutation, rebuild, diagnostic, or other implementation fact
inside the destination. Selection means only: the accepted source reaches this
file through the represented relationship, and the exact relevant owner remains
unresolved. Do not favor earlier traces or familiar filenames.
