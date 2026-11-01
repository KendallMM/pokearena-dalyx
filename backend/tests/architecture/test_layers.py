"""Reglas de la arquitectura lógica: ninguna capa importa lo que no le corresponde."""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

DB_AND_WEB_LIBRARIES = {"fastapi", "starlette", "sqlalchemy", "pymongo", "redis", "jwt"}

# capa -> importaciones prohibidas (paquetes externos o internos "app.x")
RULES: dict[str, set[str]] = {
    # La lógica define puertos; no conoce frameworks, bases de datos ni PyJWT.
    "business": DB_AND_WEB_LIBRARIES | {"app.api", "app.persistence", "app.config"},
    # La API solo habla con la lógica; nunca con la persistencia.
    "api": {"sqlalchemy", "pymongo", "redis", "PIL", "app.persistence"},
    # La persistencia implementa los puertos de la lógica; no conoce la API.
    "persistence": {"fastapi", "starlette", "jwt", "app.api"},
    # Transversal: cualquier capa la usa, así que no puede depender de ninguna.
    "observability": DB_AND_WEB_LIBRARIES
    | {"app.api", "app.business", "app.persistence"},
}

# Librerías que solo pueden usarse en un lugar.
ONLY_IN = {
    "PIL": APP_DIR / "business" / "image_processing",  # Procesamiento de imágenes
    "jwt": APP_DIR / "api" / "gateway",  # PyJWT solo en la frontera de la API
}


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


def test_restricted_libraries_stay_in_their_module() -> None:
    violations = []
    for library, allowed_dir in ONLY_IN.items():
        for path in APP_DIR.rglob("*.py"):
            if allowed_dir in path.parents:
                continue
            if any(_matches(m, library) for m in _imports(path)):
                violations.append(f"{path.relative_to(APP_DIR)} importa {library}")
    assert not violations, "\n".join(violations)
