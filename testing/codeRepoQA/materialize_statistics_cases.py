from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = ROOT / "testing" / "codeRepoQA" / "corpus"
CASES_ROOT = CORPUS_ROOT / "cases"
MANIFEST_PATH = CORPUS_ROOT / "selection_manifest.json"
GROUP_ORDER = (
    "bug_regression", "feature_enhancement", "performance_memory", "compatibility_versioning",
    "api_behavior_design", "testing_build_tooling", "maintenance_refactor", "question_usage",
)


@dataclass(frozen=True)
class Candidate:
    case_id: str
    repository: str
    issue_number: int
    source_path: Path
    original_issue_path: str
    group: str
    partition: str
    rationale: str
    fix_pr: int
    fix_title: str
    fix_commit: str
    base_commit: str
    implementation_files: tuple[str, ...]
    test_files: tuple[str, ...] = ()
    documentation_files: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    subsystem: str = ""


VUE_SOURCE = Path(r"C:\Users\mukha\Downloads\vue\cloudide\workspace\QA_data\vue")
TS_SOURCE = Path(r"C:\Users\mukha\Downloads\TypeScript\cloudide\workspace\QA_data\TypeScript")
PANDAS_SOURCE = Path(r"C:\Users\mukha\Downloads\pandas\cloudide\workspace\QA_data\pandas")


