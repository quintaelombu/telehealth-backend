import secrets
def jitsi_room(appointment_id:int)->str:
    return f"https://meet.jit.si/EMILIO_{appointment_id}_{secrets.token_hex(4)}"
