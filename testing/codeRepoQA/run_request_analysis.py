from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.intent.classifier import classify_intent
from services.intent.models import IntentClassificationInput
from testing.codeRepoQA.run_case import _load_project_llm_config, _load_test_run_config, _user_prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run request analysis without invoking retrieval.")
    parser.add_argument("--issue-json", required=True)
    parser.add_argument("--run-config", default="configs/testing/workspace.json")
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--repository-name", required=True)
    parser.add_argument("--repository-owner", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    issue_path = Path(args.issue_json)
    issue = json.loads(issue_path.read_text(encoding="utf-8"))
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    user_prompt = _user_prompt(title, body)
    snapshot_root = Path(args.snapshot_root)
    repository_context = {
        "repository": {
            "workspace_name": snapshot_root.name,
            "repository_name": args.repository_name,
            "repository_owner": args.repository_owner,
            "package_name": _package_name(snapshot_root),
        },
        "indexed_scope": {"excluded_paths": []},
        "issue_path_checks": _issue_path_checks(user_prompt, snapshot_root),
    }
    llm_config = _load_project_llm_config(_load_test_run_config(args.run_config))
    result = classify_intent(
        IntentClassificationInput(
            user_prompt=user_prompt,
            repository_name=args.repository_name,
            repository_context=repository_context,
        ),
        llm_config=llm_config,
    )
    artifact = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "issue_json": str(issue_path.resolve()),
        "snapshot_root": str(snapshot_root.resolve()),
        "input": {
            "repository_name": args.repository_name,
            "repository_context": repository_context,
            "user_prompt": user_prompt,
        },
        "result": result.to_dict(),
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output_path)
    return 0 if result.status == "success" else 1


def _package_name(snapshot_root: Path) -> str:
    package_path = snapshot_root / "package.json"
    if not package_path.is_file():
        return ""
    value = json.loads(package_path.read_text(encoding="utf-8"))
    return str(value.get("name") or "") if isinstance(value, dict) else ""


def _issue_path_checks(user_prompt: str, snapshot_root: Path) -> list[dict[str, object]]:
    from core.control_layer import _ISSUE_PATH_PATTERN

    references = tuple(dict.fromkeys(
        match.group(0).replace("\\", "/").lstrip("./")
        for match in _ISSUE_PATH_PATTERN.finditer(user_prompt)
    ))[:12]
    return [
        {
            "issue_reference": reference,
            "exists_in_indexed_repository": (snapshot_root / reference).is_file(),
        }
        for reference in references
    ]


if __name__ == "__main__":
    raise SystemExit(main())
