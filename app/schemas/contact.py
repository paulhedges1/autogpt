from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models.contact import PipelineStage


class ContactCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    stage: PipelineStage = PipelineStage.lead


class ContactUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    stage: Optional[PipelineStage] = None


class ContactRead(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    stage: PipelineStage
    stripe_customer_id: Optional[str] = None
    paypal_payer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
