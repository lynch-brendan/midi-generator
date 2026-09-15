import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
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

    # Stripe / subscription fields
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_plan = Column(String, nullable=True)      # "creator" | "pro" | None
    subscription_status = Column(String, nullable=True)    # "active" | "canceled" | "past_due" | …

    # Usage tracking
    lifetime_generations = Column(Integer, default=0, nullable=False)
    monthly_generations = Column(Integer, default=0, nullable=False)
    monthly_reset_date = Column(DateTime(timezone=True), nullable=True)

    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    saved_files = relationship("SavedFile", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")


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
    project_id = Column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    midi_url = Column(String, nullable=False)
    wav_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    user = relationship("User", back_populates="saved_files")
    folder = relationship("Folder", back_populates="saved_files")
    project = relationship("Project", back_populates="saved_files")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    daw_state = Column(Text, nullable=True)  # JSON: {bpm, clips: [...]}

    user = relationship("User", back_populates="projects")
    saved_files = relationship("SavedFile", back_populates="project", cascade="all, delete-orphan")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    stripe_event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    received_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class NastyChatLog(Base):
    """Per-chat log of Nasty AI Chat conversations. Purpose: build a training
    corpus for a future Nasty-tuned model. Every /nasty/chat request writes
    one row. Anonymous by default (no user id linkage unless we add it later).
    """
    __tablename__ = "nasty_chat_logs"

    id = Column(String, primary_key=True, default=_uuid)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    # Session grouping — same "session_id" across turns of one Nasty session.
    # Client sends this from localStorage so we can reconstruct conversations.
    session_id = Column(String, nullable=True, index=True)
    # What the user asked and what Claude said back.
    user_message = Column(Text, nullable=False)
    ai_text = Column(Text, nullable=True)
    # Full tool_calls array as JSON string so we can reconstruct what Claude DID.
    tool_calls_json = Column(Text, nullable=True)
    # Snapshot of song state at request time (JSON string), for context.
    song_state_json = Column(Text, nullable=True)
    # Plugin names the user had installed at request time (comma-separated).
    plugin_names = Column(Text, nullable=True)
    # Token accounting: sum across all tool-use iterations for this message.
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cache_read_tokens = Column(Integer, nullable=True)
    cache_write_tokens = Column(Integer, nullable=True)
    # stop_reason from the final iteration.
    stop_reason = Column(String, nullable=True)
