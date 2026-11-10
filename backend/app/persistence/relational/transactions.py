"""Transacción de MySQL compartida entre repositorios."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import Transaction


class SqlTransaction:
    """Implementa el puerto Transaction. Los repositorios usan su sesión."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.rollback_requested = False

    def rollback(self) -> None:
        self.rollback_requested = True


def session_of(transaction: Transaction) -> Session:
    """Sesión de la transacción abierta por SqlTransactionManager."""
    if not isinstance(transaction, SqlTransaction):
        raise TypeError("Se esperaba una transacción de MySQL.")
    return transaction.session


class SqlTransactionManager:
    """Implementa el puerto TransactionManager sobre una sesión de SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def begin(self) -> Iterator[Transaction]:
        try:
            with self._session_factory() as session:
                transaction = SqlTransaction(session)
                try:
                    yield transaction
                except BaseException:
                    session.rollback()
                    raise
                if transaction.rollback_requested:
                    session.rollback()
                else:
                    session.commit()
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo completar la operación. Reintenta."
            ) from exc
