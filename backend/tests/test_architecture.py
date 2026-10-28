"""Garantiza que el motor de reglas no dependa de frameworks."""

import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "app" / "engine" / "ability_engine.py"
FORBIDDEN = {
    "fastapi",
    "starlette",
    "sqlalchemy",
    "motor",
    "pymongo",
    "PIL",
    "jwt",
    "pydantic",
    "app",
}


def imported_roots(path: Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_engine_does_not_import_frameworks_or_other_app_modules():
    assert imported_roots(ENGINE) & FORBIDDEN == set()
