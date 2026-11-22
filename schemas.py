from pydantic import BaseModel, Field
from typing import Optional

class ProjectionRequest(BaseModel):
    slate_id: int

class SimulationRequest(BaseModel):
    slate_id: int
    runs: int = Field(default=5000, ge=100, le=50000)
    seed: int = 42

class Slot(BaseModel):
    name: str
    eligible: list[str]

class OptimizerRequest(BaseModel):
    slate_id: int
    salary_cap: int = Field(default=50000, ge=1000)
    slots: Optional[list[Slot]] = None
    lineup_count: int = Field(default=1, ge=1, le=150)
    strategy: str = "balanced_gpp"
    max_exposure: float = Field(default=1.0, gt=0, le=1)
