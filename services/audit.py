"""Registro de auditoría de acciones relevantes."""
from __future__ import annotations

from extensions import db
from models import AuditLog


def log_action(user, action: str, entity: str = None, entity_id: int = None,
               detail: str = None, commit: bool = False) -> None:
    """Agrega un registro de auditoría. Nunca registrar secretos.

    Por defecto no hace commit: se confía en la transacción que lo invoca.
    """
    entry = AuditLog(
        user_id=(user.id if user is not None else None),
        action=action,
        entity=entity,
        entity_id=entity_id,
        detail=detail,
    )
    db.session.add(entry)
    if commit:
        db.session.commit()