CANDIDATES = (
    Candidate(
        "vuejs-vue-10519", "vuejs/vue", 10519, VUE_SOURCE / "10519.json",
        "vue/cloudide/workspace/QA_data/vue/10519.json", "bug_regression", "development",
        "Vue prop-validation bug with a compact runtime fix and unit-test Oracle.",
        10529, "fix: avoid stringifying Symbols in prop validation messages",
        "abb5ef35dd02919dce19c895ad12113071712df0", "b97606cdc658448b56518ac27af98fc82999d05f",
        ("src/core/util/props.js",), ("test/unit/features/options/props.spec.js",),
        symbols=("assertProp", "Symbol"), subsystem="prop validation",
    ),
    Candidate(
        "microsoft-TypeScript-10020", "microsoft/TypeScript", 10020, TS_SOURCE / "10020.json",
        "TypeScript/cloudide/workspace/QA_data/TypeScript/10020.json", "feature_enhancement", "development",
        "TypeScript Organize Imports feature spanning the language service and focused harness coverage.",
        22087, "Support Organize Imports",
        "b31aa4e012fc4c2afc9c2200f18b9e79edac160b", "4d284d617f78a12461af62840b096133e63605d8",
        ("src/compiler/utilities.ts", "src/services/organizeImports.ts"),
        ("src/harness/unittests/organizeImports.ts", "tests/baselines/reference/organizeImports/AmbientModule.ts", "tests/baselines/reference/organizeImports/TopLevelAndAmbientModule.ts"),
        symbols=("organizeImports",), subsystem="language service organize-imports refactoring",
    ),
    Candidate(
        "vuejs-vue-10004", "vuejs/vue", 10004, VUE_SOURCE / "10004.json",
        "vue/cloudide/workspace/QA_data/vue/10004.json", "performance_memory", "development",
        "Vue v-model listener memory leak with a runtime owner and focused regression test.",
        10085, "fix: remove stale model listeners for deactivated components",
        "3d29ba863b89fd90dabd0856c0507eacdf5fef22", "509de2af793a770c7c29897980b27dfe5278d274",
        ("src/platforms/web/runtime/modules/events.js",), ("test/unit/features/component/component-keep-alive.spec.js",),
        symbols=("updateDOMListeners",), subsystem="web runtime DOM event listeners",
    ),
    Candidate(
        "vuejs-vue-13052", "vuejs/vue", 13052, VUE_SOURCE / "13052.json",
        "vue/cloudide/workspace/QA_data/vue/13052.json", "compatibility_versioning", "development",
        "Vue compiler-sfc compatibility case with an explicit package-level dependency owner.",
        13053, "fix(compiler-sfc): support Prettier 3",
        "45d6ad6645e960a3ee52ad9667520a1625f10dfd", "0ad8e8d94f3a3bf4429f25850c85a6bbb2b81364",
        ("packages/compiler-sfc/package.json",), ("pnpm-lock.yaml",),
        symbols=("compiler-sfc", "prettier"), subsystem="compiler-sfc dependency compatibility",
    ),
    Candidate(
        "microsoft-TypeScript-16278", "microsoft/TypeScript", 16278, TS_SOURCE / "16278.json",
        "TypeScript/cloudide/workspace/QA_data/TypeScript/16278.json", "api_behavior_design", "development",
        "TypeScript refactor API case with protocol, service, client/server, and fourslash coverage.",
        16307, "New refactor API",
        "6007eb7dfb816cf2d021f0057cda2dd1c62b352b", "b217c39bb16008a57723b7faa662b2f11447c942",
        ("scripts/buildProtocol.ts", "src/server/client.ts", "src/server/protocol.ts", "src/server/session.ts", "src/services/refactorProvider.ts", "src/services/refactors/convertFunctionToEs6Class.ts", "src/services/services.ts", "src/services/types.ts"),
        ("src/harness/fourslash.ts", "src/harness/harnessLanguageService.ts", "src/harness/unittests/session.ts", "tests/cases/fourslash/convertFunctionToEs6Class1.ts", "tests/cases/fourslash/convertFunctionToEs6Class2.ts", "tests/cases/fourslash/convertFunctionToEs6Class3.ts", "tests/cases/fourslash/fourslash.ts", "tests/cases/fourslash/server/convertFunctionToEs6Class-server.ts"),
        symbols=("getApplicableRefactors", "getEditsForRefactor"), subsystem="language service refactor API",
    ),
    Candidate(
        "vuejs-vue-11718", "vuejs/vue", 11718, VUE_SOURCE / "11718.json",
        "vue/cloudide/workspace/QA_data/vue/11718.json", "testing_build_tooling", "development",
        "Vue SSR webpack-plugin compatibility case with focused plugin implementation owners.",
        12002, "fix: support webpack 5 in vue-server-renderer plugins",
        "80e7730946538e0371e213100a0fe81299c2f4b2", "38f71de380d566e4eef60968a8eca6bd6f482dd5",
        ("src/server/webpack-plugin/client.js", "src/server/webpack-plugin/server.js", "src/server/webpack-plugin/util.js"),
        symbols=("VueSSRClientPlugin", "VueSSRServerPlugin"), subsystem="SSR webpack plugins",
    ),
    Candidate(
        "vuejs-vue-8528", "vuejs/vue", 8528, VUE_SOURCE / "8528.json",
        "vue/cloudide/workspace/QA_data/vue/8528.json", "maintenance_refactor", "development",
        "Focused maintenance issue whose owner is a single shared utility source file.",
        8529, "docs: improve comments in shared utilities",
        "af819a07dd8c2afc94e670e81b5e248f82794334", "5e912976c45ca19d8524657bffe6883723027ed2",
        ("src/shared/util.js",), symbols=("looseEqual",), subsystem="shared runtime utilities",
    ),
    Candidate(
        "microsoft-TypeScript-10473", "microsoft/TypeScript", 10473, TS_SOURCE / "10473.json",
        "TypeScript/cloudide/workspace/QA_data/TypeScript/10473.json", "bug_regression", "final",
        "Held-out tsserver configuration-diagnostic event bug with server owners and a harness test.",
        11285, "Send config file diagnostics when configuration changes",
        "635313ee45e1edd09e5e6e849cc58d2ffdacdfc8", "81fc759530c3245011d13e7f9f23f17b687a97e6",
        ("src/server/editorServices.ts", "src/server/session.ts"), ("src/harness/unittests/tsserverProjectSystem.ts",),
        symbols=("configFileDiag",), subsystem="tsserver configuration diagnostics",
    ),
    Candidate(
        "vuejs-vue-6097", "vuejs/vue", 6097, VUE_SOURCE / "6097.json",
        "vue/cloudide/workspace/QA_data/vue/6097.json", "feature_enhancement", "final",
        "Held-out Vue inject-default feature with implementation and unit-test coverage.",
        6322, "feat: allow default values for injected dependencies",
        "88423fc66a2a4917dcdb7631a4594f05446283b1", "b3cd9bc3940eb1e01da7081450929557d9c1651e",
        ("src/core/instance/inject.js", "src/core/util/options.js"), ("test/unit/features/options/inject.spec.js",),
        symbols=("resolveInject", "inject"), subsystem="dependency injection options",
    ),
    Candidate(
        "vuejs-vue-9842", "vuejs/vue", 9842, VUE_SOURCE / "9842.json",
        "vue/cloudide/workspace/QA_data/vue/9842.json", "performance_memory", "final",
        "Held-out transition/keep-alive memory case with a focused owner and regression test.",
        12015, "fix: prune keep-alive cache entries correctly",
        "e7baaa12055231c9367fa1c7bf917e534bd8a739", "2b93e86aa1437168476cbb5100cfb3bbbac55efa",
        ("src/core/components/keep-alive.js",), ("test/unit/features/component/component-keep-alive.spec.js",),
        symbols=("pruneCacheEntry", "KeepAlive"), subsystem="keep-alive component cache lifecycle",
    ),
    Candidate(
        "microsoft-TypeScript-10041", "microsoft/TypeScript", 10041, TS_SOURCE / "10041.json",
        "TypeScript/cloudide/workspace/QA_data/TypeScript/10041.json", "compatibility_versioning", "final",
        "Held-out TypeScript array-compatibility regression with checker and conformance Oracles.",
        10069, "Fix best common type selection for RegExpMatchArray compatibility",
        "1435fb19a819d85a84ebf4ca4c7ffde7935764fe", "36b611334dff29d6edf5f6be0ff95f796e98f14e",
        ("src/compiler/checker.ts",),
        ("tests/baselines/reference/bestChoiceType.js", "tests/baselines/reference/bestChoiceType.symbols", "tests/baselines/reference/bestChoiceType.types", "tests/baselines/reference/nonContextuallyTypedLogicalOr.symbols", "tests/baselines/reference/nonContextuallyTypedLogicalOr.types", "tests/baselines/reference/subtypingWithObjectMembersOptionality3.types", "tests/baselines/reference/subtypingWithObjectMembersOptionality4.types", "tests/cases/compiler/bestChoiceType.ts"),
        symbols=("RegExpMatchArray", "getBestCommonType"), subsystem="compiler type checker",
    ),
    Candidate(
        "pandas-dev-pandas-10150", "pandas-dev/pandas", 10150, PANDAS_SOURCE / "10150.json",
        "pandas/cloudide/workspace/QA_data/pandas/10150.json", "api_behavior_design", "final",
        "Held-out pandas value_counts naming-semantics issue with implementation, tests, and release note.",
        10419, "BUG/API: make value_counts name handling consistent",
        "654e7397280be9a681fafcf8f70cfe3e20a9ef47", "3908ad53e33c74096eb5a682256dc13fb6e91e3a",
        ("pandas/core/algorithms.py", "pandas/core/base.py"), ("pandas/tests/test_base.py", "pandas/util/testing.py"),
        ("doc/source/whatsnew/v0.17.0.txt",), ("value_counts",), subsystem="pandas value-counting API metadata",
    ),
    Candidate(
        "vuejs-vue-11782", "vuejs/vue", 11782, VUE_SOURCE / "11782.json",
        "vue/cloudide/workspace/QA_data/vue/11782.json", "testing_build_tooling", "final",
        "Held-out Windows npm-test tooling failure with a focused package-script owner.",
        11784, "fix: make npm test work on Windows",
        "14882c9cbfe289814de7c2b5323fe0831b3750de", "b800e8e9ee4fa4be9b3d6130b5ee82d668066870",
        ("package.json",), symbols=("test"), subsystem="cross-platform npm test scripts",
    ),
    Candidate(
        "microsoft-TypeScript-19074", "microsoft/TypeScript", 19074, TS_SOURCE / "19074.json",
        "TypeScript/cloudide/workspace/QA_data/TypeScript/19074.json", "maintenance_refactor", "final",
        "Held-out TypeScript language-service-host cleanup with production and test-runner owners.",
        32018, "Clean up LSHost mentions",
        "37b20f6afd3eee694c26ca39c586c42ec97be98e", "a97c18f227c22d3d6e0e5d413d91d3eb06065410",
        ("src/compiler/moduleNameResolver.ts", "src/server/project.ts"),
        ("src/testRunner/unittests/tscWatch/resolutionCache.ts", "src/testRunner/unittests/tsserver/cachingFileSystemInformation.ts", "src/testRunner/unittests/tsserver/resolutionCache.ts"),
        symbols=("LanguageServiceHost", "ResolutionCache"), subsystem="module resolution and server project host",
    ),
)


