from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, PolicyResult, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval.config import SUPPORTED_CODEX_PROMPT_PROFILES, WorkspaceRetrievalConfig


CODEX_PROMPT_PROFILES_DIR = Path(__file__).resolve().parent / "profiles"
USER_PROMPT_PLACEHOLDER = "{{USER_PROMPT}}"
RETRIEVAL_HINTS_PLACEHOLDER = "{{RETRIEVAL_HINTS_JSON}}"


class CodexRetrievalError(RuntimeError):
    """Raised when the Codex-backed retrieval stage cannot produce evidence."""


class CodexRetrievalStage:
    """Retrieval stage that delegates codebase evidence discovery to Codex CLI."""

    def __init__(self, config: WorkspaceRetrievalConfig) -> None:
        config.validate()
        self.config = config

    def retrieve(self, state: ConversationState, policy_result: PolicyResult) -> RetrievalResult:
        if state.evidence:
            return RetrievalResult(
                evidence=tuple(state.evidence),
                coverage_status="sufficient_context",
                sufficient=True,
                retrieval_summary={
                    "retriever": "codex",
                    "model": self.config.codex_model,
                    "source": "conversation_state",
                    "evidence_count": len(state.evidence),
                    "stop_reason": "existing_context_sufficient",
                },
            )
        if SourceCategory.SOURCE_CODE not in policy_result.allowed_sources:
            return RetrievalResult(
                evidence=(),
                coverage_status="missing",
                sufficient=False,
                retrieval_summary={
                    "retriever": "codex",
                    "model": self.config.codex_model,
                    "stop_reason": "source_code_not_allowed",
                },
                failures_or_fallbacks=("source_code_not_allowed",),
            )

        run_dir = Path(self.config.run_dir or Path(self.config.index_dir) / "codex-runs")
        run_dir.mkdir(parents=True, exist_ok=True)
        schema_path = run_dir / "codex-evidence.schema.json"
        output_path = run_dir / "codex-evidence.json"
        prompt_path = run_dir / "codex-prompt.txt"
        prompt_template, evidence_schema = load_codex_prompt_profile(self.config.codex_prompt_profile)
        schema_path.write_text(json.dumps(evidence_schema, indent=2, sort_keys=True), encoding="utf-8")
        retrieval_hints = state.retrieval_hints.to_dict() if state.retrieval_hints is not None else {}
        prompt = _codex_prompt(state.user_input, template=prompt_template, retrieval_hints=retrieval_hints)
        prompt_path.write_text(prompt, encoding="utf-8")

        command = [
            *self.config.codex_command,
            "--disable",
            "plugins",
            "-a",
            "never",
            "-c",
            'web_search="disabled"',
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--ignore-rules",
            "--model",
            self.config.codex_model,
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            prompt,
        ]
        started_at = datetime.now(timezone.utc)
        self._record(
            "codex_retrieval_started",
            {
                "conversation_id": state.conversation_id,
                "workspace_root": self.config.workspace_root,
                "model": self.config.codex_model,
                "prompt_profile": self.config.codex_prompt_profile,
                "schema_path": str(schema_path),
                "output_path": str(output_path),
                "retrieval_hints": retrieval_hints,
            },
        )
        try:
            completed = subprocess.run(
                command,
                cwd=str(Path(self.config.workspace_root)),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_codex_subprocess_env(command),
                timeout=self.config.codex_timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CodexRetrievalError(
                "Codex retrieval mode requires the `codex` CLI to be installed and available on PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CodexRetrievalError(
                f"Codex retrieval timed out after {self.config.codex_timeout_seconds} seconds."
            ) from exc
        completed_at = datetime.now(timezone.utc)
        (run_dir / "codex-stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
        (run_dir / "codex-stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:1200]
            raise CodexRetrievalError(f"Codex retrieval failed with exit code {completed.returncode}: {detail}")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CodexRetrievalError("Codex retrieval did not produce valid JSON evidence output.") from exc
        if not isinstance(payload, Mapping):
            raise CodexRetrievalError("Codex retrieval output must be a JSON object.")

        workspace_root = Path(self.config.workspace_root)
        evidence = _evidence_from_payload(payload, workspace_root=workspace_root)
        evidence, artifact_trace = _enrich_codex_evidence_artifacts(evidence, workspace_root=workspace_root)
        profile_output = _profile_output(payload)
        usage = _codex_usage(completed.stdout, completed.stderr)
        if artifact_trace:
            self._record(
                "codex_evidence_artifact_trace",
                {
                    "conversation_id": state.conversation_id,
                    "entries": artifact_trace,
                    "summary": _artifact_trace_summary(artifact_trace),
                },
            )
        self._record(
            "codex_retrieval_completed",
            {
                "conversation_id": state.conversation_id,
                "model": self.config.codex_model,
                "prompt_profile": self.config.codex_prompt_profile,
                "selected_count": len(evidence),
                "relevant_files": _string_list(payload.get("relevant_files", [])),
                "profile_output": profile_output,
                "uncertainties": _string_list(payload.get("uncertainties", [])),
                "usage": usage,
                "retrieval_hints": retrieval_hints,
                "artifact_trace": artifact_trace,
            },
        )
        coverage_status = _codex_coverage_status(evidence, artifact_trace)
        return RetrievalResult(
            evidence=evidence,
            coverage_status=coverage_status,
            sufficient=bool(evidence),
            retrieval_summary={
                "retriever": "codex",
                "model": self.config.codex_model,
                "prompt_profile": self.config.codex_prompt_profile,
                "command": list(self.config.codex_command),
                "prompt_summary": str(payload.get("prompt_summary") or ""),
                "relevant_files": _string_list(payload.get("relevant_files", [])),
                "profile_output": profile_output,
                "uncertainties": _string_list(payload.get("uncertainties", [])),
                "selected_count": len(evidence),
                "stop_reason": "codex_evidence_selected" if evidence else "codex_returned_no_usable_evidence",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "stdout_path": str(run_dir / "codex-stdout.txt"),
                "stderr_path": str(run_dir / "codex-stderr.txt"),
                "raw_output_path": str(output_path),
                "usage": usage,
                "retrieval_hints": retrieval_hints,
                "artifact_trace": _artifact_trace_summary(artifact_trace),
            },
            failures_or_fallbacks=() if evidence else ("codex_returned_no_usable_evidence",),
        )

    def _record(self, event_type: str, payload: Mapping[str, Any]) -> None:
        if not self.config.run_dir:
            return
        run_dir = Path(self.config.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": event_type,
            "conversation_id": payload.get("conversation_id", ""),
            "payload": dict(payload),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with (run_dir / "retrieval-trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def load_codex_prompt_profile(profile_name: str) -> tuple[str, dict[str, Any]]:
    normalized = profile_name.strip().lower()
    if normalized not in SUPPORTED_CODEX_PROMPT_PROFILES:
        raise CodexRetrievalError(
            f"Unknown Codex prompt profile: {profile_name}. "
            f"Supported profiles: {', '.join(SUPPORTED_CODEX_PROMPT_PROFILES)}."
        )
    profile_dir = CODEX_PROMPT_PROFILES_DIR / normalized
    prompt_path = profile_dir / "prompt.md"
    schema_path = profile_dir / "evidence.schema.json"
    try:
        template = prompt_path.read_text(encoding="utf-8")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexRetrievalError(f"Could not load Codex prompt profile `{normalized}`.") from exc
    if template.count(USER_PROMPT_PLACEHOLDER) != 1:
        raise CodexRetrievalError(
            f"Codex prompt profile `{normalized}` must contain exactly one {USER_PROMPT_PLACEHOLDER} placeholder."
        )
    if template.count(RETRIEVAL_HINTS_PLACEHOLDER) > 1:
        raise CodexRetrievalError(
            f"Codex prompt profile `{normalized}` must contain at most one {RETRIEVAL_HINTS_PLACEHOLDER} placeholder."
        )
    if not isinstance(schema, Mapping):
        raise CodexRetrievalError(f"Codex prompt profile `{normalized}` schema must be a JSON object.")
    return template.rstrip() + "\n", dict(schema)


def _codex_prompt(
    user_prompt: str,
    *,
    template: str,
    retrieval_hints: Mapping[str, Any] | None = None,
) -> str:
    hint_payload = json.dumps(retrieval_hints or {}, indent=2, sort_keys=True)
    prompt = template.replace(USER_PROMPT_PLACEHOLDER, user_prompt)
    if RETRIEVAL_HINTS_PLACEHOLDER in prompt:
        return prompt.replace(RETRIEVAL_HINTS_PLACEHOLDER, hint_payload)
    return prompt


def _codex_usage(*streams: str) -> dict[str, int]:
    for stream in streams:
        if not stream:
            continue
        for line in reversed(stream.splitlines()):
            marker = '"type":"turn.completed"'
            if marker not in line:
                continue
            start = line.find("{")
            if start < 0:
                continue
            try:
                event = json.loads(line[start:])
            except json.JSONDecodeError:
                continue
            usage = event.get("usage")
            if not isinstance(usage, Mapping):
                continue
            parsed: dict[str, int] = {}
            for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
                value = usage.get(key)
                if isinstance(value, int):
                    parsed[key] = value
            if parsed:
                if "input_tokens" in parsed and "cached_input_tokens" in parsed:
                    parsed["uncached_input_tokens"] = parsed["input_tokens"] - parsed["cached_input_tokens"]
                if "input_tokens" in parsed and "output_tokens" in parsed:
                    parsed["input_plus_output_tokens"] = parsed["input_tokens"] + parsed["output_tokens"]
                if {"input_tokens", "cached_input_tokens", "output_tokens"}.issubset(parsed):
                    parsed["uncached_input_plus_output_tokens"] = (
                        parsed["input_tokens"] - parsed["cached_input_tokens"] + parsed["output_tokens"]
                    )
                return parsed
    return {}


def _codex_subprocess_env(command: Sequence[str]) -> dict[str, str]:
    env = dict(os.environ)
    if os.name != "nt":
        return env
    path_parts = _codex_path_prefixes(command)
    if not path_parts:
        return env
    existing_path = env.get("PATH") or env.get("Path") or ""
    path_key = "Path" if "Path" in env else "PATH"
    env[path_key] = os.pathsep.join((*path_parts, existing_path))
    return env


def _codex_path_prefixes(command: Sequence[str]) -> tuple[str, ...]:
    candidates: list[Path] = []
    project_venv_scripts = Path(__file__).resolve().parents[3] / ".venv" / "Scripts"
    candidates.append(project_venv_scripts)
    if command:
        command_path = Path(str(command[0]))
        if command_path.is_file():
            candidates.append(command_path.parent)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        codex_bin = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
        if codex_bin.is_dir():
            candidates.extend(
                path
                for path in sorted(codex_bin.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
                if path.is_dir() and (path / "codex-windows-sandbox-setup.exe").is_file()
            )
    plugin_helper_dir = Path.home() / ".codex" / "plugins" / ".plugin-appserver"
    candidates.append(plugin_helper_dir)
    seen: set[str] = set()
    resolved: list[str] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        value = str(candidate)
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(value)
    return tuple(resolved)


def _evidence_from_payload(payload: Mapping[str, Any], *, workspace_root: Path) -> tuple[EvidenceItem, ...]:
    items = payload.get("evidence")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return ()
    evidence: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        path = _safe_relative_path(str(item.get("file") or ""), workspace_root=workspace_root)
        if not path:
            continue
        line_start = _positive_int(item.get("line_start"))
        line_end = _positive_int(item.get("line_end"))
        if line_start is None or line_end is None:
            continue
        if line_end < line_start:
            line_end = line_start
        snippet = _read_snippet(workspace_root / path, line_start=line_start, line_end=line_end)
        if not snippet.strip():
            continue
        source_id = f"workspace:{path}:L{line_start}-L{line_end}"
        if source_id in seen:
            continue
        seen.add(source_id)
        metadata: dict[str, Any] = {
            "path": path,
            "line_range": f"L{line_start}-L{line_end}",
            "coverage_area": str(item.get("coverage_area") or "codex_evidence").strip() or "codex_evidence",
            "claim_supported": str(item.get("claim_supported") or "").strip(),
            "why_relevant": str(item.get("why_relevant") or "").strip(),
            "retrieval_path": "codex",
            "codex_file_role": str(item.get("file_role") or "").strip(),
        }
        reserved_fields = {"file", "line_start", "line_end", "claim_supported", "why_relevant", "coverage_area"}
        metadata.update({str(key): value for key, value in item.items() if str(key) not in reserved_fields})
        metadata.setdefault("file_role", "implementation")
        evidence.append(
            EvidenceItem(
                source_category=SourceCategory.SOURCE_CODE,
                source_id=source_id,
                snippet=snippet,
                rank=len(evidence) + 1,
                metadata=metadata,
            )
        )
        if len(evidence) >= 10:
            break
    return tuple(evidence)


def _enrich_codex_evidence_artifacts(
    evidence: Sequence[EvidenceItem],
    *,
    workspace_root: Path,
) -> tuple[tuple[EvidenceItem, ...], list[dict[str, Any]]]:
    enriched: list[EvidenceItem] = []
    trace_entries: list[dict[str, Any]] = []
    for item in evidence:
        path = str(item.metadata.get("path") or _path_from_source_id(item.source_id))
        classification = _classify_artifact_path(path)
        source_trace = (
            _trace_built_artifact_source(item, workspace_root=workspace_root)
            if classification["deterministic_file_role"] == "baseline_or_generated"
            else _source_trace_not_needed()
        )
        codex_file_role = str(item.metadata.get("codex_file_role") or "")
        artifact_role_agreement = _artifact_role_agreement(codex_file_role, classification["deterministic_file_role"])
        metadata = dict(item.metadata)
        metadata.update(
            {
                "codex_file_role": codex_file_role,
                "deterministic_file_role": classification["deterministic_file_role"],
                "deterministic_artifact_kind": classification["deterministic_artifact_kind"],
                "artifact_classification_confidence": classification["confidence"],
                "artifact_classification_reasons": tuple(classification["reasons"]),
                "artifact_role_agreement": artifact_role_agreement,
                "source_trace": source_trace,
            }
        )
        if artifact_role_agreement == "mismatch":
            metadata["artifact_role_mismatch_note"] = (
                "Codex selected this artifact as implementation-like, but deterministic path classification "
                "marks it as built/generated-like evidence."
            )
        enriched_item = EvidenceItem(
            source_category=item.source_category,
            source_id=item.source_id,
            snippet=item.snippet,
            rank=item.rank,
            metadata=metadata,
        )
        enriched.append(enriched_item)
        trace_entries.append(
            {
                "source_id": item.source_id,
                "selected_file": path,
                "selected_range": str(item.metadata.get("line_range") or ""),
                "codex_file_role": codex_file_role,
                "deterministic_file_role": classification["deterministic_file_role"],
                "deterministic_artifact_kind": classification["deterministic_artifact_kind"],
                "artifact_classification_confidence": classification["confidence"],
                "artifact_classification_reasons": list(classification["reasons"]),
                "artifact_role_agreement": artifact_role_agreement,
                "source_trace": source_trace,
            }
        )
    return tuple(enriched), trace_entries


def _classify_artifact_path(path: str) -> dict[str, Any]:
    normalized = path.replace("\\", "/").strip().lower()
    parts = tuple(part for part in normalized.split("/") if part)
    name = parts[-1] if parts else ""
    reasons: list[str] = []
    if "bin" in parts or normalized.startswith("bin/"):
        reasons.append("path_contains_bin")
    if "baseline" in normalized or "baselines" in parts:
        reasons.append("path_contains_baseline")
    if "snapshot" in normalized or "snapshots" in parts:
        reasons.append("path_contains_snapshot")
    if "golden" in normalized:
        reasons.append("path_contains_golden")
    if "generated" in normalized or name.endswith(".generated.ts") or name.endswith(".generated.js"):
        reasons.append("path_contains_generated_marker")
    if reasons:
        kind = "built_or_distribution_artifact" if "path_contains_bin" in reasons else "generated_or_baseline_artifact"
        return {
            "deterministic_file_role": "baseline_or_generated",
            "deterministic_artifact_kind": kind,
            "confidence": "high",
            "reasons": tuple(reasons),
        }
    if any(part in {"src", "source", "app", "packages"} for part in parts):
        return {
            "deterministic_file_role": "implementation",
            "deterministic_artifact_kind": "source_authoring_file",
            "confidence": "medium",
            "reasons": ("source_path_marker",),
        }
    return {
        "deterministic_file_role": "other",
        "deterministic_artifact_kind": "unknown",
        "confidence": "low",
        "reasons": ("no_generated_or_source_marker",),
    }


def _trace_built_artifact_source(item: EvidenceItem, *, workspace_root: Path) -> dict[str, Any]:
    path = str(item.metadata.get("path") or _path_from_source_id(item.source_id))
    mappings = _typescript_jakefile_library_mappings(workspace_root)
    candidates = mappings.get(Path(path).name, ())
    if not candidates:
        return {
            "status": "not_found",
            "source_candidates": [],
            "matched_source_files": [],
            "build_mapping_file": "",
            "build_mapping_rule": "",
            "reason": "no_known_build_mapping_for_selected_artifact",
        }
    matches = _match_snippet_to_source_candidates(item.snippet, candidates, workspace_root=workspace_root)
    status = "found" if any(match.get("match_type") == "exact" for match in matches) else "partial" if matches else "not_found"
    reason = (
        "selected_snippet_matched_source_text"
        if status == "found"
        else "selected_snippet_had_symbol_or_term_overlap_with_source"
        if status == "partial"
        else "build_mapping_found_but_no_matching_source_text"
    )
    return {
        "status": status,
        "source_candidates": list(candidates),
        "matched_source_files": matches,
        "build_mapping_file": "Jakefile.js",
        "build_mapping_rule": f"librarySourceMap target {Path(path).name}",
        "reason": reason,
    }


def _typescript_jakefile_library_mappings(workspace_root: Path) -> dict[str, tuple[str, ...]]:
    jakefile = workspace_root / "Jakefile.js"
    try:
        text = jakefile.read_text(encoding="utf-8")
    except OSError:
        return {}
    match = re.search(r"var\s+libraryDirectory\s*=\s*[\"']([^\"']+)[\"']", text)
    library_dir = match.group(1).replace("\\", "/").strip("/") if match else "src/lib"
    mappings: dict[str, tuple[str, ...]] = {}
    for entry in re.finditer(r"target:\s*[\"']([^\"']+)[\"']\s*,\s*sources:\s*\[([^\]]*)\]", text, re.S):
        target = entry.group(1).strip()
        sources = tuple(
            f"{library_dir}/{source}".replace("\\", "/")
            for source in re.findall(r"[\"']([^\"']+)[\"']", entry.group(2))
        )
        if target and sources:
            mappings[target] = sources
    return mappings


def _match_snippet_to_source_candidates(
    snippet: str,
    candidates: Sequence[str],
    *,
    workspace_root: Path,
) -> list[dict[str, Any]]:
    normalized_snippet = _normalize_match_text(snippet)
    snippet_terms = _source_match_terms(snippet)
    exact_matches: list[dict[str, Any]] = []
    fallback_matches: list[dict[str, Any]] = []
    for candidate in candidates:
        path = workspace_root / candidate
        try:
            source_text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            source_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        normalized_source = _normalize_match_text(source_text)
        if normalized_snippet and normalized_snippet in normalized_source:
            exact_matches.append({"file": candidate, "match_type": "exact", "reason": "normalized_snippet_text_found"})
            continue
        source_terms = _source_match_terms(source_text)
        overlap = tuple(sorted(snippet_terms.intersection(source_terms)))
        if len(overlap) >= 2:
            fallback_matches.append(
                {
                    "file": candidate,
                    "match_type": "term_overlap",
                    "matched_terms": overlap[:12],
                    "reason": "selected_snippet_terms_overlap_source_file",
                }
            )
    return exact_matches or fallback_matches


def _source_trace_not_needed() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "source_candidates": [],
        "matched_source_files": [],
        "build_mapping_file": "",
        "build_mapping_rule": "",
        "reason": "selected_artifact_is_not_deterministically_built_or_generated",
    }


def _artifact_role_agreement(codex_file_role: str, deterministic_file_role: str) -> str:
    codex = codex_file_role.strip().lower()
    deterministic = deterministic_file_role.strip().lower()
    if not codex:
        return "unknown"
    codex_generated = codex in {"baseline_or_generated", "generated", "built", "symptom_surface"}
    deterministic_generated = deterministic == "baseline_or_generated"
    if codex_generated == deterministic_generated:
        return "agree"
    if deterministic_generated and codex in {"implementation_owner", "supporting_implementation", "implementation"}:
        return "mismatch"
    return "different"


def _artifact_trace_summary(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    built_count = sum(1 for entry in entries if entry.get("deterministic_file_role") == "baseline_or_generated")
    source_trace_statuses: dict[str, int] = {}
    mismatches = 0
    for entry in entries:
        if entry.get("artifact_role_agreement") == "mismatch":
            mismatches += 1
        source_trace = entry.get("source_trace")
        status = str(source_trace.get("status") if isinstance(source_trace, Mapping) else "")
        if status:
            source_trace_statuses[status] = source_trace_statuses.get(status, 0) + 1
    return {
        "selected_count": len(entries),
        "built_or_generated_count": built_count,
        "all_selected_built_or_generated": bool(entries) and built_count == len(entries),
        "artifact_role_mismatch_count": mismatches,
        "source_trace_statuses": source_trace_statuses,
    }


def _codex_coverage_status(evidence: Sequence[EvidenceItem], artifact_trace: Sequence[Mapping[str, Any]]) -> str:
    if not evidence:
        return "missing"
    summary = _artifact_trace_summary(artifact_trace)
    statuses = summary.get("source_trace_statuses", {})
    found_count = 0
    if isinstance(statuses, Mapping):
        found_count = int(statuses.get("found") or 0) + int(statuses.get("partial") or 0)
    if summary.get("all_selected_built_or_generated") and found_count == 0:
        return "partial"
    return "strong"


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _source_match_terms(value: str) -> set[str]:
    ignored = {"interface", "declare", "function", "return", "string", "number", "boolean", "this", "that", "with"}
    return {
        token
        for token in re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]{2,}\b", value)
        if token.lower() not in ignored
    }


def _path_from_source_id(source_id: str) -> str:
    match = re.match(r"^[^:]+:(?P<path>.*):L\d+-L\d+$", source_id)
    return match.group("path") if match else ""


def _safe_relative_path(value: str, *, workspace_root: Path) -> str:
    normalized = value.strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return ""
    candidate = (workspace_root / normalized).resolve()
    try:
        candidate.relative_to(workspace_root.resolve())
    except ValueError:
        return ""
    if not candidate.is_file():
        return ""
    return candidate.relative_to(workspace_root.resolve()).as_posix()


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _read_snippet(path: Path, *, line_start: int, line_end: int) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    if not lines:
        return ""
    start_index = min(max(line_start - 1, 0), len(lines))
    end_index = min(max(line_end, line_start), len(lines))
    return "\n".join(lines[start_index:end_index])


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _profile_output(payload: Mapping[str, Any]) -> dict[str, Any]:
    shared_fields = {"prompt_summary", "relevant_files", "evidence", "uncertainties"}
    return {str(key): value for key, value in payload.items() if str(key) not in shared_fields}
