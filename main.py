# main.py
import os
import uuid
from datetime import datetime
from typing import Optional, Literal

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

# ────────────────────────────────────────────────────────────────────────────────
# Configuración desde variables de entorno
# ────────────────────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")          # ej: https://telehealth-backend-production-0021.up.railway.app
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")  # ej: https://teleconsulta-emilio.vercel.app
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")

# SDK de Mercado Pago (debe estar en requirements.txt como `mercadopago`)
try:
    import mercadopago  # type: ignore
except Exception as e:
    mercadopago = None

# ────────────────────────────────────────────────────────────────────────────────
# App FastAPI
# ────────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Teleconsulta Emilio",
    version="1.0.0",
    openapi_url="/openapi.json",
)

# CORS (permite frontend en Vercel y localhost)
from fastapi.middleware.cors import CORSMiddleware
import os

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://teleconsulta-emilio.vercel.app")

origins = [
    FRONTEND_URL,
    "https://teleconsulta-emilio.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────────────────────────────────────────────────────
# Modelos
# ────────────────────────────────────────────────────────────────────────────────
class ApptIn(BaseModel):
    patient_name: str = Field(..., min_length=1)
    patient_email: EmailStr
    reason: str = Field(..., min_length=1)
    price: int = Field(..., ge=100)            # en ARS
    duration: int = Field(..., ge=10, le=180)  # minutos
    start_at: str                               # ISO string (el backend la guarda como texto)

class ApptOut(BaseModel):
    id: str
    checkout_url: Optional[str] = None
    join_url: Optional[str] = None
    status: Literal["created","paid","pending","error"] = "created"
    detail: Optional[str] = None

# ────────────────────────────────────────────────────────────────────────────────
# Utilitarios
# ────────────────────────────────────────────────────────────────────────────────
def _mp_client():
    if not mercadopago:
        raise HTTPException(500, "SDK de Mercado Pago no disponible. Ver requirements.txt")
    if not MP_ACCESS_TOKEN:
        raise HTTPException(500, "Falta MP_ACCESS_TOKEN en Railway → Variables.")
    return mercadopago.SDK(MP_ACCESS_TOKEN)

def _notification_url() -> Optional[str]:
    # URL pública del webhook
    return f"{BASE_URL}/payments/webhook" if BASE_URL else None

def _success_url() -> Optional[str]:
    return f"{FRONTEND_URL}/?status=success" if FRONTEND_URL else None

def _failure_url() -> Optional[str]:
    return f"{FRONTEND_URL}/?status=failure" if FRONTEND_URL else None

def _pending_url() -> Optional[str]:
    return f"{FRONTEND_URL}/?status=pending" if FRONTEND_URL else None

def _join_url_from_id(appt_id: str) -> str:
    # Sala de Jitsi simple derivada del id (podés cambiar a Meet/Zoom luego)
    return f"https://meet.jit.si/{appt_id}"

# ────────────────────────────────────────────────────────────────────────────────
# Rutas
# ────────────────────────────────────────────────────────────────────────────────
@app.get("/", tags=["default"])
def root():
    return {"ok": True, "service": "telehealth-backend", "version": "1.0.0"}

@app.get("/ping", tags=["default"])
def ping():
    return {"ok": True}

@app.post("/appointments", response_model=ApptOut, tags=["appointments"])
def create_appointment(payload: ApptIn, request: Request):
    """
    Crea una preferencia de pago en Mercado Pago y devuelve el `checkout_url`.
    También embebe metadatos básicos del turno en `metadata`.
    """
    appt_id = str(uuid.uuid4())

    # Cliente MP
    sdk = _mp_client()

    # Ítem único por la consulta
    item_title = f"Teleconsulta: {payload.patient_name}"
    preference_data = {
        "items": [
            {
                "title": item_title,
                "quantity": 1,
                "unit_price": float(payload.price),
                "currency_id": "ARS",
            }
        ],
        "payer": {"email": payload.patient_email},
        "metadata": {
            "appt_id": appt_id,
            "patient_name": payload.patient_name,
            "patient_email": payload.patient_email,
            "reason": payload.reason,
            "duration": payload.duration,
            "start_at": payload.start_at,
        },
        "auto_return": "approved",
    }

    # back_urls (si tenemos FRONTEND_URL)
    bu = {}
    if _success_url(): bu["success"] = _success_url()
    if _pending_url(): bu["pending"] = _pending_url()
    if _failure_url(): bu["failure"] = _failure_url()
    if bu:
        preference_data["back_urls"] = bu

    # notification_url (si tenemos BASE_URL)
    notif = _notification_url()
    if notif:
        preference_data["notification_url"] = notif

    # Crear preferencia
    pref = sdk.preference().create(preference_data)
    init_point = pref.get("response", {}).get("init_point")

    if not init_point:
        detail = pref.get("response") or "No se obtuvo init_point"
        return ApptOut(id=appt_id, status="error", detail=str(detail))

    return ApptOut(id=appt_id, checkout_url=init_point, status="created")

@app.get("/appointments/{appointment_id}/join", response_model=ApptOut, tags=["appointments"])
def join_appointment(appointment_id: str):
    """
    Devuelve un enlace de videollamada determinístico para el ID dado.
    (Más adelante podés reemplazar por Meet/Zoom/Jitsi administrado).
    """
    return ApptOut(id=appointment_id, join_url=_join_url_from_id(appointment_id), status="paid")

@app.post("/payments/webhook", tags=["payments"])
async def payments_webhook(req: Request):
    """
    Webhook de Mercado Pago. Por ahora: registra y responde 200 OK.
    (Cuando quieras, acá podés verificar el pago y marcar el turno como 'paid').
    """
    try:
        data = await req.json()
    except Exception:
        data = {"raw": await req.body()}
    # Log simple a consola
    print("MP WEBHOOK >>>", data)
    return {"ok": True}
