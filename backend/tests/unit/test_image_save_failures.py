"""Feedback del profesor: si MongoDB falla al guardar la imagen, no se guarda nada.

Antes de insertar en MySQL, Cartas y Ubicaciones guardan la imagen en MongoDB. Si
ese guardado falla, el flujo debe detenerse con un 503 y el repositorio relacional
nunca debe recibir la carta o la ubicación (no puede quedar un registro sin imagen).
"""

import pytest

from app.business.shared.errors import ServiceUnavailableError
from tests.unit.test_card_service import _command as card_command
from tests.unit.test_location_service import _command as location_command


def test_card_is_not_inserted_when_mongo_fails_to_save_the_image(
    card_service, image_store, card_repository, events
) -> None:
    image_store.fail_save = True
    with pytest.raises(ServiceUnavailableError):
        card_service.create_card(card_command())
    assert card_repository.added == []
    assert events == []


def test_location_is_not_inserted_when_mongo_fails_to_save_the_image(
    location_service, image_store, location_repository, events
) -> None:
    image_store.fail_save = True
    with pytest.raises(ServiceUnavailableError):
        location_service.create_location(location_command())
    assert location_repository.added == []
    assert events == []


def test_image_is_deleted_when_mysql_fails_after_saving_it(
    card_service, image_store, card_repository, events
) -> None:
    card_repository.fail_with = ServiceUnavailableError("MySQL no responde")
    with pytest.raises(ServiceUnavailableError):
        card_service.create_card(card_command())
    assert events == ["image_saved", "card_added"]
    assert image_store.deleted == ["img-1"]
