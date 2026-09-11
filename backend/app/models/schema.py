import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="RTSP")  # RTSP, VIDEO_FILE, WEBCAM
    source_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DISCONNECTED", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    # Relationships
    zones: Mapped[list["Zone"]] = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="camera", cascade="all, delete-orphan")
    anpr_records: Mapped[list["ANPRRecord"]] = relationship("ANPRRecord", back_populates="camera", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(50), default="RESTRICTED", nullable=False)  # RESTRICTED, MONITORING
    polygon_json: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="zones")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="zone")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), default="INFO", nullable=False, index=True)  # INFO, WARNING, HIGH, CRITICAL
    object_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zone_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False)

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="events")
    zone: Mapped[Optional["Zone"]] = relationship("Zone", back_populates="events")


class ANPRRecord(Base):
    __tablename__ = "anpr_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    plate_text: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quality: Mapped[str] = mapped_column(String(30), default="HIGH", nullable=False)  # HIGH, MEDIUM, LOW, UNREADABLE
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), default="car", nullable=False)
    vehicle_bbox_json: Mapped[str] = mapped_column(String(100), nullable=False)
    plate_bbox_json: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    evidence_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="anpr_records")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

