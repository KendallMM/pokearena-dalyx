"""Reglas de los criterios de búsqueda de cartas (historia Buscar carta)."""

from app.business.catalog.content.cards.card_rules import (
    MAX_COST,
    MAX_NAME_LENGTH,
    MAX_POWER,
    MIN_COST,
    MIN_POWER,
)
from app.business.catalog.search.models import CardCriteria, CardSearchRequest
from app.business.shared.errors import ValidationFailedError
from app.business.shared.text import normalize_for_search

DEFAULT_LIMIT = 20
MAX_LIMIT = 100  # acota el tamaño de cada respuesta


def build_criteria(request: CardSearchRequest) -> CardCriteria:
    """Valida los criterios y los deja listos para consultar.

    Lanza ValidationFailedError indicando el criterio inválido.
    """
    name = _clean(request.name)
    if name is not None and len(name) > MAX_NAME_LENGTH:
        raise ValidationFailedError(
            f"El nombre no puede superar {MAX_NAME_LENGTH} caracteres.", field="name"
        )
    code = _clean(request.code)
    cost_min, cost_max = _range(
        "cost", request.cost, request.cost_min, request.cost_max, MIN_COST, MAX_COST
    )
    power_min, power_max = _range(
        "power",
        request.power,
        request.power_min,
        request.power_max,
        MIN_POWER,
        MAX_POWER,
    )
    return CardCriteria(
        code=code.upper() if code else None,
        search_name=normalize_for_search(name) if name else None,
        cost_min=cost_min,
        cost_max=cost_max,
        power_min=power_min,
        power_max=power_max,
        card_type=_clean(request.card_type),
        rarity=_clean(request.rarity),
        ability=_clean(request.ability),
    )


def page_settings(request: CardSearchRequest) -> tuple[int, int]:
    """Devuelve (tamaño de página, cursor). El cursor 0 es el inicio del catálogo."""
    limit = DEFAULT_LIMIT if request.limit is None else request.limit
    if not 1 <= limit <= MAX_LIMIT:
        raise ValidationFailedError(
            f"El tamaño de página debe estar entre 1 y {MAX_LIMIT}.", field="limit"
        )
    last_id = 0 if request.last_id is None else request.last_id
    if last_id < 0:
        raise ValidationFailedError("El cursor no puede ser negativo.", field="last_id")
    return limit, last_id


def _clean(value: str | None) -> str | None:
    """Un criterio vacío es un criterio que no se usa."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def _range(
    name: str,
    exact: int | None,
    minimum: int | None,
    maximum: int | None,
    low: int,
    high: int,
) -> tuple[int | None, int | None]:
    """Acepta un valor exacto o un rango, nunca los dos."""
    if exact is not None and (minimum is not None or maximum is not None):
        raise ValidationFailedError(
            f"Use un valor exacto o un rango en {name}, no ambos.", field=name
        )
    if exact is not None:
        _check_bounds(name, exact, name, low, high)
        return exact, exact
    if minimum is not None:
        _check_bounds(name, minimum, f"{name}_min", low, high)
    if maximum is not None:
        _check_bounds(name, maximum, f"{name}_max", low, high)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValidationFailedError(
            f"El mínimo de {name} no puede ser mayor que el máximo.", field=name
        )
    return minimum, maximum


def _check_bounds(name: str, value: int, field: str, low: int, high: int) -> None:
    if not low <= value <= high:
        raise ValidationFailedError(
            f"El valor de {name} debe estar entre {low} y {high}.", field=field
        )
