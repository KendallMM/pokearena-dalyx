"""Repositorio de cubos: saldo del jugador y su historial de movimientos."""

from sqlalchemy import select, update

from app.business.shared.ports import Transaction
from app.persistence.relational.models import CubeMovementRow, PlayerRow
from app.persistence.relational.transactions import session_of


class SqlCubeRepository:
    """Implementa el puerto CubeRepository. Saldo e historial cambian juntos."""

    def credit(
        self,
        transaction: Transaction,
        player_id: str,
        amount: int,
        reason: str,
        reference: str,
    ) -> int:
        """Registra el movimiento y actualiza el saldo; devuelve el saldo nuevo.

        UNIQUE (motivo, referencia) impide registrar dos veces la misma operación.
        """
        session = session_of(transaction)
        # Bloquea el saldo del jugador hasta el final de la transacción, para que
        # dos movimientos simultáneos no calculen el saldo sobre el mismo valor.
        current = session.scalar(
            select(PlayerRow.cubes).where(PlayerRow.id == player_id).with_for_update()
        )
        balance = current + amount
        session.add(
            CubeMovementRow(
                player_id=player_id,
                amount=amount,
                balance_after=balance,
                reason=reason,
                reference=reference,
            )
        )
        session.flush()
        session.execute(
            update(PlayerRow).where(PlayerRow.id == player_id).values(cubes=balance)
        )
        return balance
