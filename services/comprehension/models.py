from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


ConceptRole = Literal["core", "bridge", "assumed", "boundary"]
ConceptStatus = Literal["grounded", "inferred"]
ConceptDepth = Literal["full", "capsule", "mention", "omit"]
DependencyRelation = Literal["requires", "feeds_into", "validated_by", "represented_by", "produces"]
StepPurpose = Literal["direct_answer", "mechanism", "evidence", "prerequisite", "connection", "limitation"]
CheckType = Literal["prediction", "re_explanation", "trace", "why", "transfer"]
FamiliarityLevel = Literal["unknown", "claimed_known", "demonstrated", "partial", "misunderstood"]
RepairStrategy = Literal["concept_capsule", "contrast", "smaller_example", "worked_example", "evidence_revisit"]


@dataclass(frozen=True)
class ArtifactReference:
    id: str
    path: str
    line_range: str
    role: str
    evidence_refs: tuple[str, ...]
    claim_supported: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "line_range": self.line_range,
            "role": self.role,
            "evidence_refs": list(self.evidence_refs),
            "claim_supported": self.claim_supported,
        }


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    role: ConceptRole
    description: str
    evidence_refs: tuple[str, ...]
    status: ConceptStatus
    required_for_answer: bool
    suggested_depth: ConceptDepth

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "evidence_refs": list(self.evidence_refs),
            "status": self.status,
            "required_for_answer": self.required_for_answer,
            "suggested_depth": self.suggested_depth,
        }


@dataclass(frozen=True)
class ConceptDependency:
    source_concept_id: str
    target_concept_id: str
    relation: DependencyRelation
    evidence_refs: tuple[str, ...] = ()
    status: ConceptStatus = "inferred"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_concept_id": self.source_concept_id,
            "target_concept_id": self.target_concept_id,
            "relation": self.relation,
            "evidence_refs": list(self.evidence_refs),
            "status": self.status,
        }


@dataclass(frozen=True)
class ExplanationStep:
    concept_ids: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    purpose: StepPurpose
    learning_objective: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_ids": list(self.concept_ids),
            "artifact_refs": list(self.artifact_refs),
            "purpose": self.purpose,
            "learning_objective": self.learning_objective,
        }


@dataclass(frozen=True)
class DepthPolicy:
    mode: str
    assumption_statement: str
    gate_required: bool = False
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "assumption_statement": self.assumption_statement,
            "gate_required": self.gate_required,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class PlanUnderstandingCheck:
    id: str
    type: CheckType
    question: str
    expected_points: tuple[str, ...]
    misconceptions: tuple[str, ...]
    hidden_hints: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    concept_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "question": self.question,
            "expected_points": list(self.expected_points),
            "misconceptions": list(self.misconceptions),
            "hidden_hints": list(self.hidden_hints),
            "evidence_refs": list(self.evidence_refs),
            "concept_ids": list(self.concept_ids),
        }


@dataclass(frozen=True)
class CoverageGap:
    concept_id: str
    description: str
    severity: Literal["core", "bridge", "optional"]
    retrieval_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "description": self.description,
            "severity": self.severity,
            "retrieval_allowed": self.retrieval_allowed,
        }


@dataclass(frozen=True)
class ComprehensionPlan:
    task_goal: str
    answer_scope: str
    assistance_mode: str
    relevant_artifacts: tuple[ArtifactReference, ...]
    concepts: tuple[Concept, ...]
    concept_dependencies: tuple[ConceptDependency, ...]
    explanation_sequence: tuple[ExplanationStep, ...]
    depth_policy: DepthPolicy
    understanding_check: PlanUnderstandingCheck | None
    coverage_gaps: tuple[CoverageGap, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_goal": self.task_goal,
            "answer_scope": self.answer_scope,
            "assistance_mode": self.assistance_mode,
            "relevant_artifacts": [artifact.to_dict() for artifact in self.relevant_artifacts],
            "concepts": [concept.to_dict() for concept in self.concepts],
            "concept_dependencies": [dependency.to_dict() for dependency in self.concept_dependencies],
            "explanation_sequence": [step.to_dict() for step in self.explanation_sequence],
            "depth_policy": self.depth_policy.to_dict(),
            "understanding_check": self.understanding_check.to_dict() if self.understanding_check is not None else None,
            "coverage_gaps": [gap.to_dict() for gap in self.coverage_gaps],
        }


@dataclass(frozen=True)
class ConceptFamiliarity:
    concept_id: str
    level: FamiliarityLevel
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "level": self.level,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class RepairPlan:
    failed_concept_ids: tuple[str, ...]
    misconception: str
    repair_strategy: RepairStrategy
    follow_up_check: PlanUnderstandingCheck | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "failed_concept_ids": list(self.failed_concept_ids),
            "misconception": self.misconception,
            "repair_strategy": self.repair_strategy,
            "follow_up_check": self.follow_up_check.to_dict() if self.follow_up_check is not None else None,
        }


@dataclass(frozen=True)
class ComprehensionState:
    concepts_explained: tuple[str, ...]
    concept_familiarity: tuple[ConceptFamiliarity, ...]
    checks_asked: tuple[str, ...]
    check_results: tuple[Mapping[str, Any], ...]
    current_teaching_stage: str
    repair_plan: RepairPlan | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "concepts_explained": list(self.concepts_explained),
            "concept_familiarity": [item.to_dict() for item in self.concept_familiarity],
            "checks_asked": list(self.checks_asked),
            "check_results": [dict(item) for item in self.check_results],
            "current_teaching_stage": self.current_teaching_stage,
            "repair_plan": self.repair_plan.to_dict() if self.repair_plan is not None else None,
        }


