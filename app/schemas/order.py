from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.order import OrderStatus, PaymentProvider


class OrderCreate(BaseModel):
    contact_id: int
    provider: PaymentProvider
    provider_ref: Optional[str] = None
    amount: float
    currency: str = "USD"
    status: OrderStatus = OrderStatus.pending
    description: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    description: Optional[str] = None


class OrderRead(BaseModel):
    id: int
    contact_id: int
    provider: PaymentProvider
    provider_ref: Optional[str] = None
    amount: float
    currency: str
    status: OrderStatus
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
