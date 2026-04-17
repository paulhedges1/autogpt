from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.contact import PipelineStage


class DealCreate(BaseModel):
    contact_id: int
    title: str
    value: float = 0.0
    stage: PipelineStage = PipelineStage.lead


class DealUpdate(BaseModel):
    title: Optional[str] = None
    value: Optional[float] = None
    stage: Optional[PipelineStage] = None
    closed_at: Optional[datetime] = None


class DealRead(BaseModel):
    id: int
    contact_id: int
    title: str
    value: float
    stage: PipelineStage
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
