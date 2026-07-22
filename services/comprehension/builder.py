from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from core.models import EvidenceItem, RetrievalResult
from services.comprehension.models import (
    ArtifactReference,
    ComprehensionPlan,
    Concept,
    ConceptDependency,
    CoverageGap,
    DepthPolicy,
    ExplanationStep,
)


ROLE_LABELS = {
    "entry_or_parsing": "entry point or parsing",
    "input_parsing": "input parsing",
    "state_or_representation": "state or representation",
    "representation": "representation",
    "implementation_owner": "main implementation behavior",
    "validation_or_checking": "validation or checking",
    "validation_checking": "validation or checking",
    "diagnostic_or_error": "diagnostic or error behavior",
    "diagnostics": "diagnostics",
    "output_or_emission": "output or emission",
    "behavior_output": "behavior or output",
    "test_or_expected_behavior": "expected behavior",
    "supporting_context": "supporting context",
}

RELATIONS_BY_ROLE = {
    "entry_or_parsing": "feeds_into",
    "input_parsing": "feeds_into",
    "state_or_representation": "represented_by",
    "representation": "represented_by",
    "implementation_owner": "feeds_into",
    "validation_or_checking": "validated_by",
    "validation_checking": "validated_by",
    "diagnostic_or_error": "produces",
    "diagnostics": "produces",
    "output_or_emission": "produces",
    "behavior_output": "produces",
}


def build_comprehension_plan(
    *,
    user_prompt: str,
    retrieval_result: RetrievalResult,
    assistance_mode: str = "teach",
) -> ComprehensionPlan:
    evidence = tuple(retrieval_result.evidence[:8])
    artifacts = _artifacts_from_evidence(evidence)
    concepts = _concepts_from_evidence(evidence)
    dependencies = _dependencies_from_concepts(concepts)
    gaps = _coverage_gaps(retrieval_result.retrieval_summary, concepts)
    steps = _explanation_steps(concepts, artifacts, gaps)
    return ComprehensionPlan(
        task_goal=_task_goal(user_prompt, retrieval_result.retrieval_summary),
        answer_scope=_answer_scope(retrieval_result),
        assistance_mode=assistance_mode,
        relevant_artifacts=artifacts,
        concepts=concepts,
        concept_dependencies=dependencies,
        explanation_sequence=steps,
        depth_policy=_depth_policy(assistance_mode, concepts),
        understanding_check=None,
        coverage_gaps=gaps,
    )


def _artifacts_from_evidence(evidence: Sequence[EvidenceItem]) -> tuple[ArtifactReference, ...]:
    artifacts: list[ArtifactReference] = []
    for index, item in enumerate(evidence, start=1):
        metadata = dict(item.metadata)
        artifacts.append(
            ArtifactReference(
                id=f"a{index}",
                path=str(metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id),
                line_range=str(metadata.get("line_range") or _line_range_from_source_id(item.source_id)),
                role=str(metadata.get("coverage_area") or "supporting_context"),
                evidence_refs=(item.source_id,),
                claim_supported=str(metadata.get("claim_supported") or ""),
            )
        )
    return tuple(artifacts)


def _concepts_from_evidence(evidence: Sequence[EvidenceItem]) -> tuple[Concept, ...]:
    grouped: dict[str, list[EvidenceItem]] = {}
    for item in evidence:
        role = str(item.metadata.get("coverage_area") or "supporting_context").strip() or "supporting_context"
        grouped.setdefault(role, []).append(item)
    concepts: list[Concept] = []
    for role, items in grouped.items():
        concept_id = _concept_id(role)
        concept_role = "core" if _is_core_role(role, items) else "bridge"
        concepts.append(
            Concept(
                id=concept_id,
                name=ROLE_LABELS.get(role, role.replace("_", " ")),
                role=concept_role,
                description=_concept_description(role, items),
                evidence_refs=tuple(item.source_id for item in items[:4]),
                status="grounded",
                required_for_answer=concept_role == "core",
                suggested_depth="full" if concept_role == "core" else "capsule",
            )
        )
    return tuple(concepts)


