from __future__ import annotations

import uuid

from sqlalchemy import or_, select
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
