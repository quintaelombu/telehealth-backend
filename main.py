import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime
from db import Base, engine, SessionLocal
from models import User, Patient, Service, Appointment, Role, Status
from auth import hash_password, verify_password, create_token
from payments import create_payment
from video import jitsi_room

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Teleconsulta Emilio")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def db_dep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Login simple
class LoginIn(BaseModel):
    email: EmailStr
    password: str

@app.post("/auth/login")
def login(payload: LoginIn):
    db = SessionLocal()
    u = db.query(User).filter(User.email==payload.email).first()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(401, "Credenciales inválidas")
    return {"token": create_token(u.id, u.role.value), "name": u.name}

# Crear turno
class ApptIn(BaseModel):
    patient_name: str
    patient_email: EmailStr
    when_at: datetime

@app.post("/appointments")
def create_appointment(payload: ApptIn):
    db = SessionLocal()
    svc = db.query(Service).first()
    if not svc: raise HTTPException(500, "Servicio no configurado")
    p = db.query(Patient).filter(Patient.email==payload.patient_email).first()
    if not p:
        p = Patient(name=payload.patient_name, email=payload.patient_email)
        db.add(p); db.flush()
    ap = Appointment(doctor_id=svc.doctor_id, patient_id=p.id, service_id=svc.id, when_at=payload.when_at, price=svc.price, currency="ARS")
    db.add(ap); db.flush()
    pay_url, pref_id = create_payment(ap.id, svc.title, ap.price, ap.currency)
    ap.mp_preference_id = pref_id
    db.commit()
    return {"id": ap.id, "pay_url": pay_url}

@app.get("/appointments/{appointment_id}/join")
def join(appointment_id:int):
    db = SessionLocal()
    ap = db.query(Appointment).get(appointment_id)
    if not ap: raise HTTPException(404, "Turno no encontrado")
    if not ap.video_url:
        ap.video_url = jitsi_room(appointment_id)
        db.commit()
    return {"join_url": ap.video_url}

@app.post("/payments/webhook")
async def webhook(req: Request):
    body = await req.json()
    appt_id = body.get("appointment_id") or body.get("external_reference") or (body.get("data",{}) or {}).get("external_reference")
    if appt_id:
        db = SessionLocal()
        ap = db.query(Appointment).get(int(appt_id))
        if ap:
            ap.status = Status.paid
            db.commit()
    return {"ok": True}
