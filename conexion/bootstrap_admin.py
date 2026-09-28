"""Primer administrador opcional, sin cuentas ni contraseñas predeterminadas."""
import os
import re
from email_validator import validate_email, EmailNotValidError
from werkzeug.security import generate_password_hash
from forms.password_policy import PASSWORD_POLICY_PATTERN


def crear_admin_desde_entorno(obtener_conexion, entorno=None):
    env = os.environ if entorno is None else entorno
    username = env.get("ADMIN_USERNAME", "").strip()
    email = env.get("ADMIN_EMAIL", "").strip().lower()
    password = env.get("ADMIN_PASSWORD", "")
    if not any((username, email, password)):
        return False
    if not all((username, email, password)):
        raise RuntimeError("Bootstrap admin: define las tres variables ADMIN_USERNAME, ADMIN_EMAIL y ADMIN_PASSWORD.")
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(174862931)")
            cursor.execute("SELECT 1 FROM usuarios WHERE rol='admin' LIMIT 1")
            if cursor.fetchone():
                return False
            if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,50}", username):
                raise RuntimeError("Bootstrap admin: ADMIN_USERNAME debe contener entre 3 y 50 letras.")
            try:
                validate_email(email, check_deliverability=False)
            except EmailNotValidError:
                raise RuntimeError("Bootstrap admin: ADMIN_EMAIL no tiene un formato válido.") from None
            if len(email) > 120 or len(password) > 100 or not PASSWORD_POLICY_PATTERN.fullmatch(password):
                raise RuntimeError("Bootstrap admin: revisa la longitud del correo y la política de contraseña (8 a 100 caracteres, mayúscula, minúscula, número y @ # * o !).")
            cursor.execute("SELECT 1 FROM usuarios WHERE usuario=%s OR LOWER(correo)=%s", (username, email))
            if cursor.fetchone():
                raise RuntimeError("Bootstrap admin: el usuario o correo ya pertenece a una cuenta. No se modifica ni se eleva su rol.")
            cursor.execute("INSERT INTO usuarios (usuario,correo,password,rol) VALUES (%s,%s,%s,'admin')",
                           (username, email, generate_password_hash(password)))
        conn.commit()
        return True
    finally:
        conn.close()
