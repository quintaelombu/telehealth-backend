from sqlalchemy import Column, Integer, String, DateTime, Float, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from db import Base

class Role(str, enum.Enum):
    admin = "admin"
    doctor = "doctor"

class Channel(str, enum.Enum):
    video = "video"

class Status(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    done = "done"
    no_show = "no_show"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    phone = Column(String, nullable=True)
    role = Column(Enum(Role), default=Role.doctor, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    consent_at = Column(DateTime, nullable=True)

class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    duration_min = Column(Integer, default=30)
    price = Column(Float, default=0.0)
    currency = Column(String, default="ARS")

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    when_at = Column(DateTime, nullable=False)
    status = Column(Enum(Status), default=Status.pending, nullable=False)
    price = Column(Float, default=0.0)
    currency = Column(String, default="ARS")
    mp_preference_id = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", lazy="joined")
    service = relationship("Service", lazy="joined")
# models.py — esquemas Pydantic

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ApptIn(BaseModel):
    patient_name: str = Field(min_length=1)
    patient_email: EmailStr
    reason: str = Field(min_length=1)
    price: int = Field(ge=0)
    duration: int = Field(ge=5)          # minutos
    start_at: datetime                   # ISO-8601

class ApptOut(BaseModel):
    id: str
    checkout_url: str | None = None
    join_url: str | None = None
    paid: bool = False
