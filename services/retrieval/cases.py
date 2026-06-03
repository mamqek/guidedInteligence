from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class VisibleCodeRepoQACase:
    """Stage 1 visible CodeRepoQA case data."""

    case_id: str
    repo_owner: str
    repo_name: str
    issue_number: int
    title: str
    created_at: str
    initial_body: str
    repo_pre_path: str
    repo_pre_commit: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HiddenCodeRepoQACase:
    """Evaluator-only CodeRepoQA case data that Stage 1 must not receive."""

    case_id: str
    hidden_fields: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "hidden_fields": dict(self.hidden_fields)}


VISIBLE_FIELD_NAMES = {
    "repository_url",
    "number",
    "title",
    "created_at",
    "body",
}


def load_coderepoqa_case(
    issue_json_path: str | Path,
    *,
    repo_pre_path: str | Path,
    repo_pre_commit: str,
) -> tuple[VisibleCodeRepoQACase, HiddenCodeRepoQACase]:
    """Load a CodeRepoQA issue and split Stage 1 visible data from hidden data."""

    issue_path = Path(issue_json_path)
    data = json.loads(issue_path.read_text(encoding="utf-8"))
    owner, repo_name = _repo_owner_name(data)
    issue_number = int(data["number"])
    case_id = f"{owner}-{repo_name}-{issue_number}"

    visible = VisibleCodeRepoQACase(
        case_id=case_id,
        repo_owner=owner,
        repo_name=repo_name,
        issue_number=issue_number,
        title=str(data.get("title", "")),
        created_at=str(data.get("created_at", "")),
        initial_body=str(data.get("body", "")),
        repo_pre_path=str(Path(repo_pre_path)),
        repo_pre_commit=repo_pre_commit,
    )

    hidden_fields = {key: value for key, value in data.items() if key not in VISIBLE_FIELD_NAMES}
    hidden = HiddenCodeRepoQACase(case_id=case_id, hidden_fields=hidden_fields)
    return visible, hidden


def _repo_owner_name(data: Mapping[str, Any]) -> tuple[str, str]:
    repository_url = str(data.get("repository_url", "")).rstrip("/")
    if repository_url:
        parts = repository_url.split("/")
        if len(parts) >= 2:
            return parts[-2], parts[-1]

    html_url = str(data.get("html_url", "")).rstrip("/")
    parts = html_url.split("/")
    if len(parts) >= 4:
        return parts[-3], parts[-2]

    raise ValueError("Unable to determine repository owner/name from CodeRepoQA issue JSON.")
