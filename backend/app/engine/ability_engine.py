"""Motor de reglas del juego (Microkernel de habilidades y reglas de negocio).

Todo lo que hay aquí es puro: no depende de FastAPI, SQLAlchemy, MongoDB, Pillow
ni JWT. Contiene catálogos, errores del dominio y las validaciones de carta,
ubicación, imagen y búsqueda.
"""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Final

# ======================================================================
# Catálogos cerrados y límites del dominio de contenido del juego.
# ======================================================================

# --- Cartas -------------------------------------------------------------

CARD_TYPES: Final[tuple[str, ...]] = (
    "Fuego",
    "Agua",
    "Planta",
    "Eléctrico",
    "Psíquico",
    "Lucha",
)

# Abreviatura usada en el código PKA-<TIPO>-<NNN>.
CARD_TYPE_PREFIX: Final[dict[str, str]] = {
    "Fuego": "FUE",
    "Agua": "AGU",
    "Planta": "PLA",
    "Eléctrico": "ELE",
    "Psíquico": "PSI",
    "Lucha": "LUC",
}

RARITIES: Final[tuple[str, ...]] = ("Común", "Poco común", "Rara", "Legendaria")

COST_MIN: Final[int] = 0
COST_MAX: Final[int] = 10
POWER_MIN: Final[int] = -20
POWER_MAX: Final[int] = 20
NAME_MAX_LENGTH: Final[int] = 100

# --- Habilidades (solo lo necesario para crear y buscar cartas) ----------

NO_ABILITY_CODE: Final[str] = "HAB-000"
EVOLUTION_EFFECT: Final[str] = "Evolucionar"
EVOLUTION_TARGET_KEY: Final[str] = "target_card_code"

# Catálogos de disparador y efecto: se necesitan para validar el criterio de
# búsqueda "por disparador y efecto". La creación de habilidades es otro user
# story y no forma parte de este sprint.
ABILITY_TRIGGERS: Final[tuple[str, ...]] = ("Al revelarse", "Continuo")
ABILITY_EFFECTS: Final[tuple[str, ...]] = (
    "Modificar poder",
    "Modificar costo",
    "Ganar energía",
    "Mover",
    "Destruir",
    "Descartar",
    EVOLUTION_EFFECT,
)

# --- Ubicaciones --------------------------------------------------------

EFFECT_TYPE_BONUS: Final[str] = "type_bonus"
EFFECT_TYPE_COST: Final[str] = "cost_modifier"
EFFECT_TYPE_RESTRICTION: Final[str] = "turn_restriction"
LOCATION_EFFECT_TYPES: Final[tuple[str, ...]] = (
    EFFECT_TYPE_BONUS,
    EFFECT_TYPE_COST,
    EFFECT_TYPE_RESTRICTION,
)

EFFECT_AMOUNT_MIN: Final[int] = -5
EFFECT_AMOUNT_MAX: Final[int] = 5
GAME_TURNS: Final[int] = 6

CARD_LIMIT_MIN: Final[int] = 0
CARD_LIMIT_MAX: Final[int] = 5

ENERGY_MODE_FIXED: Final[str] = "fixed"
ENERGY_MODE_PER_CARD: Final[str] = "per_card"
ENERGY_MODES: Final[tuple[str, ...]] = (ENERGY_MODE_FIXED, ENERGY_MODE_PER_CARD)
# Rango del monto de energía extra según la modalidad.
ENERGY_AMOUNT_RANGE: Final[dict[str, tuple[int, int]]] = {
    ENERGY_MODE_FIXED: (0, 3),
    ENERGY_MODE_PER_CARD: (0, 2),
}

LOCATION_DESCRIPTION_MAX_LENGTH: Final[int] = 255

# --- Estados de imagen (compartidos por cartas y ubicaciones) ------------

STATUS_PENDING_IMAGE: Final[str] = "PENDING_IMAGE"
STATUS_RETRY_IMAGE: Final[str] = "RETRY_IMAGE"
STATUS_READY: Final[str] = "READY"
CONTENT_STATUSES: Final[tuple[str, ...]] = (
    STATUS_PENDING_IMAGE,
    STATUS_RETRY_IMAGE,
    STATUS_READY,
)

