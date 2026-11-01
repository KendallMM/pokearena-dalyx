"""Referencias: entrega los valores que se pueden elegir en el formulario."""

from app.business.catalog.ports import ReferenceRepository
from app.business.catalog.references.models import References


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
