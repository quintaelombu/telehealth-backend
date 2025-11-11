# main.py
import os
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

# --- Mercado Pago (opcional; el backend no se cae si no está) ---
try:
    import mercadopago  # debe estar en requirements.txt
except Exception:  # pragma: no cover
    mercadopago = None

# ========= Config =========
BACKEND_URL = os.getenv("BACKEND_URL")  # opcional (para armar notification_url)
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://teleconsulta-emilio.vercel.app")
MP_ACCESS_TOKEN = (
    os.getenv("MP_ACCESS_TOKEN")
    or os.getenv("MERCADOPAGO_ACCESS_TOKEN")
)

# ========= App =========
app = FastAPI(
    title="Teleconsulta Emilio",
    version="1.0.0",
    description="Backend de teleconsultas del Dr. Emilio Galdeano",
)

# CORS: ¡clave para Vercel!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "https://teleconsulta-emilio.vercel.app",
        "https://*.vercel.app",
        "http://localhost",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========= Modelos =========
class ApptIn(BaseModel):
    patient_name: str = Field(..., min_length=1)
    patient_email: EmailStr
    reason: str = Field(..., min_length=1)
    price: int = Field(..., ge=0)        # en ARS
    duration: int = Field(..., ge=5)     # minutos
    start_at: datetime                    # ISO 8601 (el front ya lo envía así)

class ApptOut(BaseModel):
    appointment_id: str
    checkout_url: Optional[str] = None
    join_url: Optional[str] = None
    message: Optional[str] = None

# ========= Utiles =========
def mp_client():
    """
    Devuelve el SDK de Mercado Pago si hay token y está instalado.
    Lanza HTTP 503 si no está listo.
    """
    if not MP_ACCESS_TOKEN or mercadopago is None:
        raise HTTPException(status_code=503, detail="Servicio no configurado")
    try:
        return mercadopago.SDK(MP_ACCESS_TOKEN)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Mercado Pago no disponible: {e}")

def webhook_url() -> Optional[str]:
    # Si tenés BACKEND_URL en Railway, lo usamos; si no, no seteamos notification_url
    if BACKEND_URL:
        return f"{BACKEND_URL.rstrip('/')}/payments/webhook"
    return None