# --- Búsqueda -----------------------------------------------------------

SEARCH_DEFAULT_LIMIT: Final[int] = 50
SEARCH_MAX_LIMIT: Final[int] = 50
SEARCH_TEXT_MAX_LENGTH: Final[int] = 100


# ======================================================================
# Errores del dominio.
# ======================================================================


class DomainError(Exception):
    """Error base de las reglas de negocio."""

    code = "domain_error"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = details


class NotAuthenticatedError(DomainError):
    """No hay credenciales válidas ("no sé quién eres")."""

    code = "not_authenticated"


class TokenExpiredError(NotAuthenticatedError):
    """La credencial de acceso venció; el cliente debe renovar la sesión."""

    code = "token_expired"


class PermissionDeniedError(DomainError):
    """El usuario está autenticado pero no tiene permiso ("no tienes permiso")."""

    code = "permission_denied"


class InvalidFieldError(DomainError):
    """Un campo o criterio tiene un valor fuera de lo permitido."""

    code = "invalid_field"


class ImageRequirementError(InvalidFieldError):
    """La imagen incumple un requisito (formato, peso, resolución, proporción)."""

    code = "invalid_image"


class InvalidAbilityError(InvalidFieldError):
    """El código de habilidad no existe o no se indicó."""

    code = "invalid_ability"


class EvolutionRuleError(InvalidFieldError):
    """La habilidad de evolución apunta a la misma carta o forma un ciclo."""

    code = "invalid_evolution"


class InvalidCursorError(DomainError):
    """El cursor de paginación está alterado, mal formado o no es compatible."""

    code = "invalid_cursor"


class NotFoundError(DomainError):
    """El recurso solicitado no existe."""

    code = "not_found"


class IdempotencyKeyRequiredError(DomainError):
    """Falta el encabezado Idempotency-Key o su formato no es válido."""

    code = "idempotency_key_required"


class IdempotencyConflictError(DomainError):
    """La misma Idempotency-Key se reutilizó con una solicitud distinta."""

    code = "idempotency_key_reused"


class StorageUnavailableError(DomainError):
    """Un almacén (base de datos o imágenes) no respondió; se puede reintentar."""

    code = "storage_unavailable"


# ======================================================================
# Utilidades de texto del dominio.
# ======================================================================

_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Normaliza un texto para comparar sin tildes, mayúsculas ni espacios extra.

    Ejemplo: ``"  Pikáchu  Eléctrico "`` -> ``"pikachu electrico"``.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _WHITESPACE.sub(" ", without_marks).strip().casefold()


def escape_like(value: str, escape_char: str = "\\") -> str:
    """Escapa los comodines de LIKE para que se busquen como texto literal."""
    return (
        value.replace(escape_char, escape_char * 2)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )


# ======================================================================
# Requisitos de las imágenes de cartas y ubicaciones (reglas puras).
# ======================================================================

MAX_IMAGE_BYTES: Final[int] = 5 * 1024 * 1024
# Protección contra imágenes comprimidas que se expanden a memoria enorme.
MAX_IMAGE_PIXELS: Final[int] = 40_000_000
ALLOWED_FORMATS: Final[tuple[str, ...]] = ("PNG", "JPEG", "WEBP")

CONTENT_TYPE_BY_FORMAT: Final[dict[str, str]] = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}


@dataclass(frozen=True)
class ImageSpec:
    """Requisitos de una imagen: proporción, resolución mínima y miniatura."""

    ratio_width: int
    ratio_height: int
    min_width: int
    min_height: int
    thumbnail_width: int
    thumbnail_height: int

    @property
    def ratio_label(self) -> str:
        return f"{self.ratio_width}:{self.ratio_height}"

    @property
    def thumbnail_size(self) -> tuple[int, int]:
        return (self.thumbnail_width, self.thumbnail_height)