def _dependencies_from_concepts(concepts: Sequence[Concept]) -> tuple[ConceptDependency, ...]:
    dependencies: list[ConceptDependency] = []
    ordered = [concept for concept in concepts if concept.role in {"core", "bridge"}]
    for left, right in zip(ordered, ordered[1:]):
        dependencies.append(
            ConceptDependency(
                source_concept_id=left.id,
                target_concept_id=right.id,
                relation=RELATIONS_BY_ROLE.get(right.id, "feeds_into"),
                evidence_refs=tuple(dict.fromkeys((*left.evidence_refs[:1], *right.evidence_refs[:1]))),
                status="inferred",
            )
        )
    return tuple(dependencies)


def _coverage_gaps(summary: Mapping[str, Any], concepts: Sequence[Concept]) -> tuple[CoverageGap, ...]:
    known_ids = {concept.id for concept in concepts}
    gaps: list[CoverageGap] = []
    for item in _coverage_gap_items(summary.get("coverage_gaps")):
        role = str(item.get("coverage_area") or "").strip()
        if not role:
            continue
        concept_id = _concept_id(role)
        if concept_id in known_ids:
            continue
        gaps.append(
            CoverageGap(
                concept_id=concept_id,
                description=str(item.get("reason_missing") or item.get("missing_reason") or "Evidence was not found for this concept."),
                severity="core" if role in {"implementation_owner", "validation_or_checking", "validation_checking"} else "bridge",
                retrieval_allowed=role not in {"supporting_context", "test_or_expected_behavior"},
            )
        )
    for bucket in _coverage_gap_items(summary.get("required_role_buckets")):
        role = str(bucket.get("role") or "").strip()
        status = str(bucket.get("role_status") or "").strip().lower()
        concept_id = _concept_id(role)
        if role and concept_id not in known_ids and status in {"missing", "weak"}:
            gaps.append(
                CoverageGap(
                    concept_id=concept_id,
                    description=str(bucket.get("missing_reason") or "Required role did not have strong evidence."),
                    severity="core",
                    retrieval_allowed=True,
                )
            )
    gate = summary.get("deterministic_coverage_gate")
    missing_roles = gate.get("missing_roles") if isinstance(gate, Mapping) else ()
    if isinstance(missing_roles, list):
        for role_value in missing_roles:
            role = str(role_value).strip()
            concept_id = _concept_id(role)
            if not role or concept_id in known_ids:
                continue
            gaps.append(
                CoverageGap(
                    concept_id=concept_id,
                    description="Deterministic coverage gate reported this responsibility as missing.",
                    severity="core",
                    retrieval_allowed=True,
                )
            )
    return tuple(_dedupe_gaps(gaps))


def _explanation_steps(
    concepts: Sequence[Concept],
    artifacts: Sequence[ArtifactReference],
    gaps: Sequence[CoverageGap],
) -> tuple[ExplanationStep, ...]:
    artifact_refs_by_role: dict[str, list[str]] = {}
    for artifact in artifacts:
        artifact_refs_by_role.setdefault(_concept_id(artifact.role), []).extend(artifact.evidence_refs)
    steps: list[ExplanationStep] = [
        ExplanationStep(
            concept_ids=tuple(concept.id for concept in concepts if concept.role == "core")[:3],
            artifact_refs=tuple(artifact.evidence_refs[0] for artifact in artifacts[:3] if artifact.evidence_refs),
            purpose="direct_answer",
            learning_objective="State the implementation path the learner should understand before using the evidence.",
        )
    ]
    for concept in concepts:
        steps.append(
            ExplanationStep(
                concept_ids=(concept.id,),
                artifact_refs=tuple(artifact_refs_by_role.get(concept.id, ()))[:4],
                purpose="mechanism" if concept.role == "core" else "connection",
                learning_objective=f"Explain how {concept.name} contributes to the answer.",
            )
        )
    if gaps:
        steps.append(
            ExplanationStep(
                concept_ids=tuple(gap.concept_id for gap in gaps[:3]),
                artifact_refs=(),
                purpose="limitation",
                learning_objective="Name missing evidence without filling the gap speculatively.",
            )
        )
    return tuple(step for step in steps if step.concept_ids or step.artifact_refs)