def labels_from(raw: dict[str, object]) -> list[str]:
    labels = raw.get("labels", [])
    return [str(item.get("name", "")) for item in labels if isinstance(item, dict) and item.get("name")]


def file_rows(candidate: Candidate) -> list[dict[str, object]]:
    paths = (*candidate.implementation_files, *candidate.test_files, *candidate.documentation_files)
    return [{"path": path, "change_type": "MODIFIED"} for path in paths]


def verification(candidate: Candidate, raw: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_id": candidate.case_id,
        "primary_group": candidate.group,
        "statistics_partition": candidate.partition,
        "repository": candidate.repository,
        "issue_number": candidate.issue_number,
        "issue_url": f"https://github.com/{candidate.repository}/issues/{candidate.issue_number}",
        "original_issue_path": candidate.original_issue_path,
        "title": raw["title"],
        "labels": labels_from(raw),
        "state": raw.get("state", "closed"),
        "created_at": raw.get("created_at"),
        "closed_at": raw.get("closed_at"),
        "selection_rationale": candidate.rationale,
        "visible_prompt_policy": {
            "include_fields": ["title", "created_at", "body"],
            "exclude_post_resolution_fields": ["comments_details", "events", "fixed_by", "cite", "cited_by", "closed_at"],
        },
        "resolution_artifacts": {
            "fixed_by_pr_numbers": [candidate.fix_pr],
            "referenced_commit_shas_from_issue_events": [],
            "cite": raw.get("cite", []),
            "cited_by": raw.get("cited_by", []),
            "resolution_status": "has_local_resolution_artifact",
            "github_prs": [{
                "number": candidate.fix_pr,
                "title": candidate.fix_title,
                "url": f"https://github.com/{candidate.repository}/pull/{candidate.fix_pr}",
                "merged": True,
                "merge_commit_sha": candidate.fix_commit,
                "head_sha": "",
                "base_sha": candidate.base_commit,
                "changed_files": len(file_rows(candidate)),
                "files_truncated": False,
                "files": file_rows(candidate),
            }],
        },
        "oracle": {
            "implementation_files": list(candidate.implementation_files),
            "test_or_validation_files": list(candidate.test_files),
            "documentation_files": list(candidate.documentation_files),
            "symbols_or_apis": list(candidate.symbols),
            "subsystem": candidate.subsystem,
            "responsibility_summary": f"The relevant files own {candidate.subsystem} behavior described by the issue.",
            "hidden_resolution_summary": f"PR #{candidate.fix_pr}: {candidate.fix_title}",
            "issue_body_file_refs": [],
            "thread_file_refs": [],
            "resolution_comment_excerpts": [],
            "notes": "Oracle frozen from the locally available fixing commit before retrieval evaluation.",
        },
        "measurement_criteria": {
            "retrieval_found_at_least_one_oracle_implementation_file": "expected_true",
            "relevant_oracle_files_appear_within_top_k": {"k_values": [1, 2, 5, 10], "expected": "implementation_files_preferred_then_validation_or_docs"},
            "no_post_resolution_information_leaked_into_retrieval": "retrieval uses only visible issue fields and the verified pre-fix snapshot",
        },
    }


