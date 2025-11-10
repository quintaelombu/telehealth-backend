from fastapi import APIRouter

router = APIRouter()

@router.post("/login")
def login():
    return {"status": "ok", "message": "login test"}
# auth.py — login mínimo

from fastapi import APIRouter, HTTPException
from models import LoginIn

router = APIRouter()

@router.post("/login")
def login(payload: LoginIn):
    # Demo: cualquier usuario + password "123456" entra
    if payload.password != "123456":
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return {"ok": True, "email": payload.email}
