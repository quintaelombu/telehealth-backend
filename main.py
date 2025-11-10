from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import appointments, payments, services

app = FastAPI(
    title="Teleconsulta Emilio",
    version="1.0.0",
    description="Backend de teleconsultas médicas con integración de pagos y videollamadas."
)

# CORS — permite que el frontend (Vercel) se conecte sin restricciones
origins = [
    "http://localhost:3000",
    "https://teleconsulta-emilio.vercel.app",
    "https://telehealth-frontend.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers principales
app.include_router(appointments.router)
app.include_router(payments.router)
app.include_router(services.router)

@app.get("/")
def root():
    return {"message": "API Teleconsulta Emilio funcionando correctamente 🚀"}
