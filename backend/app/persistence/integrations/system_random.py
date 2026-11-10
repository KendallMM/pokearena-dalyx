"""Azar del servidor."""

import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class SystemRandomSource:
    """Implementa el puerto RandomSource con la fuente segura del sistema operativo.

    El cliente no puede predecir ni influir en el resultado (RNF-SEG-06).
    """

    def __init__(self) -> None:
        self._random = random.SystemRandom()

    def sample(self, population: Sequence[T], k: int) -> list[T]:
        return self._random.sample(population, k)
