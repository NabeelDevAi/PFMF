from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.category import Category
from app.domain.enums import Direction
from app.repositories.category_repository import CategoryRepository
from app.repositories.overlay_repository import OverlayRepository
from app.repositories.transaction_repository import TransactionRepository


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.repo = CategoryRepository(db)
        self.transactions = TransactionRepository(db)
        self.overlays = OverlayRepository(db)

    def list_for_user(self, user_id: uuid.UUID) -> list[Category]:
        return self.repo.list_for_user(user_id)

    def create(self, user_id: uuid.UUID, *, name: str, direction: Direction) -> Category:
        return self.repo.create(user_id=user_id, name=name, direction=direction)

    def update(
        self,
        user_id: uuid.UUID,
        category_id: uuid.UUID,
        *,
        name: str | None = None,
        direction: Direction | None = None,
    ) -> Category:
        # get_owned_by_user, not get_visible_to_user: a system category is
        # 404-equivalent here, not editable at all (09 §3, same rule as
        # any other resource belonging to someone -- or no one -- else).
        category = self._get_owned(user_id, category_id)
        if name is not None:
            category.name = name
        if direction is not None:
            category.direction = direction
        self.repo.save(category)
        return category

    def delete(self, user_id: uuid.UUID, category_id: uuid.UUID) -> None:
        category = self._get_owned(user_id, category_id)
        # Neither FK (transactions.category_id, scenario_overlays.ovr_category_id)
        # has an ON DELETE rule -- checked explicitly rather than letting
        # Postgres's IntegrityError surface as an unhandled 500.
        if self.transactions.exists_with_category(
            user_id, category_id
        ) or self.overlays.exists_with_category_for_user(user_id, category_id):
            raise APIError("category.in_use")
        self.repo.delete(category)

    def _get_owned(self, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
        category = self.repo.get_owned_by_user(user_id, category_id)
        if category is None:
            raise APIError("resource.not_found")
        return category
