"""
SQLAlchemy 2.0 ORM models for Logistics Disruption Intelligence Agent.
Implements relational schema with foreign key cascades, check constraints,
and query-justified indexes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.0 declarative models."""
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    shipments: Mapped[list["Shipment"]] = relationship(
        "Shipment", back_populates="owner", cascade="all, delete-orphan"
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        "PipelineRun", back_populates="owner", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    shipment_id: Mapped[str] = mapped_column(String(40), nullable=False)
    origin: Mapped[str] = mapped_column(String(80), nullable=False)
    destination: Mapped[str] = mapped_column(String(80), nullable=False)
    route_highway: Mapped[str] = mapped_column(String(80), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_priority: Mapped[str] = mapped_column(String(20), nullable=False)  # HIGH, MEDIUM, LOW
    estimated_delivery_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cargo_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    weight_kg: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="IN_TRANSIT", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner: Mapped["User"] = relationship("User", back_populates="shipments")
    assessments: Mapped[list["RiskAssessment"]] = relationship(
        "RiskAssessment", back_populates="shipment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "shipment_id", name="uq_owner_shipment"),
        Index("ix_shipments_owner_shipment", "owner_id", "shipment_id"),
        Index("ix_shipments_owner_updated", "owner_id", "updated_at"),
    )


class Disruption(Base):
    __tablename__ = "disruptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # weather | news
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtype: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, default=150.0, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # HIGH, MEDIUM, LOW
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    assessments: Mapped[list["RiskAssessment"]] = relationship("RiskAssessment", back_populates="disruption")

    __table_args__ = (
        Index("ix_disruptions_valid_window", "valid_from", "valid_to"),
        Index("ix_disruptions_severity", "severity"),
        Index("ix_disruptions_location", "location"),
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING", nullable=False)  # RUNNING, COMPLETED, FAILED
    disruptions_collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shipments_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_risk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_risk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_risk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safe_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    collector_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="pipeline_runs")
    assessments: Mapped[list["RiskAssessment"]] = relationship(
        "RiskAssessment", back_populates="pipeline_run", cascade="all, delete-orphan"
    )
    traces: Mapped[list["AgentTrace"]] = relationship(
        "AgentTrace", back_populates="pipeline_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_pipeline_runs_owner_started", "owner_id", "started_at"),
    )


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    shipment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shipments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    disruption_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("disruptions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # HIGH, MEDIUM, LOW, SAFE
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact_duration_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="assessments")
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="assessments")
    disruption: Mapped[Optional["Disruption"]] = relationship("Disruption", back_populates="assessments")
    recommendation: Mapped[Optional["Recommendation"]] = relationship(
        "Recommendation", back_populates="assessment", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("score >= 0", name="chk_risk_score_positive"),
        CheckConstraint("level IN ('HIGH', 'MEDIUM', 'LOW', 'SAFE')", name="chk_risk_level_valid"),
        UniqueConstraint("run_id", "shipment_id", "disruption_id", name="uq_run_shipment_disruption"),
        Index("ix_assessments_run_shipment", "run_id", "shipment_id"),
        Index("ix_assessments_run_level", "run_id", "level"),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("risk_assessments.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    alternate_route: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    estimated_delay_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    customer_message: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="rules", nullable=False)  # llm | rules
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    assessment: Mapped["RiskAssessment"] = relationship("RiskAssessment", back_populates="recommendation")


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    node: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    used_llm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tokens_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="traces")

    __table_args__ = (
        Index("ix_agent_traces_run_node", "run_id", "node"),
    )
