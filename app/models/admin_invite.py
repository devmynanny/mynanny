from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index

from app.db import Base
from app.utils.time import utc_now


class AdminInvite(Base):
    __tablename__ = "admin_invites"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="pending")  # pending, accepted, cancelled, expired
    created_at = Column(DateTime, nullable=False, default=utc_now)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)

    invited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    accepted_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    access_level = Column(String, nullable=False, default="operations")

    __table_args__ = (
        Index("ix_admin_invites_email_status", "email", "status"),
    )
