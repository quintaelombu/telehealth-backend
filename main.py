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

# ========= Rutas =========
@app.get("/", tags=["default"])
def root():
    return {"ok": True, "service": "telehealth-backend", "version": "1.0.0"}

@app.get("/ping", tags=["default"])
def ping():
    return {"ok": True}

@app.post("/appointments", response_model=ApptOut, tags=["appointments"])
def create_appointment(payload: ApptIn):
    """
    Crea la preferencia de pago en MP y devuelve el checkout_url.
    Guarda metadata mínima en la preferencia (no usamos DB aquí para simplificar).
    """
    # ID simple (podés migrar a DB luego)
    appt_id = str(uuid.uuid4())

    # Cliente MP (valida token instalado)
    sdk = mp_client()

    # Armar preferencia
    title = f"Teleconsulta pediatría — {payload.patient_name}"
    notification = webhook_url()

    preference_body = {
        "items": [
            {
                "title": title,
                "quantity": 1,
                "unit_price": float(payload.price),
                "currency_id": "ARS",
            }
        ],
        "metadata": {
            "appointment_id": appt_id,
            "patient_email": str(payload.patient_email),
            "reason": payload.reason,
            "duration": payload.duration,
            "start_at": payload.start_at.isoformat(),
        },
        "back_urls": {
            "success": f"{FRONTEND_URL}",
            "pending": f"{FRONTEND_URL}",
            "failure": f"{FRONTEND_URL}",
        },
        "auto_return": "approved",
    }

    # Notificación (webhook) si tenemos URL conocida
    if notification:
        preference_body["notification_url"] = notification

    try:
        pref = sdk.preference().create(preference_body)
        # MP responde con {'response': {...}, 'status': 201, ...}
        data = pref.get("response") or {}
        checkout = data.get("init_point") or data.get("sandbox_init_point")
        if not checkout:
            raise RuntimeError("MP no devolvió init_point")

        return ApptOut(
            appointment_id=appt_id,
            checkout_url=checkout,
            message="Preferencia creada",
        )
    except HTTPException:
        raise
    except Exception as e:
        # Si MP falla, devolvemos 502 para que el front muestre mensaje claro
        raise HTTPException(status_code=502, detail=f"Error al crear pago: {e}")

@app.get("/appointments/{appointment_id}/join", response_model=ApptOut, tags=["appointments"])
def join_appointment(appointment_id: str):
    """
    Endpoint de ejemplo: en un escenario real, leerías la DB para obtener join_url.
    Por ahora devolvemos 404 si no lo tenemos.
    """
    raise HTTPException(status_code=404, detail="Aún no hay enlace de videollamada")

@app.post("/payments/webhook", tags=["payments"])
async def payments_webhook(request: Request):
    """
    Recibe notificaciones de MP. Registra el evento y responde 200 siempre.
    (MP reintenta si no respondés 200.)
    """
    try:
        body_bytes = await request.body()
        raw = body_bytes.decode("utf-8") if body_bytes else ""
        headers = dict(request.headers)
        # Podés loguear a stdout (visible en Railway Logs) o a una tabla
        print("[WEBHOOK] headers=", json.dumps(headers))
        print("[WEBHOOK] body=", raw)

        # Si querés validar el payment_id y actualizar estado:
        if MP_ACCESS_TOKEN and mercadopago is not None:
            try:
                payload = json.loads(raw) if raw else {}
                topic = payload.get("type") or payload.get("action") or ""
                if topic in ("payment", "payment.updated", "payment.created"):
                    data = payload.get("data") or {}
                    payment_id = data.get("id") or data.get("payment_id")
                    if payment_id:
                        sdk = mp_client()
                        _res = sdk.payment().get(payment_id)
                        print("[WEBHOOK] payment.get ->", json.dumps(_res.get("response", {})))
            except Exception as e:
                print("[WEBHOOK] parse/validation error:", e)

        return {"ok": True}
    except Exception as e:
        # Respondemos 200 igual para que MP no reintente infinito, pero dejamos constancia
        print("[WEBHOOK] fatal:", e)
        return {"ok": False, "error": str(e)}

# ========= Uvicorn local =========
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
