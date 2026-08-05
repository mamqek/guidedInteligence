from __future__ import annotations

# Owns small protocol-relationship query helpers used by synthesis bridging. Do not place graph discovery execution, role retrieval, or candidate validation here.

from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import ordered_unique


def protocol_relationship_seed_texts(retrieval_plan: WorkspaceRetrievalPlan | None) -> tuple[str, ...]:
    if retrieval_plan is None:
        return ()
    values: list[str] = [
        retrieval_plan.raw_prompt,
        retrieval_plan.prompt_summary,
        *retrieval_plan.raw_prompt_evidence,
        *retrieval_plan.retrieval_terms,
        *retrieval_plan.surface_context_terms,
        *retrieval_plan.owner_artifact_terms,
        *retrieval_plan.llm_concept_terms,
        *retrieval_plan.speculative_entities,
    ]
    values.extend(subquery.query for subquery in retrieval_plan.llm_subqueries)
    values.extend(subquery.query for subquery in retrieval_plan.owner_subqueries)
    values.extend(subquery.query for subquery in retrieval_plan.support_subqueries)
    return ordered_unique(value for value in values if value and value.strip())
