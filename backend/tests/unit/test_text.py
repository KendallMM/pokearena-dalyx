"""Normalización de texto para la búsqueda."""

import pytest

from app.business.shared.text import normalize_for_search


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pikachu", "pikachu"),
        ("PIKACHU", "pikachu"),
        ("Pikáchú", "pikachu"),
        ("Ñandú Eléctrico", "nandu electrico"),
        ("  Mr.   Mime  ", "mr. mime"),
        ("Flabébé", "flabebe"),
        ("", ""),
    ],
)
def test_normalize_for_search(text, expected) -> None:
    assert normalize_for_search(text) == expected


def test_same_word_with_and_without_accent_matches() -> None:
    assert normalize_for_search("Psíquico") == normalize_for_search("psiquico")