# Carta: vertical 5:7, mínimo 600x840, miniatura 200x280.
CARD_IMAGE_SPEC: Final[ImageSpec] = ImageSpec(5, 7, 600, 840, 200, 280)
# Ubicación: horizontal 4:3, mínimo 800x600, miniatura 320x240.
LOCATION_IMAGE_SPEC: Final[ImageSpec] = ImageSpec(4, 3, 800, 600, 320, 240)


@dataclass(frozen=True)
class ImageInfo:
    """Datos leídos de la imagen real (no de lo que declara el cliente)."""

    image_format: str
    width: int
    height: int


def _fail(message: str, requirement: str, **extra: object) -> ImageRequirementError:
    return ImageRequirementError(
        message, field="image", details={"requirement": requirement, **extra}
    )


def validate_image_size(size_bytes: int) -> None:
    """Rechaza archivos vacíos o de más de 5 MB."""
    if size_bytes == 0:
        raise _fail("La imagen está vacía.", "empty")
    if size_bytes > MAX_IMAGE_BYTES:
        raise _fail(
            "La imagen supera los 5 MB permitidos.",
            "max_size",
            max_bytes=MAX_IMAGE_BYTES,
        )


def validate_image_info(info: ImageInfo, spec: ImageSpec) -> None:
    """Valida formato real, resolución mínima y proporción exacta."""
    if info.image_format not in ALLOWED_FORMATS:
        raise _fail(
            "Formato de imagen no permitido. Use PNG, JPG o WebP.",
            "format",
            allowed=["PNG", "JPG", "WebP"],
        )
    if info.width * info.height > MAX_IMAGE_PIXELS:
        raise _fail(
            "Las dimensiones de la imagen son demasiado grandes.",
            "dimensions_too_large",
            max_pixels=MAX_IMAGE_PIXELS,
        )
    if info.width < spec.min_width or info.height < spec.min_height:
        raise _fail(
            f"La resolución mínima es {spec.min_width} x {spec.min_height} píxeles.",
            "min_resolution",
            min_width=spec.min_width,
            min_height=spec.min_height,
        )
    # Comparación entera exacta: ancho/alto == ratio_width/ratio_height.
    if info.width * spec.ratio_height != info.height * spec.ratio_width:
        raise _fail(
            f"La proporción de la imagen debe ser {spec.ratio_label}.",
            "ratio",
            ratio=spec.ratio_label,
        )


# ======================================================================
# Reglas de negocio para crear una carta (sin dependencias de infraestructura).
# ======================================================================


@dataclass(frozen=True)
class CardDraft:
    """Datos de una carta ya validados, listos para guardarse."""

    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability_code: str

    @property
    def name_search(self) -> str:
        """Nombre normalizado para búsquedas sin tildes ni mayúsculas."""
        return normalize_text(self.name)


