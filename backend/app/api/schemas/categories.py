from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.domain.enums import Direction


class CategoryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    key: str | None
    name: str | None
    direction: Direction
    sort_order: int

    model_config = {"from_attributes": True}


class CategoryListOut(BaseModel):
    items: list[CategoryOut]


class CategoryCreate(BaseModel):
    name: str
    direction: Direction


class CategoryPatch(BaseModel):
    name: str | None = None
    direction: Direction | None = None
