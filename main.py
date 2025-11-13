import os
import uuid
from typing import Optional
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

if not DATABASE_URL:
    raise RuntimeError("No existe DATABASE_URL en las variables de entorno de Railway.")

engine = create_engine(DATABASE_URL)from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

if not DATABASE_URL:
    print("ATENCIÓN: DATABASE_URL no está configurada. No se guardarán turnos en DB.")
    engine = None
else:
    try:
        engine = create_engine(DATABASE_URL)
    except Exception as e:
        print("ERROR al inicializar conexión a DB:", e)
        engine = Noneelse:
    print("ATENCIÓN: DATABASE_URL no está configurada. No se guardarán turnos en DB.")

# ─────────────────────────────────────────────────────────
# Variables de entorno
# ─────────────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")          # ej: https://telehealth-backend-production-0021.up.railway.app
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")  # ej: https://teleconsulta-emilio.vercel.app
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")

# SDK de Mercado Pago
try:
    import mercadopago  # type: ignore
except Exception:
    mercadopago = None


def get_mp_client():
    """
    Crea el cliente de Mercado Pago con el token de entorno.
    Lanza error claro si falta el token o el SDK.
    """
    if mercadopago is None:
        raise RuntimeError("SDK de Mercado Pago no está instalado (mercadopago).")

    if not MP_ACCESS_TOKEN:
        raise RuntimeError("MP_ACCESS_TOKEN no está configurado en las variables de entorno.")

    return mercadopago.SDK(MP_ACCESS_TOKEN)


def get_webhook_url() -> Optional[str]:
    """URL de webhook a partir de BASE_URL si está configurada."""
    if BASE_URL:
        return f"{BASE_URL.rstrip('/')}/payments/webhook"
    return None


# ─────────────────────────────────────────────────────────
# App FastAPI
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Teleconsulta Emilio",
    version="1.1.0",
    openapi_url="/openapi.json",
)


# ─────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────
origins = []

if FRONTEND_URL:
    origins.append(FRONTEND_URL)

# Dominios que estás usando en Vercel + local
origins.extend(
    [
        "https://teleconsulta-emilio.vercel.app",
        "https://teleconsulta-emilio-p3q6epu24-dr-emilios-projects.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)

# Eliminar duplicados
origins = list(set(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # IMPORTANTE: sin "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────
# Modelos
# ─────────────────────────────────────────────────────────
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApptIn(BaseModel):
    patient_name: str = Field(..., min_length=1)
    patient_email: EmailStr
    reason: str = Field(..., min_length=1)
    price: int = Field(..., ge=100)  # ARS
    duration: int = Field(..., ge=10, le=180)  # minutos
    start_at: str  # ISO string, ej: "2025-11-11T11:11:00.000Z"


class ApptOut(BaseModel):
    id: str
    checkout_url: Optional[str] = None
    join_url: Optional[str] = None
    status: str
    detail: Optional[str] = None


# ─────────────────────────────────────────────────────────
# Rutas básicas
# ─────────────────────────────────────────────────────────
@app.get("/", tags=["default"])
def root():
    return {"ok": True, "service": "telehealth-backend", "version": "1.1.0"}


@app.get("/ping", tags=["default"])
def ping():
    return {"ok": True}


# ─────────────────────────────────────────────────────────
# Auth muy simple (solo para tener /auth/login en Swagger)
# ─────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=LoginOut, tags=["auth"])
def login(payload: LoginIn):
    """
    Login de demostración. No valida contra base de datos.
    Devuelve siempre un token fijo para que puedas entrar al panel médico.
    """
    fake_token = "demo-token"
    return LoginOut(access_token=fake_token)


# ─────────────────────────────────────────────────────────
# Crear turno y preferencia de pago en Mercado Pago + guardar en DB
# ─────────────────────────────────────────────────────────
@app.post("/appointments", response_model=ApptOut, tags=["appointments"])
def create_appointment(payload: ApptIn):
    """
    Crea una preferencia de pago en Mercado Pago y devuelve el checkout_url.
    También guarda el turno en la tabla appointments si hay DB configurada.
    """
    # ID para el turno
    appt_id = str(uuid.uuid4())

    # Cliente MP
    try:
        sdk = get_mp_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Datos de preferencia
    preference = {
        "items": [
            {
                "title": payload.reason or "Consulta pediátrica",
                "quantity": 1,
                "unit_price": float(payload.price),  # ARS
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

    webhook_url = get_webhook_url()
    if webhook_url:
        preference["notification_url"] = webhook_url

    # Crear preferencia en MP
    try:
        result = sdk.preference().create(preference)
        mp_resp = result.get("response", {})
        checkout_url = mp_resp.get("init_point") or mp_resp.get("sandbox_init_point")
        if not checkout_url:
            raise HTTPException(
                status_code=500,
                detail="No se pudo obtener checkout_url desde Mercado Pago.",
            )
        mp_preference_id = mp_resp.get("id")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear preferencia en Mercado Pago: {str(e)}",
        )

    # ─────────────────────────────────────────────────────
    # Guardar en DB si hay conexión y tabla definida
    # ─────────────────────────────────────────────────────
    if engine is not None and appointments is not None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    appointments.insert().values(
                        id=appt_id,
                        patient_name=payload.patient_name,
                        patient_email=payload.patient_email,
                        reason=payload.reason,
                        price=payload.price,
                        duration=payload.duration,
                        status="created",
                        start_at=payload.start_at,
                        mp_preference_id=mp_preference_id,
                    )
                )
        except Exception as db_err:
            # No rompemos el flujo de pago si falla la DB; solo registramos.
            print("ERROR al guardar turno en DB:", db_err)

    return ApptOut(
        id=appt_id,
        checkout_url=checkout_url,
        join_url=None,
        status="created",
        detail=None,
    )


# ─────────────────────────────────────────────────────────
# Webhook de Mercado Pago
# ─────────────────────────────────────────────────────────
@app.post("/payments/webhook", tags=["payments"])
async def payments_webhook(request: Request):
    """
    Webhook de Mercado Pago.
    Por ahora solo registra el evento y responde 200 OK.
    """
    body = await request.json()
    print("Webhook Mercado Pago:", body)
    return {"ok": True}
