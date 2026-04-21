from __future__ import annotations

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


# Default source allowlist used by v1 policy and retrieval planning.
DEFAULT_ALLOWED_SOURCE_CATEGORIES: tuple[SourceCategory, ...] = (
    SourceCategory.SOURCE_CODE,
    SourceCategory.DOCUMENTATION,
    SourceCategory.ISSUE_TRACKER,
    SourceCategory.PULL_REQUEST,
)


def is_allowed_source_category(source_category: SourceCategory) -> bool:
    """Return whether a source category is valid grounded evidence for v1."""

    return source_category in DEFAULT_ALLOWED_SOURCE_CATEGORIES
