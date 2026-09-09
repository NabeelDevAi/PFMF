# The pure forecasting engine. Built in milestone M1 (see
# claude_docs/backend-plan/04-engine-module.md and 11-build-order-and-milestones.md).
#
# Boundary rule: nothing in this package imports from app.api, app.db,
# app.services, app.repositories, or app.core, and nothing here imports
# SQLAlchemy, FastAPI, or Pydantic. Plain values in, plain values out.
