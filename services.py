from fastapi import APIRouter

router = APIRouter(
    prefix="/services",
    tags=["services"]
)

@router.get("/")
def list_services():
    return [
        {"name": "Teleconsulta pediátrica", "price": 40000, "duration": 30, "currency": "ARS"},
        {"name": "Consulta de control", "price": 30000, "duration": 30, "currency": "ARS"},
        {"name": "Asesoramiento por síntomas", "price": 35000, "duration": 20, "currency": "ARS"},
    ]
