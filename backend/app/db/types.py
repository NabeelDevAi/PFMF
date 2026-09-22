"""Small ORM type helpers shared across models."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


def pg_enum[E: Enum](enum_cls: type[E], name: str) -> SAEnum:
    """A Postgres-native enum column bound to a Python (Str)Enum, where the
    DB values are the enum's *values* ("income"), not its member *names*
    ("INCOME") -- SQLAlchemy's default is member names, which silently
    doesn't match the lowercase labels our migrations create by hand from
    the architecture doc's DDL. `create_type=False` because that raw DDL,
    not SQLAlchemy, is what creates the Postgres type.
    """
    return SAEnum(
        enum_cls, name=name, create_type=False, values_callable=lambda cls: [e.value for e in cls]
    )
