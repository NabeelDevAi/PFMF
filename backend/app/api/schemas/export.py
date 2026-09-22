from __future__ import annotations

import csv
import io
import uuid
import zipfile
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.api.schemas.categories import CategoryOut
from app.api.schemas.me import SettingsOut
from app.api.schemas.overlays import OverlayOut
from app.api.schemas.scenarios import ScenarioOut
from app.domain.enums import Direction, Recurrence

if TYPE_CHECKING:
    from app.services.export_service import ExportData


class ExportUserOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportTransactionOut(BaseModel):
    """Same fields as TransactionOut minus `origin` -- a raw row has no
    origin of its own, that's only meaningful through a resolved view
    (Origin's docstring in app.domain.enums)."""

    id: uuid.UUID
    scenario_id: uuid.UUID
    name: str
    amount_minor: int
    direction: Direction
    category_id: uuid.UUID | None
    notes: str | None
    recurrence: Recurrence
    start_date: date
    end_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExportOut(BaseModel):
    user: ExportUserOut
    settings: SettingsOut
    categories: list[CategoryOut]
    scenarios: list[ScenarioOut]
    transactions: list[ExportTransactionOut]
    overlays: list[OverlayOut]

    @classmethod
    def from_data(cls, data: ExportData) -> ExportOut:
        return cls(
            user=ExportUserOut.model_validate(data.user),
            settings=SettingsOut.model_validate(data.settings),
            categories=[CategoryOut.model_validate(c) for c in data.categories],
            scenarios=[ScenarioOut.model_validate(s) for s in data.scenarios],
            transactions=[ExportTransactionOut.model_validate(t) for t in data.transactions],
            overlays=[OverlayOut.model_validate(o) for o in data.overlays],
        )


def _write_csv(rows: list[dict], fieldnames: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def export_to_csv_zip(data: ExportData) -> bytes:
    """The CSV counterpart to ExportOut.from_data -- same raw, unresolved
    tables (this is a reconstructable backup, not a resolved financial
    statement), just serialized as five CSV files instead of one JSON
    tree. A single flat CSV can't hold five differently-shaped tables,
    so this bundles them as a ZIP -- a standard, well-understood shape
    for a "multi-table data export" download, and no new dependency:
    csv/io/zipfile are all stdlib.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "account.csv",
            _write_csv(
                [
                    {
                        "user_id": str(data.user.id),
                        "email": data.user.email,
                        "created_at": data.user.created_at.isoformat(),
                        "display_name": data.settings.display_name,
                        "currency_code": data.settings.currency_code,
                        "locale": data.settings.locale,
                        "current_balance_minor": data.settings.current_balance_minor,
                        "balance_as_of": data.settings.balance_as_of.isoformat(),
                    }
                ],
                [
                    "user_id",
                    "email",
                    "created_at",
                    "display_name",
                    "currency_code",
                    "locale",
                    "current_balance_minor",
                    "balance_as_of",
                ],
            ),
        )
        zf.writestr(
            "categories.csv",
            _write_csv(
                [
                    {
                        "id": str(c.id),
                        "key": c.key or "",  # blank here -- only user-owned rows get exported
                        "name": c.name or "",
                        "direction": c.direction.value,
                        "sort_order": c.sort_order,
                    }
                    for c in data.categories
                ],
                ["id", "key", "name", "direction", "sort_order"],
            ),
        )
        zf.writestr(
            "scenarios.csv",
            _write_csv(
                [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "is_base": s.is_base,
                        "current_balance_override_minor": s.current_balance_override_minor,
                        "archived_at": s.archived_at.isoformat() if s.archived_at else "",
                        "created_at": s.created_at.isoformat(),
                        "updated_at": s.updated_at.isoformat(),
                    }
                    for s in data.scenarios
                ],
                [
                    "id",
                    "name",
                    "is_base",
                    "current_balance_override_minor",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ],
            ),
        )
        zf.writestr(
            "transactions.csv",
            _write_csv(
                [
                    {
                        "id": str(t.id),
                        "scenario_id": str(t.scenario_id),
                        "name": t.name,
                        "amount_minor": t.amount_minor,
                        "direction": t.direction.value,
                        "category_id": str(t.category_id) if t.category_id else "",
                        "notes": t.notes or "",
                        "recurrence": t.recurrence.value,
                        "start_date": t.start_date.isoformat(),
                        "end_date": t.end_date.isoformat() if t.end_date else "",
                        "created_at": t.created_at.isoformat(),
                        "updated_at": t.updated_at.isoformat(),
                    }
                    for t in data.transactions
                ],
                [
                    "id",
                    "scenario_id",
                    "name",
                    "amount_minor",
                    "direction",
                    "category_id",
                    "notes",
                    "recurrence",
                    "start_date",
                    "end_date",
                    "created_at",
                    "updated_at",
                ],
            ),
        )
        zf.writestr(
            "overlays.csv",
            _write_csv(
                [
                    {
                        "id": str(o.id),
                        "scenario_id": str(o.scenario_id),
                        "base_transaction_id": str(o.base_transaction_id),
                        "op": o.op.value,
                        "ovr_name": o.ovr_name or "",
                        "ovr_amount_minor": o.ovr_amount_minor
                        if o.ovr_amount_minor is not None
                        else "",
                        "ovr_category_id": str(o.ovr_category_id) if o.ovr_category_id else "",
                        "ovr_recurrence": o.ovr_recurrence.value if o.ovr_recurrence else "",
                        "ovr_start_date": o.ovr_start_date.isoformat() if o.ovr_start_date else "",
                        "ovr_end_date": o.ovr_end_date.isoformat() if o.ovr_end_date else "",
                        "unset_end_date": o.unset_end_date,
                        "created_at": o.created_at.isoformat(),
                    }
                    for o in data.overlays
                ],
                [
                    "id",
                    "scenario_id",
                    "base_transaction_id",
                    "op",
                    "ovr_name",
                    "ovr_amount_minor",
                    "ovr_category_id",
                    "ovr_recurrence",
                    "ovr_start_date",
                    "ovr_end_date",
                    "unset_end_date",
                    "created_at",
                ],
            ),
        )
    return buf.getvalue()