def _depth_policy(assistance_mode: str, concepts: Sequence[Concept]) -> DepthPolicy:
    core_count = sum(1 for concept in concepts if concept.role == "core")
    if assistance_mode == "work":
        return DepthPolicy(
            mode="silent_adaptation",
            assumption_statement="Use a concise implementation-focused answer and avoid blocking checks.",
            gate_required=False,
            rationale="Work mode should not force tutoring behavior.",
        )
    gate_required = core_count > 4
    return DepthPolicy(
        mode="concept_gate" if gate_required else "assumption_statement",
        assumption_statement="I will briefly explain the central code responsibilities and keep supporting concepts as short capsules.",
        gate_required=gate_required,
        rationale="Multiple core concepts may require an explicit depth choice." if gate_required else "The plan can proceed with bounded teaching depth.",
    )


def _task_goal(user_prompt: str, summary: Mapping[str, Any]) -> str:
    issue_analysis = summary.get("issue_analysis")
    if isinstance(issue_analysis, Mapping):
        requested = str(issue_analysis.get("requested_behavior") or "").strip()
        if requested:
            return requested[:500]
    prompt_summary = str(summary.get("prompt_summary") or "").strip()
    if prompt_summary:
        return prompt_summary[:500]
    normalized = re.sub(r"\s+", " ", user_prompt).strip()
    return normalized[:500] or "Understand the relevant code path."


def _answer_scope(retrieval_result: RetrievalResult) -> str:
    if retrieval_result.sufficient:
        return "Explain the code path supported by the selected evidence and mark inferred relationships explicitly."
    return "Explain the partial code path, emphasize coverage gaps, and avoid unsupported implementation claims."


def _concept_description(role: str, items: Sequence[EvidenceItem]) -> str:
    label = ROLE_LABELS.get(role, role.replace("_", " "))
    claims = [str(item.metadata.get("claim_supported") or "").strip() for item in items]
    claim = next((item for item in claims if item), "")
    if claim:
        return f"{label.capitalize()} is grounded by the selected artifact: {claim}"
    return f"{label.capitalize()} is represented by selected code evidence."


def _is_core_role(role: str, items: Sequence[EvidenceItem]) -> bool:
    if role in {"implementation_owner", "validation_or_checking", "validation_checking", "entry_or_parsing", "input_parsing"}:
        return True
    return any(str(item.metadata.get("relevance") or "").lower() == "primary" for item in items)


def _coverage_gap_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _dedupe_gaps(gaps: Sequence[CoverageGap]) -> list[CoverageGap]:
    output: list[CoverageGap] = []
    seen: set[str] = set()
    for gap in gaps:
        if gap.concept_id in seen:
            continue
        seen.add(gap.concept_id)
        output.append(gap)
    return output


def _concept_id(role: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", role.strip().lower().replace("-", "_")).strip("_") or "supporting_context"


def _path_from_source_id(source_id: str) -> str:
    if source_id.startswith("workspace:"):
        return source_id[len("workspace:") :].split(":L", 1)[0]
    if source_id.startswith("repo-pre:"):
        return source_id[len("repo-pre:") :].split(":L", 1)[0]
    return ""


def _line_range_from_source_id(source_id: str) -> str:
    match = re.search(r":L(?P<start>\d+)(?:-L(?P<end>\d+))?$", source_id)
    if match is None:
        return ""
    start = match.group("start")
    end = match.group("end")
    return f"L{start}-L{end}" if end else f"L{start}"
