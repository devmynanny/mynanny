from sqlalchemy import Column, Integer, BigInteger, Date, Time, Text, Boolean, ForeignKey, DateTime, CheckConstraint, Index
from sqlalchemy.sql import func
from app.db import Base

class NannyAvailability(Base):
    __tablename__ = "nanny_availability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nanny_id = Column(BigInteger, ForeignKey("nannies.id", ondelete="CASCADE"), nullable=False)

    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    start_dt = Column(Text, nullable=True)
    end_dt = Column(Text, nullable=True)
    type = Column(Text, nullable=False, default="available")

    is_available = Column(Boolean, nullable=False, default=True)
    created_by = Column(Text, nullable=False, default="admin")
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("end_time > start_time", name="availability_time_check"),
        Index("na_nanny_date_idx", "nanny_id", "date"),
    )
