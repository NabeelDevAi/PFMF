from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.categories import CategoryListOut, CategoryOut
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
