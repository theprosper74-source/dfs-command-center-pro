from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Slate(Base):
    __tablename__ = "slates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport: Mapped[str] = mapped_column(String(8), index=True)
    name: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(80), default="DraftKings CSV")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    players = relationship("Player", back_populates="slate", cascade="all, delete-orphan")

class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slate_id: Mapped[int] = mapped_column(ForeignKey("slates.id"), index=True)
    sport: Mapped[str] = mapped_column(String(8), index=True)
    external_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    positions: Mapped[str] = mapped_column(String(80))
    team: Mapped[str] = mapped_column(String(16), default="")
    opponent: Mapped[str] = mapped_column(String(16), default="")
    salary: Mapped[int] = mapped_column(Integer)
    game_info: Mapped[str] = mapped_column(String(160), default="")
    source_avg: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(80), default="DraftKings CSV")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.5)
    projection: Mapped[float] = mapped_column(Float, default=0)
    floor: Mapped[float] = mapped_column(Float, default=0)
    ceiling: Mapped[float] = mapped_column(Float, default=0)
    ownership: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    slate = relationship("Slate", back_populates="players")

class Lineup(Base):
    __tablename__ = "lineups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slate_id: Mapped[int] = mapped_column(ForeignKey("slates.id"), index=True)
    sport: Mapped[str] = mapped_column(String(8))
    strategy: Mapped[str] = mapped_column(String(40))
    salary: Mapped[int] = mapped_column(Integer)
    projection: Mapped[float] = mapped_column(Float)
    player_ids: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slate_id: Mapped[int] = mapped_column(ForeignKey("slates.id"), index=True)
    runs: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    results_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
