# Crea usuario admin/médico y servicio de Emilio
from db import SessionLocal, Base, engine
from models import User, Service, Role
from auth import hash_password

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    email = "jegaldeano@hotmail.com"
    password = "jegal2364"
    nombre = "Emilio Galdeano"

    u = db.query(User).filter(User.email==email).first()
    if not u:
        u = User(name=nombre, email=email, role=Role.admin, password_hash=hash_password(password))
        db.add(u); db.commit()

    svc = db.query(Service).filter(Service.doctor_id==u.id).first()
    if not svc:
        svc = Service(doctor_id=u.id, title="Teleconsulta pediatría-infectología por video", duration_min=30, price=40000.0, currency="ARS")
        db.add(svc); db.commit()

    print("Listo. Admin/Médico:", email, "| Servicio creado con $40000 por 30 minutos.")

if __name__ == "__main__":
    main()
