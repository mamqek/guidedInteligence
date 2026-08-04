from __future__ import annotations

# Owns small protocol-relationship query helpers used by synthesis bridging. Do not place graph discovery execution, role retrieval, or candidate validation here.

from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import ordered_unique


def cypher_relative_path(path: str) -> str:
    return path.replace("/", "\\")


def cypher_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


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


def anchor_symbol_relation_query(anchor_path: str, candidate_path: str) -> str:
    # TECH DEBT: This is textual substring matching, not a verified symbol-reference edge.
    # Replace it with native CGC/SCIP relationships before reusing or extending this path.
    anchor_value = cypher_string(cypher_relative_path(anchor_path))
    candidate_value = cypher_string(candidate_path)
    return (
        "MATCH (fa:File)-[:CONTAINS]->(fn:Function), (fc:File)-[:CONTAINS]->(decl) "
        f"WHERE fa.relative_path = '{anchor_value}' "
        f"AND fc.relative_path = '{candidate_value}' "
        "AND fn.source IS NOT NULL "
        "AND decl.name IS NOT NULL "
        "AND fn.source CONTAINS decl.name "
        "RETURN DISTINCT decl.name AS shared_symbol, fn.name AS anchor_function, fn.line_number AS anchor_line "
        "LIMIT 25"
    )


def is_structural_symbol_name(value: str) -> bool:
    return len(value) >= 5 and value[:1].isupper()
