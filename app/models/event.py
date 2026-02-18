from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    event_type = Column(String, nullable=False) # e.g., "Anniversary", "Birthday"
    event_date = Column(Date, nullable=False)
    description = Column(String, nullable=True)

    member = relationship("Member", back_populates="events")
