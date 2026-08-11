from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from statistics import mean
import sys
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.retrieval.workspace.bm25 import file_role


PRODUCTIVE_EDGE_KINDS = {
    "calls",
    "references",
    "imports",
    "file_dependency",
    "implements",
    "extends",
    "overrides",
    "instantiates",
}
ACTION_TERMS = {
    "affect",
    "apply",
    "arithmetic",
    "binop",
    "build",
    "change",
    "compute",
    "emit",
    "handle",
    "invalidate",
    "parse",
    "propagate",
    "render",
    "resolve",
    "serialize",
    "set",
    "transform",
    "update",
    "visit",
}
STOP_TERMS = {
    "about",
    "after",
    "also",
    "and",
    "code",
    "establish",
    "explain",
    "file",
    "from",
    "how",
    "identify",
    "into",
    "must",
    "repository",
    "source",
    "that",
    "the",
    "this",
    "through",
    "what",
    "when",
    "where",
    "with",
}
EXECUTABLE_KINDS = {"function", "method", "constructor"}
OBLIGATION_PATTERN = re.compile(r"obligation\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)


def _terms(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
    return {
        token
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expanded.casefold())
        if len(token) >= 3 and token not in STOP_TERMS
    }


def _obligation(reason: str) -> str:
    match = OBLIGATION_PATTERN.search(str(reason))
    return match.group(1).rstrip(".") if match else "unscoped"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _items(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


@dataclass
class CandidateSignals:
    path: str
    obligations: set[str] = field(default_factory=set)
    queries: list[str] = field(default_factory=list)
    hybrid_ranks: list[int] = field(default_factory=list)
    initial_hybrid_ranks: list[int] = field(default_factory=list)
    dense_ranks: list[int] = field(default_factory=list)
    sparse_ranks: list[int] = field(default_factory=list)
    hybrid_scores: list[float] = field(default_factory=list)
    matched_terms: set[str] = field(default_factory=set)
    texts: list[str] = field(default_factory=list)
    node_ids: set[str] = field(default_factory=set)
    node_names: set[str] = field(default_factory=set)
    node_kinds: set[str] = field(default_factory=set)
    edge_kinds: set[str] = field(default_factory=set)
    inbound_edges: int = 0
    outbound_edges: int = 0
    inbound_productive: int = 0
    outbound_productive: int = 0
    inbound_productive_edges: set[str] = field(default_factory=set)
    outbound_productive_edges: set[str] = field(default_factory=set)
    neighbor_paths: set[str] = field(default_factory=set)

    def observe_qdrant(
        self,
        *,
        obligation: str,
        query: str,
        channel: str,
        rank: int,
        item: Mapping[str, Any],
        initial_search: bool = False,
    ) -> None:
        self.obligations.add(obligation)
        if query:
            self.queries.append(query)
        getattr(self, f"{channel}_ranks").append(rank)
        if channel == "hybrid":
            self.hybrid_scores.append(float(item.get("score") or 0.0))
            if initial_search:
                self.initial_hybrid_ranks.append(rank)
        self.matched_terms.update(str(term).casefold() for term in item.get("matched_terms", ()) if term)
        text = str(item.get("text") or "")
        if text:
            self.texts.append(text)

    def observe_node(self, *, obligation: str, node: Mapping[str, Any]) -> None:
        self.obligations.add(obligation)
        node_id = str(node.get("id") or "")
        name = str(node.get("qualified_name") or node.get("name") or "")
        kind = str(node.get("kind") or "").casefold()
        if node_id:
            self.node_ids.add(node_id)
        if name:
            self.node_names.add(name)
        if kind:
            self.node_kinds.add(kind)

    @property
    def semantic_channels(self) -> int:
        return sum(bool(values) for values in (self.hybrid_ranks, self.dense_ranks, self.sparse_ranks))

    @property
    def semantic_present(self) -> bool:
        return self.semantic_channels > 0

    @property
    def graph_present(self) -> bool:
        return bool(self.node_ids or self.edge_kinds)

    @property
    def executable(self) -> bool:
        return bool(self.node_kinds & EXECUTABLE_KINDS) or any(
            re.search(r"\b(?:def|function)\s+[A-Za-z_$]|=>|\breturn\b", text)
            for text in self.texts
        )

    @property
    def action_symbol_terms(self) -> int:
        return max((len(_terms(name) & ACTION_TERMS) for name in self.node_names), default=0)

    @property
    def query_symbol_overlap(self) -> int:
        query_terms = set().union(*(_terms(query) for query in self.queries)) if self.queries else set()
        symbol_terms = set().union(*(_terms(name) for name in self.node_names)) if self.node_names else set()
        return len(query_terms & symbol_terms)

    @property
    def mutation_text(self) -> bool:
        return any(
            re.search(r"(?:\.[A-Za-z_$][A-Za-z0-9_$]*\s*=|\bset\s*\(|\.set\s*\(|\.add\s*\(|\.update\s*\()", text)
            for text in self.texts
        )

    def feature_values(self) -> dict[str, float]:
        return {
            "semantic_channels": float(self.semantic_channels),
            "hybrid_present": float(bool(self.hybrid_ranks)),
            "best_hybrid_inverse_rank": 1.0 / min(self.hybrid_ranks) if self.hybrid_ranks else 0.0,
            "graph_present": float(self.graph_present),
            "semantic_graph_corroborated": float(self.semantic_present and self.graph_present),
            "obligation_recurrence": float(len(self.obligations)),
            "executable": float(self.executable),
            "action_symbol_terms": float(self.action_symbol_terms),
            "query_symbol_overlap": float(self.query_symbol_overlap),
            "mutation_text": float(self.mutation_text),
            "outbound_productive": float(self.outbound_productive),
            "inbound_productive": float(self.inbound_productive),
            "unique_outbound_productive": float(len(self.outbound_productive_edges)),
            "unique_inbound_productive": float(len(self.inbound_productive_edges)),
            "bidirectional_productive": float(self.outbound_productive > 0 and self.inbound_productive > 0),
            "cross_file_fanout": float(len(self.neighbor_paths)),
        }


@dataclass(frozen=True)
class RunAudit:
    run_dir: Path
    case_id: str
    run_id: str
    oracle_files: frozenset[str]
    selected_files: frozenset[str]
    candidates: Mapping[str, CandidateSignals]
    initial_queries: Mapping[str, str]
    obligation_boundaries: Mapping[str, tuple[str, str]]


def _load_events(path: Path) -> list[Mapping[str, Any]]:
    return [
        value
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and isinstance((value := json.loads(line)), Mapping)
    ]


def audit_run(run_dir: Path) -> RunAudit:
    comparison = json.loads((run_dir / "evaluator-comparison.json").read_text(encoding="utf-8"))
    retrieval_plan = json.loads((run_dir / "retrieval-plan.json").read_text(encoding="utf-8"))
    candidates: dict[str, CandidateSignals] = {}
    initial_queries: dict[str, str] = {}

    def candidate(path: str) -> CandidateSignals:
        normalized = path.replace("\\", "/")
        return candidates.setdefault(normalized, CandidateSignals(normalized))

    pending_request: Mapping[str, Any] | None = None
    for event in _load_events(run_dir / "retrieval-trace.jsonl"):
        event_type = str(event.get("event_type") or "")
        payload = _mapping(event.get("payload"))
        if event_type == "tool_call_requested":
            pending_request = payload
            continue
        if event_type != "tool_observation_created" or pending_request is None:
            continue
        tool_name = str(pending_request.get("tool_name") or "")
        reason = str(pending_request.get("reason") or "")
        obligation = _obligation(reason)
        arguments = _mapping(pending_request.get("arguments"))
        observation = _mapping(payload.get("payload"))
        if tool_name == "qdrant_hybrid_search":
            query = str(arguments.get("query") or "")
            initial_search = reason.startswith("Find conceptual anchors for evidence obligation ")
            if initial_search:
                initial_queries[obligation] = query
            breakdown = _mapping(observation.get("breakdown"))
            channels = {
                "hybrid": _items(observation.get("results")),
                "dense": _items(breakdown.get("dense")),
                "sparse": _items(breakdown.get("sparse")),
            }
            for channel, values in channels.items():
                for rank, item in enumerate(values, start=1):
                    path = str(item.get("path") or "")
                    if path:
                        candidate(path).observe_qdrant(
                            obligation=obligation,
                            query=query,
                            channel=channel,
                            rank=rank,
                            item=item,
                            initial_search=initial_search,
                        )
        if tool_name.startswith("structural_"):
            for node in _items(observation.get("nodes")):
                path = str(node.get("path") or "")
                if path:
                    candidate(path).observe_node(obligation=obligation, node=node)
            for edge in _items(observation.get("edges")):
                kind = str(edge.get("kind") or edge.get("edge_kind") or "related")
                source = _mapping(edge.get("source"))
                target = _mapping(edge.get("target"))
                source_path = str(source.get("path") or "")
                target_path = str(target.get("path") or "")
                edge_key = "|".join(
                    (
                        kind,
                        str(source.get("id") or source_path),
                        str(target.get("id") or target_path),
                    )
                )
                if source_path:
                    source_candidate = candidate(source_path)
                    source_candidate.observe_node(obligation=obligation, node=source)
                    source_candidate.edge_kinds.add(kind)
                    source_candidate.outbound_edges += 1
                    source_candidate.outbound_productive += int(kind in PRODUCTIVE_EDGE_KINDS)
                    if kind in PRODUCTIVE_EDGE_KINDS:
                        source_candidate.outbound_productive_edges.add(edge_key)
                    if target_path and target_path != source_path:
                        source_candidate.neighbor_paths.add(target_path)
                if target_path:
                    target_candidate = candidate(target_path)
                    target_candidate.observe_node(obligation=obligation, node=target)
                    target_candidate.edge_kinds.add(kind)
                    target_candidate.inbound_edges += 1
                    target_candidate.inbound_productive += int(kind in PRODUCTIVE_EDGE_KINDS)
                    if kind in PRODUCTIVE_EDGE_KINDS:
                        target_candidate.inbound_productive_edges.add(edge_key)
                    if source_path and source_path != target_path:
                        target_candidate.neighbor_paths.add(source_path)
        pending_request = None

    oracle_files = frozenset(str(path).replace("\\", "/") for path in comparison["oracle_implementation_files"])
    selected_files = frozenset(str(path).replace("\\", "/") for path in comparison["retrieved_source_files"])
    obligation_boundaries = {
        str(item.get("id") or ""): (
            str(item.get("evidence_source") or ""),
            str(item.get("evidence_boundary") or ""),
        )
        for item in retrieval_plan.get("obligations", ())
        if isinstance(item, Mapping) and str(item.get("id") or "")
    }
    # Selected evidence must have been a candidate even if a historical trace
    # omitted the event that introduced it. Oracle-only paths are deliberately
    # not injected: doing so would leak unavailable answers into replay ranks.
    for path in selected_files:
        candidate(path)
    return RunAudit(
        run_dir=run_dir,
        case_id=str(comparison["case_id"]),
        run_id=run_dir.name,
        oracle_files=oracle_files,
        selected_files=selected_files,
        candidates=candidates,
        initial_queries=initial_queries,
        obligation_boundaries=obligation_boundaries,
    )


def _rankings(audit: RunAudit) -> dict[str, list[str]]:
    candidates = list(audit.candidates.values())
    return {
        "hybrid": [
            item.path
            for item in sorted(
                candidates,
                key=lambda item: (
                    min(item.hybrid_ranks) if item.hybrid_ranks else 10**9,
                    -max(item.hybrid_scores, default=0.0),
                    item.path,
                ),
            )
        ],
        "corroboration": [
            item.path
            for item in sorted(
                candidates,
                key=lambda item: (
                    -int(item.semantic_present and item.graph_present),
                    -item.semantic_channels,
                    -len(item.obligations),
                    -int(item.executable),
                    min(item.hybrid_ranks) if item.hybrid_ranks else 10**9,
                    item.path,
                ),
            )
        ],
        "responsibility": [
            item.path
            for item in sorted(
                candidates,
                key=lambda item: (
                    -item.action_symbol_terms,
                    -int(item.mutation_text),
                    -item.query_symbol_overlap,
                    -int(item.executable),
                    -int(item.semantic_present and item.graph_present),
                    -len(item.obligations),
                    len(item.neighbor_paths),
                    item.path,
                ),
            )
        ],
        "chain": [
            item.path
            for item in sorted(
                candidates,
                key=lambda item: (
                    -int(item.executable and item.outbound_productive > 0),
                    -int(item.outbound_productive > 0 and item.inbound_productive > 0),
                    -item.action_symbol_terms,
                    -int(item.semantic_present and item.graph_present),
                    -len(item.obligations),
                    len(item.neighbor_paths),
                    min(item.hybrid_ranks) if item.hybrid_ranks else 10**9,
                    item.path,
                ),
            )
        ],
    }


def _recall_at(paths: Sequence[str], oracle: frozenset[str], limit: int) -> float:
    if not oracle:
        return 0.0
    return len(set(paths[:limit]) & oracle) / len(oracle)


def _first_oracle_rank(paths: Sequence[str], oracle: frozenset[str]) -> int | None:
    return next((index for index, path in enumerate(paths, start=1) if path in oracle), None)


def protected_implementation_pool(
    audit: RunAudit,
    *,
    per_obligation_hybrid_rank: int = 12,
    limit: int = 24,
) -> tuple[str, ...]:
    """Keep direct semantic owner files before graph/component shortlisting.

    Oracle labels are deliberately absent from this policy. They are used only
    by the report to measure how much owner evidence the pool preserves.
    """
    eligible = [
        candidate
        for candidate in audit.candidates.values()
        if file_role(candidate.path) == "implementation"
        and candidate.initial_hybrid_ranks
        and min(candidate.initial_hybrid_ranks) <= per_obligation_hybrid_rank
    ]
    return tuple(
        candidate.path
        for candidate in sorted(
            eligible,
            key=lambda candidate: (
                min(candidate.initial_hybrid_ranks),
                -len(candidate.obligations),
                -candidate.semantic_channels,
                candidate.path,
            ),
        )[:limit]
    )


def _feature_rows(audits: Sequence[RunAudit]) -> list[tuple[str, float, float, float]]:
    oracle_values: dict[str, list[float]] = defaultdict(list)
    other_values: dict[str, list[float]] = defaultdict(list)
    for audit in audits:
        for path, candidate in audit.candidates.items():
            target = oracle_values if path in audit.oracle_files else other_values
            for name, value in candidate.feature_values().items():
                target[name].append(value)
    rows = []
    for name in sorted(set(oracle_values) | set(other_values)):
        oracle_mean = mean(oracle_values[name]) if oracle_values[name] else 0.0
        other_mean = mean(other_values[name]) if other_values[name] else 0.0
        rows.append((name, oracle_mean, other_mean, oracle_mean - other_mean))
    return sorted(rows, key=lambda row: abs(row[3]), reverse=True)


def render_report(audits: Sequence[RunAudit]) -> str:
    lines = [
        "# Offline Shortlist Signal Audit",
        "",
        "Historical traces do not contain the later `obligation_candidate_shortlists_created` event. ",
        "This audit reconstructs a file/obligation candidate universe from Qdrant hybrid/dense/sparse results ",
        "and CodeGraph nodes/edges; it does not claim byte-for-byte replay of the historical shortlist.",
        "",
        "## Run coverage",
        "",
        "| Case | Run | Candidate files | Oracle implementation files observed | Selected Oracle files |",
        "|---|---|---:|---:|---:|",
    ]
    for audit in audits:
        observed = set(audit.candidates) & audit.oracle_files
        selected = audit.selected_files & audit.oracle_files
        lines.append(
            f"| `{audit.case_id}` | `{audit.run_id}` | {len(audit.candidates)} | "
            f"{len(observed)}/{len(audit.oracle_files)} | {len(selected)} |"
        )

    lines.extend(
        [
            "",
            "## Matched owner-survival pool",
            "",
            "This comparison asks whether a causal source-owner Oracle file survives while competing against actual files from the same run. The policy uses no Oracle labels: retain every `implementation` file appearing within the top 12 hybrid results of at least one initial obligation, deduplicate across obligations, and cap the request-level pool at 24 files.",
            "",
            "| Case | Run | Pool files | Source-owner Oracles retained | Retained owner paths |",
            "|---|---|---:|---:|---|",
        ]
    )
    for audit in audits:
        pool = set(protected_implementation_pool(audit))
        owner_oracles = {
            path for path in audit.oracle_files if file_role(path) == "implementation"
        }
        retained = sorted(pool & owner_oracles)
        lines.append(
            f"| `{audit.case_id}` | `{audit.run_id}` | {len(pool)} | "
            f"{len(retained)}/{len(owner_oracles)} | "
            f"{', '.join(f'`{path}`' for path in retained) if retained else 'none'} |"
        )

    lines.extend(
        [
            "",
            "## Intent-to-query drift",
            "",
            "The first intent choice may be unchanged while the stage-requirement LLM changes proposition text or evidence boundary.",
            "",
            "| Case | Runs | Repository queries | Boundary/source changes | Shared query obligations | Exact queries | Mean token Jaccard |",
            "|---|---|---:|---|---:|---:|---:|",
        ]
    )
    by_case: dict[str, list[RunAudit]] = defaultdict(list)
    for audit in audits:
        by_case[audit.case_id].append(audit)
    for case_id, case_audits in sorted(by_case.items()):
        if len(case_audits) != 2:
            continue
        left, right = sorted(case_audits, key=lambda item: item.run_id)
        obligation_ids = set(left.obligation_boundaries) | set(right.obligation_boundaries)
        boundary_changes = [
            obligation_id
            for obligation_id in sorted(obligation_ids)
            if left.obligation_boundaries.get(obligation_id) != right.obligation_boundaries.get(obligation_id)
        ]
        shared_queries = sorted(set(left.initial_queries) & set(right.initial_queries))
        exact_queries = sum(left.initial_queries[item] == right.initial_queries[item] for item in shared_queries)
        similarities = []
        for obligation_id in shared_queries:
            left_terms = _terms(left.initial_queries[obligation_id])
            right_terms = _terms(right.initial_queries[obligation_id])
            similarities.append(
                len(left_terms & right_terms) / len(left_terms | right_terms)
                if left_terms or right_terms
                else 1.0
            )
        lines.append(
            f"| `{case_id}` | `{left.run_id}` / `{right.run_id}` | "
            f"{len(left.initial_queries)} / {len(right.initial_queries)} | "
            f"{', '.join(boundary_changes) if boundary_changes else 'none'} | "
            f"{len(shared_queries)} | {exact_queries} | "
            f"{mean(similarities):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Feature means",
            "",
            "Oracle labels are used only for this evaluation table.",
            "",
            "| Feature | Oracle mean | Non-Oracle mean | Difference |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, oracle_mean, other_mean, difference in _feature_rows(audits):
        lines.append(f"| `{name}` | {oracle_mean:.3f} | {other_mean:.3f} | {difference:+.3f} |")

    lines.extend(
        [
            "",
            "## Oracle candidate diagnostics",
            "",
            "| Case | Run | Oracle path | Selected | Channels | Hybrid rank | Obligations | Query/symbol overlap | Action terms | Unique out/in | Fanout | Hybrid/corroboration/responsibility/chain ranks |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for audit in audits:
        rankings = _rankings(audit)
        rank_maps = {
            policy: {path: index for index, path in enumerate(paths, start=1)}
            for policy, paths in rankings.items()
        }
        for path in sorted(audit.oracle_files):
            candidate = audit.candidates.get(path)
            if candidate is None:
                lines.append(
                    f"| `{audit.case_id}` | `{audit.run_id}` | `{path}` | no | 0 | — | 0 | 0 | 0 | 0/0 | 0 | — |"
                )
                continue
            ranks = "/".join(
                str(rank_maps[policy].get(path, "—"))
                for policy in ("hybrid", "corroboration", "responsibility", "chain")
            )
            lines.append(
                f"| `{audit.case_id}` | `{audit.run_id}` | `{path}` | "
                f"{'yes' if path in audit.selected_files else 'no'} | {candidate.semantic_channels} | "
                f"{min(candidate.hybrid_ranks) if candidate.hybrid_ranks else '—'} | "
                f"{len(candidate.obligations)} | {candidate.query_symbol_overlap} | "
                f"{candidate.action_symbol_terms} | {len(candidate.outbound_productive_edges)}/"
                f"{len(candidate.inbound_productive_edges)} | {len(candidate.neighbor_paths)} | {ranks} |"
            )

    lines.extend(
        [
            "",
            "## Counterfactual file rankings",
            "",
            "| Case | Run | Policy | First Oracle rank | Recall@5 | Recall@10 |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    policy_recalls: dict[str, list[float]] = defaultdict(list)
    for audit in audits:
        for policy, paths in _rankings(audit).items():
            first = _first_oracle_rank(paths, audit.oracle_files)
            recall5 = _recall_at(paths, audit.oracle_files, 5)
            recall10 = _recall_at(paths, audit.oracle_files, 10)
            policy_recalls[policy].append(recall10)
            lines.append(
                f"| `{audit.case_id}` | `{audit.run_id}` | `{policy}` | "
                f"{first if first is not None else '—'} | {recall5:.3f} | {recall10:.3f} |"
            )

    lines.extend(["", "## Mean recall@10", "", "| Policy | Mean recall@10 |", "|---|---:|"])
    for policy, values in sorted(policy_recalls.items(), key=lambda item: mean(item[1]), reverse=True):
        lines.append(f"| `{policy}` | {mean(values):.3f} |")
    lines.extend(
        [
            "",
            "## Conclusions",
            "",
            "1. Intent selection is not the stable boundary assumed by retrieval. The selected `explain` contract and stage IDs can remain fixed while the second request-analysis LLM changes proposition text and evidence boundary. None of the paired initial Qdrant queries were byte-identical, and the TypeScript pair changed from four to six repository obligations because `explain_resulting_effect` and `explain_why` moved from `external` to `repository/local_to_external_handoff`.",
            "",
            "2. Qdrant alone cannot explain final instability. In the bad Vue 10803 and pandas repeats, the Oracle file had hybrid rank 1 but was not selected. Conversely, the good Vue 10803 run had the Oracle file only at reconstructed hybrid rank 16, while semantic/graph corroboration brought it to rank 3.",
            "",
            "3. Oracle files are unusually recurrent and structurally active in aggregate. They appear across more obligations, more semantic channels, and more productive incoming/outgoing edges, with higher query-to-symbol overlap. No one feature is a safe eligibility gate.",
            "",
            "4. Penalizing graph fanout is not generally valid. Oracle files had higher mean cross-file fanout than non-Oracle files. Generic utilities can be high-fanout, but real orchestration and state-propagation owners can be high-fanout too.",
            "",
            "5. The chain policy is useful for pool building, not as a replacement shortlist policy. It has the best mean recall@10 but still misses every TypeScript Oracle file in the first run's top ten and misses several owners at rank five.",
            "",
            "6. A bounded survival invariant does separate the causal source owners from the point at which they are currently lost. The union of top-12 initial hybrid files classified as implementation retains every source-owner Oracle in all eight runs, with only 12-22 files per run. This is a file-pool guarantee, not evidence acceptance and not an Oracle-ranking claim.",
            "",
            "## Recommended design order",
            "",
            "### 1. Keep repository scope backend-owned",
            "",
            "- Backend stage policy must own whether a stage receives repository retrieval. The stage-requirement LLM may describe an external boundary, but it should not suppress a repository-policy stage merely by emitting `external`.",
            "- The measured deterministic base-query experiment was stable but did not recover owners, so it should not be treated as part of this candidate-survival proposal.",
            "",
            "### 2. Build the measured bounded owner-survival pool",
            "",
            "- Before connected-component ranking, union every implementation file in the top 12 hybrid results of any initial obligation and cap the request-level pool at 24 files.",
            "- Allocate one exact executable representative per protected file across the request before allocating additional per-obligation nodes. The eight-run maximum was 22 files, so this does not require a larger candidate count than the current four-by-six final request.",
            "- Keep dense, sparse, exact-anchor, and productive-graph provenance on those files as corroboration; do not let one winning component erase a directly retrieved protected file.",
            "",
            "### 3. Select a joint responsibility chain after file survival",
            "",
            "- Within the bounded file pool, assign exact nodes to trigger/producer, state-mutation owner, and consumer/effect roles.",
            "- Treat productive graph adjacency in both directions. Newer TypeScript traces show builder functions as upstream callers of semantic seed nodes; the current provenance tier favors visible downstream `graph_direct_target` nodes and can demote those upstream owners to generic `graph_neighbor` candidates.",
            "- Assess role assignments jointly with real CodeGraph edges and source snippets, rather than isolated lexical overlap, component size, edge direction, or fanout.",
            "- Keep the prompt bounded by selecting exact ranges after file pooling instead of shrinking the file pool prematurely.",
            "",
            "### 4. Evaluation gate",
            "",
            "- Replay policies against saved traces first, using Oracle labels only for metrics.",
            "- Require improvement on every repository pair, not only mean recall.",
            "- Then run two unchanged real repetitions per main case and record scope drift, candidate-pool recall, shortlist recall, final selection, sufficiency, and retrieval tokens separately.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit shortlist signals from saved CodeRepoQA runs.")
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    audits = [audit_run(path.resolve()) for path in args.run_dirs]
    report = render_report(audits)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
