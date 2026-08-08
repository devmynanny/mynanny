from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db import Base
from app.utils.time import utc_now


class AdminProfile(Base):
    __tablename__ = "admin_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    is_superadmin = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User")
