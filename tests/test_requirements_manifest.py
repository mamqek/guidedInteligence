from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAINTAINED_PYTHON_PATHS = (
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "services",
    PROJECT_ROOT / "testing",
    PROJECT_ROOT / "tools",
    PROJECT_ROOT / "step3_harness_scenarios.py",
)
LOCAL_TOP_LEVEL_MODULES = {"core", "services", "testing", "tools", "step3_harness_scenarios"}
PACKAGE_BY_IMPORT = {
    "langgraph": "langgraph",
}


class RequirementsManifestTests(unittest.TestCase):
    def test_requirements_match_direct_third_party_imports(self) -> None:
        imported_packages = {
            PACKAGE_BY_IMPORT[name]
            for name in _direct_third_party_imports()
            if name in PACKAGE_BY_IMPORT
        }
        unknown_imports = sorted(name for name in _direct_third_party_imports() if name not in PACKAGE_BY_IMPORT)
        declared_packages = _declared_requirement_packages(PROJECT_ROOT / "requirements.txt")

        self.assertEqual(unknown_imports, [])
        self.assertEqual(declared_packages, imported_packages)


def _direct_third_party_imports() -> set[str]:
    imports: set[str] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".", 1)[0])
    return {
        name
        for name in imports
        if name not in sys.stdlib_module_names and name not in LOCAL_TOP_LEVEL_MODULES
    }


def _python_files() -> list[Path]:
    files: list[Path] = []
    for source in MAINTAINED_PYTHON_PATHS:
        if source.is_file():
            files.append(source)
        elif source.is_dir():
            files.extend(path for path in source.rglob("*.py") if ".venv" not in path.parts and "__pycache__" not in path.parts)
    return files


def _declared_requirement_packages(path: Path) -> set[str]:
    packages: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        package = text.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0].strip()
        packages.add(package.lower().replace("_", "-"))
    return packages


if __name__ == "__main__":
    unittest.main()
