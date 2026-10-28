"""Infraestructura: configuración, MySQL, MongoDB, imágenes, JWT, cursor e idempotencia.

Aquí vive todo lo que habla con el exterior (bases de datos, Pillow, tokens),
para que ``ability_engine`` se mantenga puro.
"""

import base64
import binascii
import hashlib
import hmac
import io
import json
import os
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image, UnidentifiedImageError
from pymongo.errors import PyMongoError
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.engine.ability_engine import (
    CARD_TYPES,
    MAX_IMAGE_PIXELS,
    NO_ABILITY_CODE,
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    ImageInfo,
    ImageRequirementError,
    InvalidCursorError,
    NotAuthenticatedError,
    PermissionDeniedError,
    StorageUnavailableError,
    TokenExpiredError,
)
from app.models.carta_model import (
    JOB_DONE,
    JOB_FAILED,
    JOB_PENDING,
    JOB_PROCESSING,
    JOB_RETRY,
    Ability,
    Base,
    CardCodeCounter,
    IdempotencyKey,
    ImageJob,
    utc_now,
)

# ======================================================================
# Configuración (variables de entorno)
# ======================================================================

MIN_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    """Falta una variable de entorno obligatoria o su valor no es válido."""


@dataclass(frozen=True)
class Settings:
    database_url: str
    mongo_url: str
    mongo_db_name: str
    jwt_secret: str
    cursor_secret: str
    jwt_algorithms: tuple[str, ...] = ("HS256",)
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    image_worker_poll_seconds: float = 5.0
    image_max_attempts: int = 5
    image_lock_seconds: int = 120
    image_retry_base_seconds: int = 10
    temporary_image_ttl_seconds: int = 3600
    run_image_worker: bool = True

    def __post_init__(self) -> None:
        for name in ("jwt_secret", "cursor_secret"):
            if len(getattr(self, name)) < MIN_SECRET_LENGTH:
                raise ConfigError(
                    f"{name} debe tener al menos {MIN_SECRET_LENGTH} caracteres."
                )
        if "none" in {alg.lower() for alg in self.jwt_algorithms}:
            raise ConfigError("El algoritmo JWT 'none' no está permitido.")


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"Falta la variable de entorno {name}.")
    return value


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Construye la configuración a partir de las variables de entorno."""
    env = os.environ if env is None else env
    algorithms = tuple(
        alg.strip() for alg in env.get("JWT_ALGORITHMS", "HS256").split(",") if alg
    )
    return Settings(
        database_url=_required(env, "DATABASE_URL"),
        mongo_url=_required(env, "MONGO_URL"),
        mongo_db_name=env.get("MONGO_DB_NAME", "pokearena"),
        jwt_secret=_required(env, "JWT_SECRET"),
        cursor_secret=_required(env, "CURSOR_SECRET"),
        jwt_algorithms=algorithms,
        jwt_issuer=env.get("JWT_ISSUER") or None,
        jwt_audience=env.get("JWT_AUDIENCE") or None,
        image_worker_poll_seconds=float(env.get("IMAGE_WORKER_POLL_SECONDS", "5")),
        image_max_attempts=int(env.get("IMAGE_MAX_ATTEMPTS", "5")),
        image_lock_seconds=int(env.get("IMAGE_LOCK_SECONDS", "120")),
        temporary_image_ttl_seconds=int(env.get("TEMPORARY_IMAGE_TTL_SECONDS", "3600")),
        run_image_worker=env.get("RUN_IMAGE_WORKER", "true").lower() != "false",
    )


# ======================================================================
# Conexión a MySQL y esquema inicial
# ======================================================================


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Crea las tablas si no existen y siembra los datos mínimos.

    Se usa ``create_all`` porque el proyecto aún no define migraciones.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        existing = await session.scalar(
            select(Ability.id).where(Ability.code == NO_ABILITY_CODE)
        )
        if existing is None:
            session.add(
                Ability(
                    code=NO_ABILITY_CODE,
                    name="Sin Habilidad",
                    trigger_type=None,
                    condition_type=None,
                    effect_type=None,
                    target_type=None,
                    affected_type=None,
                    parameters={},
                )
            )
        present = set(await session.scalars(select(CardCodeCounter.card_type)))
        for card_type in CARD_TYPES:
            if card_type not in present:
                session.add(CardCodeCounter(card_type=card_type, last_number=0))


# ======================================================================
# JWT del administrador (PyJWT)
# ======================================================================

ADMIN_ROLE = "admin"


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise NotAuthenticatedError("Falta el encabezado Authorization.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise NotAuthenticatedError("El encabezado Authorization debe ser Bearer.")
    return token.strip()


def authenticate_admin(authorization: str | None, settings: Settings) -> Principal:
    """Valida el token y exige rol administrador.

    Los algoritmos permitidos salen solo de la configuración del servidor (nunca
    del encabezado del token). 401 = no autenticado o vencido; 403 = sin permiso.
    """
    token = extract_bearer_token(authorization)
    options: dict[str, object] = {"require": ["exp", "sub"]}
    if settings.jwt_audience is None:
        options["verify_aud"] = False
    if settings.jwt_issuer is not None:
        options["require"] = ["exp", "sub", "iss"]
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=list(settings.jwt_algorithms),
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options=options,  # type: ignore[arg-type]
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("La sesión venció. Inicie sesión de nuevo.") from exc
    except jwt.InvalidTokenError as exc:
        raise NotAuthenticatedError("El token no es válido.") from exc

    subject, role = claims.get("sub"), claims.get("role")
    if not isinstance(subject, str) or not subject or not isinstance(role, str):
        raise NotAuthenticatedError("El token no contiene usuario o rol.")
    if role != ADMIN_ROLE:
        raise PermissionDeniedError("Solo un administrador puede hacer esto.")
    return Principal(user_id=subject, role=role)


# ======================================================================
# Cursores firmados con HMAC
# ======================================================================


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _sign(body: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), body.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def encode_cursor(payload: dict[str, Any], secret: str) -> str:
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body, secret)}"


def decode_cursor(cursor: str, secret: str) -> dict[str, Any]:
    """Verifica la firma y devuelve el contenido; lanza ``InvalidCursorError``."""
    error = InvalidCursorError("El cursor no es válido.", field="cursor")
    body, separator, signature = cursor.partition(".")
    if not separator or not body.isascii():
        raise error
    if not hmac.compare_digest(signature.encode(), _sign(body, secret).encode()):
        raise error
    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, binascii.Error):
        raise error from None
    if not isinstance(payload, dict):
        raise error
    return payload


# ======================================================================
# Imágenes con Pillow
# ======================================================================

_FORMAT_NAMES = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WEBP"}


def _not_an_image() -> ImageRequirementError:
    return ImageRequirementError(
        "El archivo no es una imagen válida (PNG, JPG o WebP).",
        field="image",
        details={"requirement": "format"},
    )


def inspect_image(data: bytes) -> ImageInfo:
    """Lee formato y dimensiones reales sin decodificar todos los píxeles."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            return ImageInfo(
                image_format=image.format or "",
                width=image.width,
                height=image.height,
            )
    except Image.DecompressionBombError:
        return ImageInfo(image_format="PNG", width=MAX_IMAGE_PIXELS, height=2)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise _not_an_image() from None


