from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import auth, payments, video, models, db, services  # Importamos los módulos

app = FastAPI(
    title="Teleconsulta Emilio",
    description="Backend de teleconsultas médicas con integración de pagos y videollamadas",
    version="1.1.0"
)

# CORS para permitir conexión con el frontend en Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # luego se puede restringir al dominio final
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas principales
app.include_router(auth.router, prefix="/auth")
app.include_router(payments.router, prefix="/payments")
app.include_router(video.router, prefix="/appointments")
app.include_router(services.router, prefix="/services")  # nuevo router agregado

@app.get("/")
def root():
    return {"status": "ok", "message": "Backend Teleconsulta Emilio activo"}
