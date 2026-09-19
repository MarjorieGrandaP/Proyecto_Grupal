import re

from wtforms.validators import ValidationError

PASSWORD_POLICY_MESSAGE = (
    "La contraseña debe tener al menos 8 caracteres, una mayúscula, "
    "una minúscula, un número y uno de estos símbolos: @ # * !"
)


PASSWORD_POLICY_PATTERN = re.compile(
    r"^(?=[\s\S]{8,}$)(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@#*!])[\s\S]*$"
)


def validar_politica_password(form, field):
    """Aplica la misma política de contraseña en todos los formularios."""
    if not PASSWORD_POLICY_PATTERN.fullmatch(field.data or ""):
        raise ValidationError(PASSWORD_POLICY_MESSAGE)
