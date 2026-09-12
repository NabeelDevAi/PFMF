from __future__ import annotations

import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db.models.category import Category


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: uuid.UUID) -> list[Category]:
        """System categories (user_id NULL) plus this user's own, ordered
        the way the client should render them."""
        stmt = (
            select(Category)
            .where(or_(Category.user_id.is_(None), Category.user_id == user_id))
            .order_by(Category.direction, Category.sort_order)
        )
        return list(self.db.scalars(stmt))

    def list_owned_by_user(self, user_id: uuid.UUID) -> list[Category]:
        """This user's own categories only, excluding system ones -- for
        GET /me/export (a personal data export has no business including
        global reference data)."""
        stmt = (
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.direction, Category.sort_order)
        )
        return list(self.db.scalars(stmt))

    def delete_all_owned_by_user(self, user_id: uuid.UUID) -> None:
        self.db.execute(delete(Category).where(Category.user_id == user_id))
        self.db.flush()

    def get_visible_to_user(self, user_id: uuid.UUID, category_id: uuid.UUID) -> Category | None:
        """A system category (visible to everyone) or one this user owns --
        used to validate a transaction's category_id belongs to a category
        this user is actually allowed to use."""
        return self.db.scalar(
            select(Category).where(
                Category.id == category_id,
                or_(Category.user_id.is_(None), Category.user_id == user_id),
            )
        )
