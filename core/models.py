import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from core.db import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    google_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=False)
    name = Column(String, nullable=False)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    saved_files = relationship("SavedFile", back_populates="user", cascade="all, delete-orphan")


class Folder(Base):
    __tablename__ = "folders"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    user = relationship("User", back_populates="folders")
    saved_files = relationship("SavedFile", back_populates="folder", cascade="all, delete-orphan")


class SavedFile(Base):
    __tablename__ = "saved_files"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id = Column(String, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    midi_url = Column(String, nullable=False)
    wav_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    user = relationship("User", back_populates="saved_files")
    folder = relationship("Folder", back_populates="saved_files")
