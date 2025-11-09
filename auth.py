import os, jwt, datetime
from passlib.hash import bcrypt

JWT_SECRET = os.getenv("JWT_SECRET", "cambia_esta_clave_larga")
JWT_EXPIRES_MIN = 4320

def hash_password(p): return bcrypt.hash(p)
def verify_password(p, h): return bcrypt.verify(p, h)

def create_token(user_id:int, role:str):
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXPIRES_MIN)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
