"""Referencias: entrega los valores que se pueden elegir en el formulario."""

from app.business.catalog.ports import ReferenceRepository
from typing import Any

from app.business.catalog.references.models import (
    EffectParameter,
    LocationEffectType,
    References,
)
from app.business.shared.errors import ValidationFailedError


class ReferenceService:
    """Caso de uso de lectura de referencias."""

    def __init__(self, repository: ReferenceRepository) -> None:
        self._repository = repository

    def get_references(self) -> References:
        """Devuelve todas las referencias en una sola lectura agrupada."""
        return References(
            card_types=self._repository.list_card_types(),
            rarities=self._repository.list_rarities(),
            abilities=self._repository.list_abilities(),
            location_effect_types=self._repository.list_location_effect_types(),
        )

    def validate_selection(
        self, card_type: str, rarity: str, ability: str | None
    ) -> None:
        """Comprueba que tipo, rareza y habilidad existan. Indica el campo inválido."""
        references = self.get_references()
        if card_type not in {t.code for t in references.card_types}:
            raise ValidationFailedError(
                "El tipo de carta no existe.", field="card_type"
            )
        if rarity not in {r.code for r in references.rarities}:
            raise ValidationFailedError("La rareza no existe.", field="rarity")
        if not ability:
            raise ValidationFailedError(
                "Debe elegir una habilidad, aunque sea Sin Habilidad.", field="ability"
            )
        if ability not in {a.code for a in references.abilities}:
            raise ValidationFailedError("La habilidad no existe.", field="ability")

    def validate_optional_selection(
        self, card_type: str | None, rarity: str | None, ability: str | None
    ) -> None:
        """Como validate_selection, pero cada valor es opcional (para filtrar)."""
        references = self.get_references()
        if card_type and card_type not in {t.code for t in references.card_types}:
            raise ValidationFailedError(
                "El tipo de carta no existe.", field="card_type"
            )
        if rarity and rarity not in {r.code for r in references.rarities}:
            raise ValidationFailedError("La rareza no existe.", field="rarity")
        if ability and ability not in {a.code for a in references.abilities}:
            raise ValidationFailedError("La habilidad no existe.", field="ability")

    def validate_location_effect(
        self, effect_type: str | None, parameters: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Valida el efecto de una ubicación y devuelve sus parámetros normalizados.

        Sin tipo de efecto no puede haber parámetros. Con tipo, sus parámetros se
        validan según el catálogo. Indica el campo inválido.
        """
        if not effect_type:
            if parameters:
                raise ValidationFailedError(
                    "No se pueden enviar parámetros sin un tipo de efecto.",
                    field="effect_parameters",
                )
            return {}
        references = self.get_references()
        catalog = {t.code: t for t in references.location_effect_types}
        if effect_type not in catalog:
            raise ValidationFailedError(
                "El tipo de efecto no existe.", field="effect_type"
            )
        card_type_codes = {t.code for t in references.card_types}
        return _validate_parameters(
            catalog[effect_type], parameters or {}, card_type_codes
        )


def _validate_parameters(
    effect: LocationEffectType, given: dict[str, Any], card_type_codes: set[str]
) -> dict[str, Any]:
    known = {p.name for p in effect.parameters}
    for name in given:
        if name not in known:
            raise ValidationFailedError(
                f"El efecto {effect.name} no tiene el parámetro {name}.",
                field=f"effect_parameters.{name}",
            )
    result: dict[str, Any] = {}
    for parameter in effect.parameters:
        field_name = f"effect_parameters.{parameter.name}"
        if given.get(parameter.name) is None:
            if parameter.required:
                raise ValidationFailedError(
                    f"El parámetro {parameter.name} es obligatorio.", field=field_name
                )
            continue
        result[parameter.name] = _validate_value(
            parameter, given[parameter.name], card_type_codes, field_name
        )
    return result


def _validate_value(
    parameter: EffectParameter, value: Any, card_type_codes: set[str], field_name: str
) -> Any:
    if parameter.kind == "integer":
        return _check_integer(parameter, value, field_name)
    if parameter.kind == "card_type":
        if value not in card_type_codes:
            raise ValidationFailedError(
                f"El tipo de carta del parámetro {parameter.name} no existe.",
                field=field_name,
            )
        return value
    if parameter.kind == "integer_list":
        if not isinstance(value, list) or not value:
            raise ValidationFailedError(
                f"El parámetro {parameter.name} debe ser una lista con al menos un valor.",
                field=field_name,
            )
        numbers = [_check_integer(parameter, item, field_name) for item in value]
        if len(set(numbers)) != len(numbers):
            raise ValidationFailedError(
                f"El parámetro {parameter.name} no puede repetir valores.",
                field=field_name,
            )
        return sorted(numbers)
    raise ValueError(f"Clase de parámetro desconocida: {parameter.kind}")


def _check_integer(parameter: EffectParameter, value: Any, field_name: str) -> int:
    # bool es subclase de int en Python, pero true/false no es un número válido.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationFailedError(
            f"El parámetro {parameter.name} debe ser un número entero.",
            field=field_name,
        )
    low, high = parameter.minimum, parameter.maximum
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValidationFailedError(
            f"El parámetro {parameter.name} debe estar entre {low} y {high}.",
            field=field_name,
        )
    return value
