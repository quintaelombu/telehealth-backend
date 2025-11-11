from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
import uuid
import os
import mercadopago

# ==================================================
# CONFIGURACIÓN
# ==================================================

app = FastAPI(
    title="Teleconsulta Emilio",
    version="1.0.0",
    openapi_url="/openapi.json"
)

# Variables de entorno
BACKEND_URL = os.getenv("BACKEND_URL", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
mp_client = mercadopago.SDK(MP_ACCESS_TOKEN)

# CORS (permite conexión entre backend y frontend)
allow_origins = ["*"]
if FRONTEND_URL:
    allow_origins = [FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================================================
# MODELOS
# ==================================================

class ApptIn(BaseModel):
    patient_name: str = Field(..., min_length=1)
    patient_email: EmailStr
    reason: str = Field(..., min_length=1)
    price: int = Field(..., ge=100)
    duration: int = Field(..., ge=10, le=180)
    start_at: Optional[str] = None
    when_at: Optional[str] = None  # compatibilidad temporal

class ApptOut(BaseModel):
    id: str
    checkout_url: Optional[str] = None
    join_url: Optional[str] = None
    status: str
    detail: Optional[str] = None

# ==================================================
# RUTAS BÁSICAS
# ==================================================

@app.get("/", tags=["default"])
def root():
    return {"ok": True, "service": "telehealth-backend", "version": "1.0.0"}

@app.get("/ping", tags=["default"])
def ping():
    return {"ok": True}

# ==================================================
# CREAR TURNOS
# ==================================================

@app.post("/appointments", response_model=ApptOut, tags=["appointments"])
def create_appointment(payload: ApptIn):
    """
    Crea la preferencia de pago en Mercado Pago y devuelve el checkout_url.
    """
    # Aceptar start_at o when_at
    start_at_val = payload.start_at or payload.when_at
    if not start_at_val:
        raise HTTPException(status_code=400, detail="start_at is required")

    appt_id = str(uuid.uuid4())

    # Crear preferencia en Mercado Pago
    preference_data = {
        "items": [
            {
                "id": appt_id,
                "title": payload.reason,
                "quantity": 1,
                "unit_price": payload.price,
                "currency_id": "ARS",
            }
        ],
        "metadata": {
            "patient_name": payload.patient_name,
            "patient_email": payload.patient_email,
            "reason": payload.reason,
            "start_at": start_at_val,
            "duration": payload.duration,
        },
        "back_urls": {
            "success": f"{FRONTEND_URL}/success",
            "failure": f"{FRONTEND_URL}/failure",
            "pending": f"{FRONTEND_URL}/pending",
        },
        "auto_return": "approved",
    }

    try:
        pref = mp_client.preference().create(preference_data)
        if pref["status"] != 201:
            raise Exception(str(pref))
        checkout_url = pref["response"]["init_point"]
        return ApptOut(
            id=appt_id,
            checkout_url=checkout_url,
            join_url=None,
            status="created",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================
# WEBHOOK DE MERCADO PAGO
# ==================================================

@app.post("/payments/webhook", tags=["payments"])
def mp_webhook(data: dict):
    print("Webhook recibido:", data)
    return {"ok": True}

# ==================================================
# EJECUCIÓN LOCAL
# ==================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
