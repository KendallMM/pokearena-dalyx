"""Reglas de la arquitectura lógica: ninguna capa importa lo que no le corresponde."""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

DB_AND_WEB_LIBRARIES = {"fastapi", "starlette", "sqlalchemy", "pymongo", "redis", "jwt"}

# capa -> importaciones prohibidas (paquetes externos o internos "app.x")
RULES: dict[str, set[str]] = {
    "business": DB_AND_WEB_LIBRARIES
    | {"app.api", "app.persistence", "app.security", "app.tasks", "app.config"},
    "api": {
        "sqlalchemy",
        "pymongo",
        "redis",
        "jwt",
        "PIL",
        "app.persistence",
        "app.tasks",
    },
    "persistence": {"fastapi", "starlette", "app.api", "app.tasks", "app.security"},
    "security": {
        "fastapi",
        "starlette",
        "sqlalchemy",
        "pymongo",
        "redis",
        "app.api",
        "app.business",
        "app.persistence",
        "app.tasks",
    },
    "tasks": {
        "fastapi",
        "starlette",
        "sqlalchemy",
        "pymongo",
        "redis",
        "jwt",
        "app.api",
        "app.persistence",
    },
}

# Pillow solo puede usarse en el módulo de Procesamiento de imágenes.
IMAGE_LIBRARY_ONLY_IN = APP_DIR / "business" / "catalog" / "image_processing"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _matches(module: str, forbidden: str) -> bool:
    return module == forbidden or module.startswith(forbidden + ".")


def test_layers_respect_dependency_rules() -> None:
    violations = []
    for layer, forbidden in RULES.items():
        for path in (APP_DIR / layer).rglob("*.py"):
            for module in _imports(path):
                for rule in forbidden:
                    if _matches(module, rule):
                        violations.append(
                            f"{path.relative_to(APP_DIR)} importa {module}"
                        )
    assert not violations, "\n".join(violations)


def test_image_library_only_in_image_processing() -> None:
    violations = []
    for path in APP_DIR.rglob("*.py"):
        if IMAGE_LIBRARY_ONLY_IN in path.parents:
            continue
        if any(_matches(m, "PIL") for m in _imports(path)):
            violations.append(str(path.relative_to(APP_DIR)))
    assert not violations, "\n".join(violations)
