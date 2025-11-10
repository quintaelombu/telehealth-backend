import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
# db.py — almacenamiento simple en memoria

from typing import Dict, Any
from threading import RLock

_APPTS: Dict[str, Dict[str, Any]] = {}
_LOCK = RLock()

def save_appt(appt: Dict[str, Any]) -> None:
    with _LOCK:
        _APPTS[appt["id"]] = appt

def get_appt(appt_id: str) -> Dict[str, Any] | None:
    with _LOCK:
        return _APPTS.get(appt_id)

def mark_paid(appt_id: str) -> None:
    with _LOCK:
        if appt_id in _APPTS:
            _APPTS[appt_id]["paid"] = True
