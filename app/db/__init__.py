from app.db.base import Base
from app.db.models import (  # noqa: F401 — import so Alembic sees all models
    AIRun,
    ActionItem,
    ItemHistory,
    KBDocument,
    KBLink,
    Meeting,
    Participant,
    Person,
)

