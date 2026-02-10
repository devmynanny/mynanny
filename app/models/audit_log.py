from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship

from app.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_role = Column(String, nullable=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    entity = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    action = Column(String, nullable=False)

    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    changed_fields = Column(Text, nullable=True)

    ip = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    event_type = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)
    details = Column(Text, nullable=True)

    actor = relationship("User", foreign_keys=[actor_user_id])

    __table_args__ = (
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        Index("ix_audit_logs_target_user_id", "target_user_id"),
        Index("ix_audit_logs_entity", "entity"),
        Index("ix_audit_logs_entity_id", "entity_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
