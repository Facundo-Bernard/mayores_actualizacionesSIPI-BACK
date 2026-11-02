"""Ratchet de imports entre features: no se agregan dependencias nuevas.

Cada extracción debe quitar su línea de architecture_baseline.txt.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
FEATURES_ROOT = ROOT / "app" / "features"
BASELINE_PATH = Path(__file__).parent / "architecture_baseline.txt"


def _feature_of(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "features":
        return parts[2]
    return None


def scan_cross_feature_imports() -> set[str]:
    violations = set()
    for path in FEATURES_ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        current_feature = _feature_of(".".join(Path(relative).with_suffix("").parts))
        if not current_feature:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]

            for module in modules:
                other_feature = _feature_of(module)
                if other_feature and other_feature != current_feature:
                    violations.add(f"{relative} -> {other_feature}")
    return violations


def load_baseline() -> set[str]:
    lines = BASELINE_PATH.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def test_no_new_cross_feature_imports():
    current = scan_cross_feature_imports()
    baseline = load_baseline()

    new_violations = sorted(current - baseline)
    assert not new_violations, (
        "Nuevos imports feature -> feature. Movelos a app/shared/ o usá una interfaz explícita: "
        + ", ".join(new_violations)
    )

    fixed_violations = sorted(baseline - current)
    assert not fixed_violations, (
        "Estas violaciones ya no existen; quitarlas de tests/unit/architecture_baseline.txt: "
        + ", ".join(fixed_violations)
    )
