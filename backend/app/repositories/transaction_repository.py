from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction | None:
        return self.db.scalar(
            select(Transaction).where(
                Transaction.id == transaction_id, Transaction.user_id == user_id
            )
        )

    def list_by_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.scenario_id == scenario_id, Transaction.user_id == user_id)
            .order_by(Transaction.created_at)
        )
        return list(self.db.scalars(stmt))

    def list_all_for_user(self, user_id: uuid.UUID) -> list[Transaction]:
        """Every transaction this user owns, across every scenario --
        for GET /me/export (backend-plan/08's data section)."""
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.scenario_id, Transaction.created_at)
        )
        return list(self.db.scalars(stmt))

    def count_for_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.scenario_id == scenario_id, Transaction.user_id == user_id)
        )

    def create(self, *, user_id: uuid.UUID, scenario_id: uuid.UUID, **fields) -> Transaction:
        txn = Transaction(user_id=user_id, scenario_id=scenario_id, **fields)
        self.db.add(txn)
        self.db.flush()
        return txn

    def save(self, txn: Transaction) -> None:
        self.db.flush()

    def delete(self, txn: Transaction) -> None:
        self.db.delete(txn)
        self.db.flush()

    def delete_all_for_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> None:
        """Bulk delete -- used by account reset to empty Base's own
        transactions (Base itself is never deleted, only its rows)."""
        self.db.execute(
            delete(Transaction).where(
                Transaction.scenario_id == scenario_id, Transaction.user_id == user_id
            )
        )
        self.db.flush()
