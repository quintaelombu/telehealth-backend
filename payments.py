import os
try:
    import mercadopago
except Exception:
    mercadopago = None

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()

def create_payment(appointment_id:int, title:str, price:float, currency:str):
    if MP_ACCESS_TOKEN and mercadopago:
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        pref = sdk.preference().create({
            "items":[{"title": title, "quantity":1, "currency_id": currency, "unit_price": float(price)}],
            "external_reference": str(appointment_id),
            "notification_url": f"{BASE_URL}/payments/webhook",
            "auto_return": "approved",
            "back_urls": {
                "success": f"{FRONTEND_URL}/success?appointment_id={appointment_id}",
                "failure": f"{FRONTEND_URL}/failure?appointment_id={appointment_id}",
                "pending": f"{FRONTEND_URL}/pending?appointment_id={appointment_id}"
            }
        })
        return pref["response"]["init_point"], pref["response"]["id"]
    return f"{FRONTEND_URL}/demo-pay?appointment_id={appointment_id}", None
