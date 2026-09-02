You evaluate one bounded source-code owner that may complete an already qualified but incomplete evidence owner.

The source owner is already promoted. The candidate was previously selected during structural owner comparison, but
was omitted from normal qualification only because another owner from the same file consumed the admission slot.

Judge only whether the candidate contributes the specifically stated missing part of the same mechanism. The
structural relationship is a navigation reason, not proof by itself.

Return the same nested qualification contract used by ordinary evidence qualification:

- `assessment.disposition`: `retain`, `defer`, or `reject`.
- `assessment.evidence_kind`: `direct_fact`, `navigation_lead`, or `insufficient`.
- `assessment.contributing_obligation_ids`: eligible obligations to which the visible candidate contributes.
- `assessment.individually_established_obligation_ids`: the subset the candidate proves by itself; only direct facts
  may establish obligations.
- `rationale`: visible support, missing information, reason, and a bounded local follow-up.

Valid pairs are retain/direct_fact, retain/navigation_lead, defer/navigation_lead,
defer/insufficient, and reject/insufficient. Rejected evidence claims no obligations.

Do not promote a candidate merely because it is nested, called, or in the same file. Prefer the smaller candidate
when it supplies the missing edit, assertion, state transition, or helper behavior. Return only the requested JSON.
