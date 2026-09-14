from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.categories import CategoryCreate, CategoryListOut, CategoryOut, CategoryPatch
from app.db.models.user import User
from app.db.session import get_db
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListOut)
def list_categories(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CategoryListOut:
    categories = CategoryService(db).list_for_user(user.id)
    return CategoryListOut(items=[CategoryOut.model_validate(c) for c in categories])


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CategoryOut:
    category = CategoryService(db).create(user.id, name=body.name, direction=body.direction)
    db.commit()
    return CategoryOut.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryOut)
def patch_category(
    category_id: uuid.UUID,
    body: CategoryPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategoryOut:
    category = CategoryService(db).update(
        user.id, category_id, name=body.name, direction=body.direction
    )
    db.commit()
    return CategoryOut.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    CategoryService(db).delete(user.id, category_id)
    db.commit()
