"""Utilidades de texto compartidas por la lógica de negocio."""

import unicodedata


def normalize_for_search(text: str) -> str:
    """Minúsculas, sin tildes y con espacios simples, para buscar sin distinguir
    mayúsculas ni tildes. Se aplica igual al guardar y al buscar."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_marks.casefold().split())
