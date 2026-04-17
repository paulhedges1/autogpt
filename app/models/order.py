import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class OrderStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    refunded = "refunded"
    disputed = "disputed"


class PaymentProvider(str, enum.Enum):
    stripe = "stripe"
    paypal = "paypal"
    manual = "manual"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    provider = Column(Enum(PaymentProvider), nullable=False)
    provider_ref = Column(String, unique=True, nullable=True, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contact = relationship("Contact", back_populates="orders")
