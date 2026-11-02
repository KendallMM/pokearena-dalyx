"""Referencias: entrega los valores que se pueden elegir en el formulario."""

from app.business.catalog.ports import ReferenceRepository
from app.business.catalog.references.models import References
from app.business.shared.errors import ValidationFailedError


class ReferenceService:
    """Caso de uso de lectura de referencias."""

    def __init__(self, repository: ReferenceRepository) -> None:
        self._repository = repository

    def get_references(self) -> References:
        """Devuelve tipos, rarezas y habilidades en una sola lectura agrupada."""
        return References(
            card_types=self._repository.list_card_types(),
            rarities=self._repository.list_rarities(),
            abilities=self._repository.list_abilities(),
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