def plan_from_mapping(value: Mapping[str, Any]) -> ComprehensionPlan:
    artifacts = tuple(
        ArtifactReference(
            id=str(item.get("id") or ""),
            path=str(item.get("path") or ""),
            line_range=str(item.get("line_range") or ""),
            role=str(item.get("role") or ""),
            evidence_refs=tuple(str(ref) for ref in item.get("evidence_refs", ()) if str(ref).strip()),
            claim_supported=str(item.get("claim_supported") or ""),
        )
        for item in _mapping_items(value.get("relevant_artifacts"))
    )
    concepts = tuple(
        Concept(
            id=str(item.get("id") or ""),
            name=str(item.get("name") or ""),
            role=_literal(str(item.get("role") or "bridge"), {"core", "bridge", "assumed", "boundary"}, "bridge"),
            description=str(item.get("description") or ""),
            evidence_refs=tuple(str(ref) for ref in item.get("evidence_refs", ()) if str(ref).strip()),
            status=_literal(str(item.get("status") or "inferred"), {"grounded", "inferred"}, "inferred"),
            required_for_answer=bool(item.get("required_for_answer", False)),
            suggested_depth=_literal(str(item.get("suggested_depth") or "capsule"), {"full", "capsule", "mention", "omit"}, "capsule"),
        )
        for item in _mapping_items(value.get("concepts"))
    )
    dependencies = tuple(
        ConceptDependency(
            source_concept_id=str(item.get("source_concept_id") or ""),
            target_concept_id=str(item.get("target_concept_id") or ""),
            relation=_literal(
                str(item.get("relation") or "feeds_into"),
                {"requires", "feeds_into", "validated_by", "represented_by", "produces"},
                "feeds_into",
            ),
            evidence_refs=tuple(str(ref) for ref in item.get("evidence_refs", ()) if str(ref).strip()),
            status=_literal(str(item.get("status") or "inferred"), {"grounded", "inferred"}, "inferred"),
        )
        for item in _mapping_items(value.get("concept_dependencies"))
    )
    steps = tuple(
        ExplanationStep(
            concept_ids=tuple(str(ref) for ref in item.get("concept_ids", ()) if str(ref).strip()),
            artifact_refs=tuple(str(ref) for ref in item.get("artifact_refs", ()) if str(ref).strip()),
            purpose=_literal(
                str(item.get("purpose") or "mechanism"),
                {"direct_answer", "mechanism", "evidence", "prerequisite", "connection", "limitation"},
                "mechanism",
            ),
            learning_objective=str(item.get("learning_objective") or ""),
        )
        for item in _mapping_items(value.get("explanation_sequence"))
    )
    depth_raw = value.get("depth_policy") if isinstance(value.get("depth_policy"), Mapping) else {}
    check_raw = value.get("understanding_check") if isinstance(value.get("understanding_check"), Mapping) else None
    gaps = tuple(
        CoverageGap(
            concept_id=str(item.get("concept_id") or ""),
            description=str(item.get("description") or ""),
            severity=_literal(str(item.get("severity") or "optional"), {"core", "bridge", "optional"}, "optional"),
            retrieval_allowed=bool(item.get("retrieval_allowed", False)),
        )
        for item in _mapping_items(value.get("coverage_gaps"))
    )
    return ComprehensionPlan(
        task_goal=str(value.get("task_goal") or ""),
        answer_scope=str(value.get("answer_scope") or ""),
        assistance_mode=str(value.get("assistance_mode") or "teach"),
        relevant_artifacts=artifacts,
        concepts=concepts,
        concept_dependencies=dependencies,
        explanation_sequence=steps,
        depth_policy=DepthPolicy(
            mode=str(depth_raw.get("mode") or "assumption_statement"),
            assumption_statement=str(depth_raw.get("assumption_statement") or ""),
            gate_required=bool(depth_raw.get("gate_required", False)),
            rationale=str(depth_raw.get("rationale") or ""),
        ),
        understanding_check=_check_from_mapping(check_raw) if check_raw is not None else None,
        coverage_gaps=gaps,
    )


def _check_from_mapping(value: Mapping[str, Any]) -> PlanUnderstandingCheck:
    return PlanUnderstandingCheck(
        id=str(value.get("id") or "q1"),
        type=_literal(
            str(value.get("type") or "why"),
            {"prediction", "re_explanation", "trace", "why", "transfer"},
            "why",
        ),
        question=str(value.get("question") or ""),
        expected_points=tuple(str(item) for item in value.get("expected_points", ()) if str(item).strip()),
        misconceptions=tuple(str(item) for item in value.get("misconceptions", ()) if str(item).strip()),
        hidden_hints=tuple(str(item) for item in value.get("hidden_hints", ()) if str(item).strip()),
        evidence_refs=tuple(str(item) for item in value.get("evidence_refs", ()) if str(item).strip()),
        concept_ids=tuple(str(item) for item in value.get("concept_ids", ()) if str(item).strip()),
    )


def _mapping_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _literal(value: str, allowed: set[str], default: str) -> Any:
    return value if value in allowed else default
