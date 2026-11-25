"""ETag para consultas que cambian poco: el cliente evita descargar lo que ya tiene."""

import hashlib
import json
from typing import Any

# Caracteres del resumen SHA-256 que se usan como ETag.
ETAG_LENGTH = 32


def compute_etag(payload: Any) -> str:
    """ETag derivado del contenido: si el contenido cambia, el ETag también."""
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return (
        '"' + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:ETAG_LENGTH] + '"'
    )


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """Indica si el cliente ya tiene esta versión (cabecera If-None-Match)."""
    if not if_none_match:
        return False
    candidates = [part.strip().removeprefix("W/") for part in if_none_match.split(",")]
    return "*" in candidates or etag in candidates
