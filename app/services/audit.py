import json

from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def record(action, entity_type, entity_id=None, details=None):
    actor_id = current_user.id if current_user.is_authenticated else None
    db.session.add(AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details or {}, default=str),
    ))
