from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from payments import router as payments_router
from video import router as video_router

app = FastAPI(
    title="Teleconsulta Emilio",
    version="1.0.0",
    description="Backend de teleconsultas del Dr. Emilio Galdeano",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
app.include_router(video_router, prefix="/appointments", tags=["appointments"])


@app.get("/")
def root():
    return {"message": "API online — Teleconsulta Emilio"}


# --- Bloque de ejecución local / Railway ---
if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
# main.py — aplicación FastAPI principal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from video import router as video_router
from payments import router as payments_router

app = FastAPI(title="Teleconsulta Emilio", version="1.0.0")

# CORS para permitir al frontend en Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # puedes restringir a tu dominio de Vercel si quieres
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "API online — Teleconsulta Emilio"}

# Montamos routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(video_router, tags=["appointments"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