def ensure_decodable(data: bytes) -> None:
    """Decodifica la imagen completa para detectar archivos corruptos."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageRequirementError(
            "La imagen está dañada y no se puede leer.",
            field="image",
            details={"requirement": "corrupt"},
        ) from None


def make_thumbnail(data: bytes, size: tuple[int, int]) -> tuple[bytes, str]:
    """Devuelve (bytes, formato) de la miniatura exacta ``size``."""
    with Image.open(io.BytesIO(data)) as image:
        image_format = image.format or "PNG"
        image.load()
        if image_format == "JPEG":
            converted = image.convert("RGB")
        elif image.mode in ("RGB", "RGBA", "L", "LA"):
            converted = image.copy()
        else:
            converted = image.convert("RGBA")
        thumbnail = converted.resize(size, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        thumbnail.save(output, format=image_format)
        return output.getvalue(), image_format


# ======================================================================
# Imágenes en MongoDB
# ======================================================================

STATUS_TEMPORARY = "TEMPORARY"
STATUS_ATTACHED = "ATTACHED"


class ImageStore:
    """Una colección por tipo de entidad (``card_images``, ``location_images``)."""

    def __init__(self, collection: Any) -> None:
        self._collection = collection

    async def ensure_indexes(self) -> None:
        # Mongo borra solo los documentos temporales vencidos (TTL).
        await self._collection.create_index(
            "temporary_expires_at", expireAfterSeconds=0
        )

    async def save_temporary(
        self, image_ref: str, content_type: str, original: bytes, ttl_seconds: int
    ) -> None:
        now = utc_now()
        await self._collection.insert_one(
            {
                "_id": image_ref,
                "content_type": content_type,
                "original": original,
                "thumbnail": None,
                "status": STATUS_TEMPORARY,
                "temporary_expires_at": now + timedelta(seconds=ttl_seconds),
                "created_at": now,
            }
        )

    async def attach(self, image_ref: str) -> None:
        """Marca la imagen como definitiva: deja de vencer."""
        await self._collection.update_one(
            {"_id": image_ref},
            {
                "$set": {"status": STATUS_ATTACHED},
                "$unset": {"temporary_expires_at": ""},
            },
        )

    async def delete(self, image_ref: str) -> None:
        await self._collection.delete_one({"_id": image_ref})

    async def get(self, image_ref: str) -> dict[str, Any] | None:
        return await self._collection.find_one({"_id": image_ref})

    async def set_thumbnail(
        self, image_ref: str, thumbnail: bytes, content_type: str
    ) -> None:
        await self._collection.update_one(
            {"_id": image_ref},
            {
                "$set": {
                    "thumbnail": thumbnail,
                    "thumbnail_content_type": content_type,
                    "status": STATUS_ATTACHED,
                },
                "$unset": {"temporary_expires_at": ""},
            },
        )

    async def has_both(self, image_ref: str) -> bool:
        document = await self._collection.find_one(
            {"_id": image_ref}, {"original": 1, "thumbnail": 1}
        )
        return bool(document and document.get("original") and document.get("thumbnail"))


# ======================================================================
# Repositorio de idempotencia
# ======================================================================


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(
        self, user_id: str, endpoint: str, key_value: str
    ) -> IdempotencyKey | None:
        return await self._session.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.key_value == key_value,
            )
        )

    async def reserve(
        self, user_id: str, endpoint: str, key_value: str, request_hash: str
    ) -> IdempotencyKey:
        """Inserta la llave; si otra solicitud la tiene, falla por UNIQUE."""
        record = IdempotencyKey(
            user_id=user_id,
            endpoint=endpoint,
            key_value=key_value,
            request_hash=request_hash,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def complete(self, record_id: int, response_body: dict[str, Any]) -> None:
        await self._session.execute(
            update(IdempotencyKey)
            .where(IdempotencyKey.id == record_id)
            .values(response_body=response_body)
        )


# ======================================================================
# Repositorio de trabajos de imagen
# ======================================================================


class ImageJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entity_type: str, entity_id: int, image_ref: str) -> ImageJob:
        job = ImageJob(
            entity_type=entity_type, entity_id=entity_id, image_ref=image_ref
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: int) -> ImageJob | None:
        return await self._session.get(ImageJob, job_id)

    async def latest_for(self, entity_type: str, entity_id: int) -> ImageJob | None:
        return await self._session.scalar(
            select(ImageJob)
            .where(ImageJob.entity_type == entity_type, ImageJob.entity_id == entity_id)
            .order_by(ImageJob.id.desc())
            .limit(1)
        )

    async def due_job_ids(self, limit: int = 20) -> list[int]:
        """Trabajos listos para correr o con el bloqueo vencido (worker caído)."""
        now = utc_now()
        rows = await self._session.scalars(
            select(ImageJob.id)
            .where(self._claimable(now))
            .order_by(ImageJob.id)
            .limit(limit)
        )
        return list(rows)

    @staticmethod
    def _claimable(now):
        return or_(
            and_(
                ImageJob.status.in_([JOB_PENDING, JOB_RETRY]),
                ImageJob.next_attempt_at <= now,
            ),
            and_(ImageJob.status == JOB_PROCESSING, ImageJob.locked_until < now),
        )

    async def claim(self, job_id: int, lock_seconds: int) -> bool:
        """Reclama el trabajo con un UPDATE condicional (solo uno lo logra)."""
        now = utc_now()
        result = await self._session.execute(
            update(ImageJob)
            .where(ImageJob.id == job_id, self._claimable(now))
            .values(
                status=JOB_PROCESSING,
                locked_until=now + timedelta(seconds=lock_seconds),
                attempts=ImageJob.attempts + 1,
                updated_at=now,
            )
        )
        return result.rowcount == 1

    async def mark_done(self, job_id: int) -> None:
        await self._session.execute(
            update(ImageJob)
            .where(ImageJob.id == job_id)
            .values(
                status=JOB_DONE,
                locked_until=None,
                last_error=None,
                updated_at=utc_now(),
            )
        )

    async def mark_failed_attempt(
        self, job_id: int, error: str, *, final: bool, retry_in_seconds: int
    ) -> None:
        now = utc_now()
        await self._session.execute(
            update(ImageJob)
            .where(ImageJob.id == job_id)
            .values(
                status=JOB_FAILED if final else JOB_RETRY,
                next_attempt_at=now + timedelta(seconds=retry_in_seconds),
                locked_until=None,
                last_error=error[:1000],
                updated_at=now,
            )
        )


# ======================================================================
# Flujo común de creación con imagen
# ======================================================================

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")

BuildEntity = Callable[[AsyncSession], Awaitable[tuple[dict[str, Any], int]]]


@dataclass(frozen=True)
class CreationResult:
    status_code: int
    body: dict[str, Any]
    job_id: int | None


def parse_idempotency_key(value: str | None) -> str:
    key = (value or "").strip()
    if not _KEY_PATTERN.match(key):
        raise IdempotencyKeyRequiredError(
            "Falta el encabezado Idempotency-Key (1 a 128 caracteres: letras, "
            "números, punto, guion, guion bajo o dos puntos).",
            field="Idempotency-Key",
        )
    return key


def compute_request_hash(fields: dict[str, Any], image: bytes | None) -> str:
    digest = hashlib.sha256(image or b"").hexdigest()
    canonical = json.dumps(
        {"fields": fields, "image": digest}, sort_keys=True, ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class CreationFlow:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        image_store: ImageStore,
        temporary_ttl_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._store = image_store
        self._ttl = temporary_ttl_seconds

    async def find_replay(
        self, user_id: str, endpoint: str, key: str, request_hash: str
    ) -> CreationResult | None:
        """Si la llave ya se usó: misma solicitud -> 200 con la respuesta original."""
        async with self._session_factory() as session:
            record = await IdempotencyRepository(session).find(user_id, endpoint, key)
        if record is None or record.response_body is None:
            return None
        if record.request_hash != request_hash:
            raise IdempotencyConflictError(
                "Esta Idempotency-Key ya se usó con datos distintos.",
                field="Idempotency-Key",
            )
        return CreationResult(200, record.response_body, None)

    async def execute(
        self,
        *,
        user_id: str,
        endpoint: str,
        key: str,
        request_hash: str,
        image_ref: str,
        content_type: str,
        image_bytes: bytes,
        build: BuildEntity,
    ) -> CreationResult:
        try:
            await self._store.save_temporary(
                image_ref, content_type, image_bytes, self._ttl
            )
        except PyMongoError as exc:
            raise StorageUnavailableError(
                "No se pudo guardar la imagen. Intente de nuevo."
            ) from exc

        try:
            body, job_id = await self._run_transaction(
                user_id, endpoint, key, request_hash, build
            )
        except IntegrityError:
            # Otra solicitud con la misma llave ganó la carrera: se reproduce su
            # respuesta. Si no es ese caso, es un error real y se propaga.
            await self._discard(image_ref)
            replay = await self.find_replay(user_id, endpoint, key, request_hash)
            if replay is None:
                raise
            return replay
        except BaseException:
            await self._discard(image_ref)
            raise

        try:
            await self._store.attach(image_ref)
        except PyMongoError:
            # No es grave: el worker deja la imagen como definitiva al procesarla.
            pass
        return CreationResult(202, body, job_id)

    async def _run_transaction(
        self,
        user_id: str,
        endpoint: str,
        key: str,
        request_hash: str,
        build: BuildEntity,
    ) -> tuple[dict[str, Any], int]:
        async with self._session_factory() as session, session.begin():
            idempotency = IdempotencyRepository(session)
            record = await idempotency.reserve(user_id, endpoint, key, request_hash)
            body, job_id = await build(session)
            await idempotency.complete(record.id, body)
            return body, job_id

    async def _discard(self, image_ref: str) -> None:
        try:
            await self._store.delete(image_ref)
        except PyMongoError:
            pass  # el índice TTL la eliminará cuando venza


# ======================================================================
# Dependencias de FastAPI
# ======================================================================

# Declara el esquema Bearer para que Swagger muestre el botón "Authorize".
# auto_error=False: los errores los arma nuestro propio manejador (401 con formato).
bearer_scheme = HTTPBearer(auto_error=False, description="JWT de administrador")


def get_container(request: Request) -> Any:
    return request.app.state.container


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    container = request.app.state.container
    authorization = (
        f"{credentials.scheme} {credentials.credentials}" if credentials else None
    )
    # Si el encabezado no es "Bearer ...", HTTPBearer no lo entrega: se lee crudo
    # para devolver el mismo error de autenticación.
    if authorization is None:
        authorization = request.headers.get("Authorization")
    return authenticate_admin(authorization, container.settings)
