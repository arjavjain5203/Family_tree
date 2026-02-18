from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("trees.id"), nullable=False)
    name = Column(String, nullable=False)
    dob = Column(Date, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    phone = Column(String, nullable=True)
    generation_level = Column(Integer, nullable=False) # 1-4
    
    # Locking mechanism
    is_locked = Column(Boolean, default=False)
    locked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tree = relationship("Tree", back_populates="members")
    # relationships where this member is the parent
    children_relationships = relationship("Relationship", foreign_keys="Relationship.parent_id", back_populates="parent", cascade="all, delete-orphan")
    # relationships where this member is the child
    parent_relationships = relationship("Relationship", foreign_keys="Relationship.child_id", back_populates="child", cascade="all, delete-orphan")
    
    events = relationship("Event", back_populates="member", cascade="all, delete-orphan")

class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("trees.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("members.id"), nullable=False)

    tree = relationship("Tree")
    parent = relationship("Member", foreign_keys=[parent_id], back_populates="children_relationships")
    child = relationship("Member", foreign_keys=[child_id], back_populates="parent_relationships")
