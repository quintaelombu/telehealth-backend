import os
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Table, Column, MetaData, String, Integer, Text, insert

# =====================================================================
# BASE DE DATOS (POSTGRES)
# =====================================================================

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("DATABASE_PUBLIC_URL")
)

engine = None
appointments = None

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
        metadata = MetaData()

        appointments = Table(
            "appointments",
            metadata,
            Column("id", String, primary_key=True),
            Column("patient_name", String, nullable=False),
            Column("patient_email", String, nullable=False),
            Column("reason", Text, nullable=False),
            Column("price", Integer, nullable=False),
            Column("duration", Integer, nullable=False),
            Column("start_at", Text, nullable=False),
            Column("status", String, nullable=False),
            Column("mp_preference_id", String, nullable=True),
        )

        # NO crear create_all() porque Railway ya creó la tabla
        print("DB inicializada correctamente.")

    except Exception as e:
        print("ERROR al inicializar DB:", e)
        engine = None
        appointments = None
else:
    print("ATENCIÓN: No se encontró DATABASE_URL en Railway. No se guardarán turnos.")


# =====================================================================
# VARIABLES DE ENTORNO
# =====================================================================

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")


# =====================================================================
# MERCADO PAGO
# =====================================================================

try:
    import mercadopago  # type: ignore
except Exception:
    mercadopago = None


def get_mp_client():
    if mercadopago is None:
        raise RuntimeError("SDK de Mercado Pago no está instalado.")

    if not MP_ACCESS_TOKEN:
        raise RuntimeError("MP_ACCESS_TOKEN no está configurado en Railway.")

    return mercadopago.SDK(MP_ACCESS_TOKEN)


def get_webhook_url():
    if BASE_URL:
        return f"{BASE_URL}/payments/webhook"
    return None


# =====================================================================
# FASTAPI APP
# =====================================================================

app = FastAPI(
    title="Teleconsulta Emilio",
    version="1.0.0",
    openapi_url="/openapi.json",
)


# =====================================================================
# CORS
# =====================================================================

origins = list(
    set(
        [
            FRONTEND_URL,
            "https://teleconsulta-emilio.vercel.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# MODELOS
# =====================================================================

class ApptIn(BaseModel):
    patient_name: str = Field(..., min_length=1)
    patient_email: EmailStr
    reason: str = Field(..., min_length=1)
    price: int = Field(..., ge=100)
    duration: int = Field(..., ge=10, le=180)
    start_at: str  # ISO datetime string


class ApptOut(BaseModel):
    id: str
    checkout_url: Optional[str]
    join_url: Optional[str]
    status: str
    detail: Optional[str]


# =====================================================================
# RUTAS
# =====================================================================

@app.get("/")
def root():
    return {"ok": True, "service": "telehealth-backend"}


@app.post("/appointments", response_model=ApptOut)
def create_appointment(payload: ApptIn):

    # Crear ID local del turno
    appt_id = str(uuid.uuid4())

    # Cliente MP
    try:
        sdk = get_mp_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Crear preferencia
    preference_data = {
        "items": [
            {
                "title": payload.reason,
                "quantity": 1,
                "unit_price": float(payload.price),
            }
        ],
        "payer": {
            "name": payload.patient_name,
            "email": payload.patient_email,
        },
        "metadata": {
            "appointment_id": appt_id,
            "patient_name": payload.patient_name,
            "patient_email": payload.patient_email,
            "reason": payload.reason,
            "price": payload.price,
            "duration": payload.duration,
            "start_at": payload.start_at,
        },
    }

    wh = get_webhook_url()
    if wh:
        preference_data["notification_url"] = wh

    try:
        result = sdk.preference().create(preference_data)
        resp = result.get("response", {})
        checkout_url = resp.get("init_point") or resp.get("sandbox_init_point")
        mp_pref_id = resp.get("id")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error MP: {str(e)}")

    # Guardar turno en DB
    if engine and appointments:
        try:
            stmt = insert(appointments).values(
                id=appt_id,
                patient_name=payload.patient_name,
                patient_email=payload.patient_email,
                reason=payload.reason,
                price=payload.price,
                duration=payload.duration,
                start_at=payload.start_at,
                status="created",
                mp_preference_id=mp_pref_id,
            )
            with engine.connect() as conn:
                conn.execute(stmt)
                conn.commit()
        except Exception as e:
            print("Error guardando en DB:", e)

    return ApptOut(
        id=appt_id,
        checkout_url=checkout_url,
        join_url=None,
        status="created",
        detail=None,
    )


@app.post("/payments/webhook")
async def payments_webhook(request: Request):
    data = await request.json()
    print("Webhook recibido:", data)
    return {"ok": True}
