from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models.category import Category
from app.domain.enums import Direction
from app.repositories.category_repository import CategoryRepository


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.repo = CategoryRepository(db)

    def list_for_user(self, user_id: uuid.UUID) -> list[Category]:
        return self.repo.list_for_user(user_id)

    def create(self, user_id: uuid.UUID, *, name: str, direction: Direction) -> Category:
        return self.repo.create(user_id=user_id, name=name, direction=direction)