def _require_int(value: object, field: str, label: str) -> int:
    if value is None:
        raise InvalidFieldError(f"El campo {label} es obligatorio.", field=field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidFieldError(f"El campo {label} debe ser un entero.", field=field)
    return value


def _require_in_range(value: int, field: str, label: str, low: int, high: int) -> int:
    if not low <= value <= high:
        raise InvalidFieldError(
            f"El campo {label} debe estar entre {low} y {high}.",
            field=field,
            details={"min": low, "max": high},
        )
    return value


def _require_choice(
    value: str | None, field: str, label: str, allowed: tuple[str, ...]
) -> str:
    if value is None or not value.strip():
        raise InvalidFieldError(
            f"El campo {label} es obligatorio.",
            field=field,
            details={"allowed": list(allowed)},
        )
    if value not in allowed:
        raise InvalidFieldError(
            f"El campo {label} tiene un valor no permitido: '{value}'.",
            field=field,
            details={"allowed": list(allowed)},
        )
    return value


def validate_card_draft(
    *,
    name: str | None,
    cost: int | None,
    power: int | None,
    card_type: str | None,
    rarity: str | None,
    ability_code: str | None,
) -> CardDraft:
    """Valida los campos de una carta y devuelve el borrador normalizado.

    Lanza ``InvalidFieldError`` indicando el campo inválido, o
    ``InvalidAbilityError`` cuando no se eligió habilidad.
    """
    clean_name = (name or "").strip()
    if not clean_name:
        raise InvalidFieldError("El campo nombre es obligatorio.", field="name")
    if len(clean_name) > NAME_MAX_LENGTH:
        raise InvalidFieldError(
            f"El nombre no puede superar {NAME_MAX_LENGTH} caracteres.",
            field="name",
            details={"max_length": NAME_MAX_LENGTH},
        )

    valid_cost = _require_in_range(
        _require_int(cost, "cost", "costo"),
        "cost",
        "costo",
        COST_MIN,
        COST_MAX,
    )
    valid_power = _require_in_range(
        _require_int(power, "power", "poder"),
        "power",
        "poder",
        POWER_MIN,
        POWER_MAX,
    )
    valid_type = _require_choice(card_type, "type", "tipo", CARD_TYPES)
    valid_rarity = _require_choice(rarity, "rarity", "rareza", RARITIES)

    if ability_code is None or not ability_code.strip():
        raise InvalidAbilityError(
            "Debe elegir una habilidad, aunque sea Sin Habilidad "
            f"({NO_ABILITY_CODE}).",
            field="ability",
        )

    return CardDraft(
        name=clean_name,
        cost=valid_cost,
        power=valid_power,
        card_type=valid_type,
        rarity=valid_rarity,
        ability_code=ability_code.strip().upper(),
    )


def format_card_code(card_type: str, sequence_number: int) -> str:
    """Arma el código ``PKA-<TIPO>-<NNN>`` (consecutivo de al menos 3 dígitos).

    Si un tipo supera las 999 cartas el consecutivo crece a 4 dígitos en lugar
    de repetir códigos.
    """
    prefix = CARD_TYPE_PREFIX[card_type]
    return f"PKA-{prefix}-{sequence_number:03d}"


def ensure_evolution_is_valid(
    new_card_code: str,
    evolution_target: str | None,
    evolution_edges: Mapping[str, str],
) -> None:
    """Rechaza evoluciones que apunten a la misma carta o formen un ciclo.

    ``evolution_edges`` mapea el código de cada carta existente con una
    habilidad de evolución a su carta destino. Se recorre la cadena que parte
    del destino con un conjunto de visitados, así que siempre termina.
    """
    if evolution_target is None:
        return
    if evolution_target == new_card_code:
        raise EvolutionRuleError(
            "La habilidad de evolución no puede tener como destino la misma carta.",
            field="ability",
        )
    visited = {new_card_code}
    current: str | None = evolution_target
    while current is not None:
        if current in visited:
            raise EvolutionRuleError(
                "La habilidad de evolución forma un ciclo entre cartas.",
                field="ability",
            )
        visited.add(current)
        current = evolution_edges.get(current)


# ======================================================================
# Reglas de negocio para crear una ubicación (sin infraestructura).
# ======================================================================


@dataclass(frozen=True)
class LocationEffect:
    """Efecto de una ubicación: tipo del catálogo y sus parámetros ya validados."""

    effect_type: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocationDraft:
    """Configuración de una ubicación ya validada."""

    name: str
    description: str
    effect: LocationEffect | None
    card_limit: int
    extra_energy_mode: str
    extra_energy_amount: int


def _int_in_range(
    value: object, field_name: str, label: str, low: int, high: int
) -> int:
    if value is None:
        raise InvalidFieldError(f"El campo {label} es obligatorio.", field=field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidFieldError(
            f"El campo {label} debe ser un entero.", field=field_name
        )
    if not low <= value <= high:
        raise InvalidFieldError(
            f"El campo {label} debe estar entre {low} y {high}.",
            field=field_name,
            details={"min": low, "max": high},
        )
    return value


def _text(value: str | None, field_name: str, label: str, max_length: int) -> str:
    clean = (value or "").strip()
    if not clean:
        raise InvalidFieldError(f"El campo {label} es obligatorio.", field=field_name)
    if len(clean) > max_length:
        raise InvalidFieldError(
            f"El campo {label} no puede superar {max_length} caracteres.",
            field=field_name,
            details={"max_length": max_length},
        )
    return clean


def _validate_effect(
    effect_type: str | None,
    card_type: str | None,
    amount: int | None,
    turns: list[int] | None,
) -> LocationEffect | None:
    has_params = card_type is not None or amount is not None or bool(turns)

    if effect_type is None:
        if has_params:
            raise InvalidFieldError(
                "Se enviaron parámetros de efecto sin indicar el tipo de efecto.",
                field="effect_type",
                details={"allowed": list(LOCATION_EFFECT_TYPES)},
            )
        return None

    if effect_type not in LOCATION_EFFECT_TYPES:
        raise InvalidFieldError(
            f"El tipo de efecto '{effect_type}' no existe.",
            field="effect_type",
            details={"allowed": list(LOCATION_EFFECT_TYPES)},
        )

    if effect_type == EFFECT_TYPE_RESTRICTION:
        _reject_unused("effect_card_type", card_type, effect_type)
        _reject_unused("effect_amount", amount, effect_type)
        return LocationEffect(effect_type, {"turns": _validate_turns(turns)})

    # Los otros dos tipos usan monto; el turnos no aplica.
    _reject_unused("effect_restricted_turns", turns or None, effect_type)
    valid_amount = _int_in_range(
        amount,
        "effect_amount",
        "monto del efecto",
        EFFECT_AMOUNT_MIN,
        EFFECT_AMOUNT_MAX,
    )

    if effect_type == EFFECT_TYPE_BONUS:
        if card_type is None:
            raise InvalidFieldError(
                "La bonificación por tipo exige un tipo de carta.",
                field="effect_card_type",
                details={"allowed": list(CARD_TYPES)},
            )
        return LocationEffect(
            effect_type,
            {"card_type": _valid_card_type(card_type), "amount": valid_amount},
        )

    # Modificador de costo: el tipo afectado es opcional.
    affected = None if card_type is None else _valid_card_type(card_type)
    return LocationEffect(effect_type, {"amount": valid_amount, "card_type": affected})


def _valid_card_type(card_type: str) -> str:
    if card_type not in CARD_TYPES:
        raise InvalidFieldError(
            f"El tipo de carta '{card_type}' no existe.",
            field="effect_card_type",
            details={"allowed": list(CARD_TYPES)},
        )
    return card_type


def _validate_turns(turns: list[int] | None) -> list[int]:
    if not turns:
        raise InvalidFieldError(
            "La restricción por turno exige al menos un turno.",
            field="effect_restricted_turns",
        )
    for turn in turns:
        _int_in_range(turn, "effect_restricted_turns", "turno", 1, GAME_TURNS)
    if len(set(turns)) != len(turns):
        raise InvalidFieldError(
            "Los turnos de la restricción no pueden repetirse.",
            field="effect_restricted_turns",
        )
    return sorted(turns)


def _reject_unused(field_name: str, value: object, effect_type: str) -> None:
    if value is not None:
        raise InvalidFieldError(
            f"El parámetro {field_name} no corresponde al efecto '{effect_type}'.",
            field=field_name,
        )


def validate_location_draft(
    *,
    name: str | None,
    description: str | None,
    effect_type: str | None,
    effect_card_type: str | None,
    effect_amount: int | None,
    effect_restricted_turns: list[int] | None,
    card_limit: int | None,
    extra_energy_mode: str | None,
    extra_energy_amount: int | None,
) -> LocationDraft:
    """Valida la configuración de una ubicación según el catálogo de efectos."""
    clean_name = _text(name, "name", "nombre", NAME_MAX_LENGTH)
    clean_description = _text(
        description,
        "description",
        "descripción",
        LOCATION_DESCRIPTION_MAX_LENGTH,
    )
    effect = _validate_effect(
        effect_type, effect_card_type, effect_amount, effect_restricted_turns
    )
    valid_limit = _int_in_range(
        card_limit,
        "card_limit",
        "límite de cartas",
        CARD_LIMIT_MIN,
        CARD_LIMIT_MAX,
    )

    if extra_energy_mode is None or extra_energy_mode not in ENERGY_MODES:
        raise InvalidFieldError(
            "La modalidad de energía extra no existe.",
            field="extra_energy_mode",
            details={"allowed": list(ENERGY_MODES)},
        )
    low, high = ENERGY_AMOUNT_RANGE[extra_energy_mode]
    valid_amount = _int_in_range(
        extra_energy_amount,
        "extra_energy_amount",
        "monto de energía extra",
        low,
        high,
    )

    return LocationDraft(
        name=clean_name,
        description=clean_description,
        effect=effect,
        card_limit=valid_limit,
        extra_energy_mode=extra_energy_mode,
        extra_energy_amount=valid_amount,
    )


# ======================================================================
# Criterios de búsqueda de cartas: validación y normalización.
# ======================================================================

_CARD_CODE = re.compile(r"^PKA-[A-Z]{3}-\d{3,}$")
_ABILITY_CODE = re.compile(r"^HAB-\d{3,}$")


@dataclass(frozen=True)
class CardSearchCriteria:
    """Criterios ya validados. Los que valen ``None`` no se aplican.

    Todos los criterios activos se combinan con AND. ``name_search`` ya viene
    normalizado (sin tildes, en minúsculas).
    """

    code: str | None = None
    name_search: str | None = None
    cost_min: int | None = None
    cost_max: int | None = None
    power_min: int | None = None
    power_max: int | None = None
    card_type: str | None = None
    rarity: str | None = None
    ability_code: str | None = None
    ability_trigger: str | None = None
    ability_effect: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa los criterios (se incluyen dentro del cursor firmado)."""
        return asdict(self)


def _blank_to_none(value: str | None) -> str | None:
    """Un filtro vacío equivale a no enviarlo."""
    if value is None or not value.strip():
        return None
    return value.strip()


def _choice(value: str | None, field: str, label: str, allowed: tuple[str, ...]):
    clean = _blank_to_none(value)
    if clean is None:
        return None
    if clean not in allowed:
        raise InvalidFieldError(
            f"El criterio {label} tiene un valor no permitido: '{clean}'.",
            field=field,
            details={"allowed": list(allowed)},
        )
    return clean


def _numeric_range(
    *,
    exact: int | None,
    minimum: int | None,
    maximum: int | None,
    field: str,
    label: str,
    low: int,
    high: int,
) -> tuple[int | None, int | None]:
    """Convierte valor exacto o rango en un par (mínimo, máximo)."""
    if exact is not None and (minimum is not None or maximum is not None):
        raise InvalidFieldError(
            f"Use {field} (valor exacto) o {field}_min/{field}_max (rango), no ambos.",
            field=field,
        )
    if exact is not None:
        minimum = maximum = exact
        checked = {field: exact}
    else:
        checked = {f"{field}_min": minimum, f"{field}_max": maximum}

    for name, value in checked.items():
        if value is not None and not low <= value <= high:
            raise InvalidFieldError(
                f"El criterio {label} debe estar entre {low} y {high}.",
                field=name,
                details={"min": low, "max": high},
            )
    if minimum is not None and maximum is not None and minimum > maximum:
        raise InvalidFieldError(
            f"En el rango de {label} el mínimo no puede ser mayor que el máximo.",
            field=f"{field}_min",
        )
    return minimum, maximum


def validate_search_criteria(
    *,
    code: str | None = None,
    name: str | None = None,
    cost: int | None = None,
    cost_min: int | None = None,
    cost_max: int | None = None,
    power: int | None = None,
    power_min: int | None = None,
    power_max: int | None = None,
    card_type: str | None = None,
    rarity: str | None = None,
    ability_code: str | None = None,
    ability_trigger: str | None = None,
    ability_effect: str | None = None,
) -> CardSearchCriteria:
    """Valida los criterios recibidos y devuelve los normalizados.

    Lanza ``InvalidFieldError`` indicando el criterio inválido.
    """
    clean_code = _blank_to_none(code)
    if clean_code is not None:
        clean_code = clean_code.upper()
        if not _CARD_CODE.match(clean_code):
            raise InvalidFieldError(
                "El código de carta debe tener el formato PKA-<TIPO>-<NNN>.",
                field="code",
            )

    clean_name = _blank_to_none(name)
    name_search = None
    if clean_name is not None:
        if len(clean_name) > SEARCH_TEXT_MAX_LENGTH:
            raise InvalidFieldError(
                "El nombre a buscar es demasiado largo.",
                field="name",
                details={"max_length": SEARCH_TEXT_MAX_LENGTH},
            )
        name_search = normalize_text(clean_name)

    cost_lo, cost_hi = _numeric_range(
        exact=cost,
        minimum=cost_min,
        maximum=cost_max,
        field="cost",
        label="costo",
        low=COST_MIN,
        high=COST_MAX,
    )
    power_lo, power_hi = _numeric_range(
        exact=power,
        minimum=power_min,
        maximum=power_max,
        field="power",
        label="poder",
        low=POWER_MIN,
        high=POWER_MAX,
    )

    clean_ability_code = _blank_to_none(ability_code)
    if clean_ability_code is not None:
        clean_ability_code = clean_ability_code.upper()
        if not _ABILITY_CODE.match(clean_ability_code):
            raise InvalidFieldError(
                "El código de habilidad debe tener el formato HAB-<NNN>.",
                field="ability_code",
            )

    return CardSearchCriteria(
        code=clean_code,
        name_search=name_search,
        cost_min=cost_lo,
        cost_max=cost_hi,
        power_min=power_lo,
        power_max=power_hi,
        card_type=_choice(card_type, "type", "tipo", CARD_TYPES),
        rarity=_choice(rarity, "rarity", "rareza", RARITIES),
        ability_code=clean_ability_code,
        ability_trigger=_choice(
            ability_trigger,
            "ability_trigger",
            "disparador",
            ABILITY_TRIGGERS,
        ),
        ability_effect=_choice(
            ability_effect, "ability_effect", "efecto", ABILITY_EFFECTS
        ),
    )


def validate_page_limit(limit: int | None) -> int:
    """Valida el tamaño de página (por defecto 50, máximo 50)."""
    if limit is None:
        return SEARCH_DEFAULT_LIMIT
    if not 1 <= limit <= SEARCH_MAX_LIMIT:
        raise InvalidFieldError(
            f"El límite debe estar entre 1 y {SEARCH_MAX_LIMIT}.",
            field="limit",
            details={"min": 1, "max": SEARCH_MAX_LIMIT},
        )
    return limit


# ======================================================================
# Microkernel de habilidades
# ======================================================================


class AbilityMicrokernel:
    """Reglas de habilidades.

    Antes el registro de habilidades era un diccionario en memoria con datos
    inventados. Ahora las habilidades viven en la tabla ``abilities`` (MySQL);
    este microkernel solo contiene las reglas que no dependen de la base.
    """

    no_ability_code = NO_ABILITY_CODE

    @staticmethod
    def evolution_target(
        effect_type: str | None, parameters: dict | None
    ) -> str | None:
        """Carta destino si la habilidad es de evolución; ``None`` en otro caso."""
        if effect_type != EVOLUTION_EFFECT:
            return None
        target = (parameters or {}).get(EVOLUTION_TARGET_KEY)
        return target if isinstance(target, str) and target else None

    @staticmethod
    def ensure_evolution_is_valid(
        new_card_code: str,
        evolution_target: str | None,
        evolution_edges: Mapping[str, str],
    ) -> None:
        ensure_evolution_is_valid(new_card_code, evolution_target, evolution_edges)


# Instancia global del motor (Microkernel Core)
ability_engine = AbilityMicrokernel()