def manifest_entry(candidate: Candidate, raw: dict[str, object]) -> dict[str, object]:
    return {
        "case_id": candidate.case_id,
        "group": candidate.group,
        "statistics_partition": candidate.partition,
        "repository": candidate.repository,
        "issue_number": candidate.issue_number,
        "title": raw["title"],
        "original_issue_path": candidate.original_issue_path,
        "case_dir": f"cases/{candidate.case_id}",
        "labels": labels_from(raw),
        "selection_rationale": candidate.rationale,
        "resolution_status": "has_local_resolution_artifact",
    }


def render_cases_markdown(cases: list[dict[str, object]]) -> str:
    lines = [
        "# Selected CodeRepoQA Corpus Cases", "",
        "This table is generated from `selection_manifest.json`. Each case directory contains `issue.json` and `verification.json`.", "",
    ]
    for group in GROUP_ORDER:
        lines.extend([
            f"## {group}", "",
            "| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |",
            "| --- | --- | --- | ---: | --- | --- | --- |",
        ])
        for case in (item for item in cases if item["group"] == group):
            title = str(case["title"]).replace("|", "\\|")
            rationale = str(case["selection_rationale"]).replace("|", "\\|")
            lines.append(
                f"| `{case['case_id']}` | `{case.get('statistics_partition', '')}` | {case['repository']} | "
                f"#{case['issue_number']}: {title} | `{case['original_issue_path']}` | `{case['case_dir']}` | {rationale} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_benchmark_groups(cases: list[dict[str, object]]) -> str:
    retrieval = sorted(str(item["case_id"]) for item in cases if item["group"] != "question_usage")
    explanation = sorted(str(item["case_id"]) for item in cases if item["group"] == "question_usage")
    lines = [
        "# CodeRepoQA Benchmark Groups", "",
        "This corpus mixes two different benchmark intents. They should not be treated as interchangeable when comparing retrieval modes.", "",
        "## Retrieval-grounded", "",
        "Use these cases for overlap, ranking, token, and timing comparisons.", "",
        "Classification rule:",
        "- `verification.json` contains at least one explicit oracle file in `oracle.implementation_files`,",
        "  `oracle.test_or_validation_files`, or `oracle.documentation_files`.",
        "- These cases support deterministic checks such as file overlap, top-k placement, and stable timing/token comparisons.", "",
        f"Cases in this group: `{len(retrieval)}`", "",
        *(f"- `{case_id}`" for case_id in retrieval), "",
        "## Explanation-grounded", "",
        "Use these cases for explanation agreement, leakage checks, and evidence plausibility.", "",
        "Classification rule:",
        "- `verification.json` intentionally omits oracle file lists and instead defines truth mainly through",
        "  subsystem/responsibility summaries and post-resolution maintainer explanations.",
        "- These cases are poor headline retrieval benchmarks because file overlap is not meaningful or is explicitly marked secondary.", "",
        f"Cases in this group: `{len(explanation)}`", "",
        *(f"- `{case_id}`" for case_id in explanation), "",
        "## Why The Split Matters", "",
        "- Retrieval-grounded cases answer: did the retriever reach the right code quickly and cheaply?",
        "- Explanation-grounded cases answer: did the system infer the right explanation without leaking hindsight?",
        "- Do not use explanation-grounded cases as the main evidence for retrieval superiority.",
        "- Do not use retrieval-grounded overlap scores alone to judge explanation quality.", "",
        "## Current Corpus Totals", "",
        f"- Total cases: `{len(cases)}`",
        f"- Retrieval-grounded: `{len(retrieval)}`",
        f"- Explanation-grounded: `{len(explanation)}`", "",
    ]
    return "\n".join(lines)


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    existing = {item["case_id"]: item for item in manifest["cases"]}
    for item in manifest["cases"]:
        item.setdefault("statistics_partition", "excluded_explanation" if item["group"] == "question_usage" else "development")

    for candidate in CANDIDATES:
        if not candidate.source_path.exists():
            raise FileNotFoundError(candidate.source_path)
        raw = json.loads(candidate.source_path.read_text(encoding="utf-8"))
        if raw.get("issue_or_pr") != "issue" or int(raw.get("number", -1)) != candidate.issue_number:
            raise ValueError(f"Unexpected source record for {candidate.case_id}")
        case_dir = CASES_ROOT / candidate.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate.source_path, case_dir / "issue.json")
        (case_dir / "verification.json").write_text(
            json.dumps(verification(candidate, raw), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        entry = manifest_entry(candidate, raw)
        if candidate.case_id in existing:
            existing[candidate.case_id].update(entry)
        else:
            manifest["cases"].append(entry)
            existing[candidate.case_id] = entry

    manifest["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (CORPUS_ROOT / "cases.md").write_text(render_cases_markdown(manifest["cases"]), encoding="utf-8")
    (CORPUS_ROOT / "benchmark-groups.md").write_text(render_benchmark_groups(manifest["cases"]), encoding="utf-8")
    print(f"Materialized {len(CANDIDATES)} cases; manifest now contains {len(manifest['cases'])} cases.")


if __name__ == "__main__":
    main()
