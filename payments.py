from fastapi import APIRouter

router = APIRouter()

@router.post("/webhook")
def webhook():
    return {"status": "ok", "message": "webhook test"}
# payments.py — webhook de Mercado Pago

from fastapi import APIRouter, Request
from db import mark_paid

router = APIRouter()

@router.post("/webhook")
async def webhook(req: Request):
    """
    Mercado Pago te enviará notificaciones acá.
    Modo simple: si llega cualquier notificación con appointment_id
    en el body (o en query), marcamos pagado.
    """
    try:
        data = await req.json()
    except Exception:
        data = {}

    # MP puede mandar la metadata en distintos niveles; buscamos en varios lugares
    appt_id = (
        data.get("data", {}).get("id") or
        data.get("metadata", {}).get("appointment_id") or
        data.get("appointment_id") or
        req.query_params.get("appointment_id")
    )

    if appt_id:
        mark_paid(appt_id)

    # Siempre respondemos 200 para que MP no reintente infinito
    return {"ok": True, "appointment_id": appt_id}
