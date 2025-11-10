from fastapi import APIRouter

router = APIRouter()

@router.post("/")
def create_appointment():
    return {"status": "ok", "message": "appointment created"}

@router.get("/{appointment_id}/join")
def join_appointment(appointment_id: str):
    return {"status": "ok", "join_url": f"https://example.com/{appointment_id}"}
# video.py — creación de turnos y enlace de videollamada

import os
import uuid
from fastapi import APIRouter, HTTPException
from models import ApptIn, ApptOut
from db import save_appt, get_appt
from datetime import datetime, timezone

# Mercado Pago opcional
_MP_TOKEN = os.getenv("MP_ACCESS_TOKEN")
_MP_INTEGRATION: bool = bool(_MP_TOKEN)
mp = None
if _MP_INTEGRATION:
    import mercadopago
    mp = mercadopago.SDK(_MP_TOKEN)

router = APIRouter()

def _build_join_url(appt_id: str) -> str:
    # Usamos Jitsi como sala gratuita
    return f"https://meet.jit.si/teleconsulta-emilio-{appt_id}"

def _create_mp_preference(appt_id: str, appt: ApptIn) -> str:
    assert mp is not None
    # URL a tu webhook (este endpoint lo exponemos en payments.py)
    webhook_url = os.getenv("WEBHOOK_URL")  # opcional: si no está, Railway la infiere por dominio
    pref = {
        "items": [{
            "title": f"Teleconsulta Dr. Emilio ({appt.duration} min)",
            "quantity": 1,
            "unit_price": float(appt.price),
            "currency_id": "ARS",
        }],
        "metadata": {
            "appointment_id": appt_id,
            "patient_email": appt.patient_email,
        },
    }
    if webhook_url:
        pref["notification_url"] = webhook_url

    pref_res = mp.preference().create(pref)
    if pref_res["status"] not in (200, 201):
        raise HTTPException(status_code=502, detail="Error con Mercado Pago")
    return pref_res["response"]["init_point"]

@router.post("/appointments", response_model=ApptOut)
def create_appointment(appt: ApptIn):
    # Normalizamos fecha (guardada en UTC)
    if appt.start_at.tzinfo is None:
        start_utc = appt.start_at.replace(tzinfo=timezone.utc)
    else:
        start_utc = appt.start_at.astimezone(timezone.utc)

    appt_id = str(uuid.uuid4())
    join_url = _build_join_url(appt_id)

    checkout_url = None
    if _MP_INTEGRATION:
        checkout_url = _create_mp_preference(appt_id, appt)

    record = {
        "id": appt_id,
        "patient_name": appt.patient_name,
        "patient_email": appt.patient_email,
        "reason": appt.reason,
        "price": appt.price,
        "duration": appt.duration,
        "start_at": start_utc.isoformat(),
        "join_url": join_url,
        "paid": False if _MP_INTEGRATION else True,  # si no hay MP, lo damos por pago p/ pruebas
    }
    save_appt(record)

    return {"id": appt_id, "checkout_url": checkout_url, "join_url": None if _MP_INTEGRATION else join_url, "paid": record["paid"]}

@router.get("/appointments/{appointment_id}/join", response_model=ApptOut)
def join(appointment_id: str):
    appt = get_appt(appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if _MP_INTEGRATION and not appt.get("paid"):
        raise HTTPException(status_code=402, detail="Pago pendiente")
    return {
        "id": appt["id"],
        "checkout_url": None,
        "join_url": appt["join_url"],
        "paid": appt["paid"],
    }
