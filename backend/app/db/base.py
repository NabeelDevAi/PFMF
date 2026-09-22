"""Declarative base for all ORM models.

Deliberately empty of models right now -- the first ones land in milestone M2
(see claude_docs/backend-plan/03-database-schema-and-migrations.md). Alembic's
env.py points at Base.metadata so every model that ever gets defined against
this base is automatically visible to migrations without further wiring.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
