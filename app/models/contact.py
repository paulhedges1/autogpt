import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class PipelineStage(str, enum.Enum):
    lead = "lead"
    prospect = "prospect"
    customer = "customer"
    churned = "churned"


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    company = Column(String, nullable=True)
    stage = Column(Enum(PipelineStage), default=PipelineStage.lead, nullable=False)
    stripe_customer_id = Column(String, unique=True, nullable=True, index=True)
    paypal_payer_id = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="contact", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="contact", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="contact", cascade="all, delete-orphan")
