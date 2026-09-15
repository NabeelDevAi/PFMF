from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.scenarios import (
    ScenarioCreate,
    ScenarioDuplicateRequest,
    ScenarioListOut,
    ScenarioOut,
    ScenarioPatch,
)
from app.db.models.user import User
from app.db.session import get_db
from app.services.scenario_service import ScenarioService

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=ScenarioListOut)
def list_scenarios(
    include_archived: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioListOut:
    scenarios = ScenarioService(db).list_for_user(user.id, include_archived=include_archived)
    return ScenarioListOut(items=[ScenarioOut.model_validate(s) for s in scenarios])


@router.post("", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def create_scenario(
    body: ScenarioCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScenarioOut:
    scenario = ScenarioService(db).create(
        user.id, name=body.name, current_balance_override_minor=body.current_balance_override_minor
    )
    db.commit()
    return ScenarioOut.model_validate(scenario)


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(
    scenario_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScenarioOut:
    scenario = ScenarioService(db).get(user.id, scenario_id)
    return ScenarioOut.model_validate(scenario)


@router.patch("/{scenario_id}", response_model=ScenarioOut)
def patch_scenario(
    scenario_id: uuid.UUID,
    body: ScenarioPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    scenario = ScenarioService(db).patch(
        user.id,
        scenario_id,
        name=body.name,
        current_balance_override_minor=body.current_balance_override_minor,
        _unset_current_balance_override=body.unset_current_balance_override,
    )
    db.commit()
    return ScenarioOut.model_validate(scenario)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    ScenarioService(db).delete(user.id, scenario_id)
    db.commit()


@router.post(
    "/{scenario_id}/duplicate", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED
)
def duplicate_scenario(
    scenario_id: uuid.UUID,
    body: ScenarioDuplicateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    copy = ScenarioService(db).duplicate(user.id, scenario_id, name=body.name)
    db.commit()
    return ScenarioOut.model_validate(copy)


@router.post("/{scenario_id}/archive", response_model=ScenarioOut)
def archive_scenario(
    scenario_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScenarioOut:
    scenario = ScenarioService(db).archive(user.id, scenario_id)
    db.commit()
    return ScenarioOut.model_validate(scenario)


@router.post("/{scenario_id}/unarchive", response_model=ScenarioOut)
def unarchive_scenario(
    scenario_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScenarioOut:
    scenario = ScenarioService(db).unarchive(user.id, scenario_id)
    db.commit()
    return ScenarioOut.model_validate(scenario)
