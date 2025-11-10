from fastapi import APIRouter

router = APIRouter()

@router.post("/webhook")
def webhook():
    return {"status": "ok", "message": "webhook test"}
