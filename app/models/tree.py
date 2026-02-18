from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class Role(str, enum.Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"

class Tree(Base):
    __tablename__ = "trees"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True) # One tree per user (owner)
    generation_limit = Column(Integer, default=4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="owned_tree", lazy="selectin")
    members = relationship("Member", back_populates="tree", cascade="all, delete-orphan")
    access_list = relationship("TreeAccess", back_populates="tree", cascade="all, delete-orphan")

class TreeAccess(Base):
    __tablename__ = "tree_access"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("trees.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(Role), default=Role.VIEWER)

    tree = relationship("Tree", back_populates="access_list")
    user = relationship("User", backref="accessed_trees")
