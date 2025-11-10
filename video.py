from fastapi import APIRouter

router = APIRouter()

@router.post("/")
def create_appointment():
    return {"status": "ok", "message": "appointment created"}

@router.get("/{appointment_id}/join")
def join_appointment(appointment_id: str):
    return {"status": "ok", "join_url": f"https://example.com/{appointment_id}"}
