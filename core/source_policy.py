from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceCategory(str, Enum):
    """Project-specific artifact categories that may ground v1 responses."""

    #: Files that are part of the repository implementation.
    SOURCE_CODE = "source_code"
    #: Project documentation, design notes, README files, and similar docs.
    DOCUMENTATION = "documentation"
    #: Issue tracker entries that describe defects, requirements, or discussion.
    ISSUE_TRACKER = "issue_tracker"
    #: Pull requests and review discussion tied to repository evolution.
    PULL_REQUEST = "pull_request"
    #: Local project notes configured alongside the workspace.
    LOCAL_NOTES = "local_notes"
    #: NotebookLM-derived project context attached to the current workspace.
    NOTEBOOKLM = "notebooklm"


# Default source allowlist used by v1 policy and retrieval planning.
DEFAULT_ALLOWED_SOURCE_CATEGORIES: tuple[SourceCategory, ...] = (
    SourceCategory.SOURCE_CODE,
    SourceCategory.DOCUMENTATION,
    SourceCategory.ISSUE_TRACKER,
    SourceCategory.PULL_REQUEST,
    SourceCategory.LOCAL_NOTES,
    SourceCategory.NOTEBOOKLM,
)


@dataclass(frozen=True)
class SourcePolicy:
    """Caller-controlled source allowlist for policy and retrieval planning."""

    #: Source categories retrieval and response generation may use.
    allowed_categories: tuple[SourceCategory, ...]
    #: Stable name for logs, evaluation traces, and policy metadata.
    policy_name: str = "v1_default"

    def allows(self, source_category: SourceCategory) -> bool:
        """Return whether this policy allows the source category."""

        return source_category in self.allowed_categories


DEFAULT_SOURCE_POLICY = SourcePolicy(
    allowed_categories=DEFAULT_ALLOWED_SOURCE_CATEGORIES,
    policy_name="v1_default",
)


def is_allowed_source_category(
    source_category: SourceCategory,
    source_policy: SourcePolicy = DEFAULT_SOURCE_POLICY,
) -> bool:
    """Return whether a source category is valid grounded evidence."""

    return source_policy.allows(source_category)
