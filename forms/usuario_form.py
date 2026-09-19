from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
import re

from wtforms.validators import DataRequired, Length, EqualTo, ValidationError

from .password_policy import validar_politica_password, PASSWORD_POLICY_MESSAGE


def validar_correo(form, field):
    """Valida el formato del correo antes de guardar un usuario nuevo."""
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", field.data.strip()):
        raise ValidationError("Ingresa un correo electrónico válido.")


class UsuarioForm(FlaskForm):
    """
    Formulario utilizado para registrar nuevos usuarios.

    Antes de almacenar la contraseña en PostgreSQL,
    app.py la transformará mediante generate_password_hash(),
    evitando guardarla en texto plano.
    """

    nombres = StringField(
        "Nombres",
        validators=[
            DataRequired(message="Los nombres son obligatorios."),
            Length(max=100, message="Los nombres no pueden superar 100 caracteres."),
        ],
    )

    apellidos = StringField(
        "Apellidos",
        validators=[
            DataRequired(message="Los apellidos son obligatorios."),
            Length(max=100, message="Los apellidos no pueden superar 100 caracteres."),
        ],
    )

    # Nombre que identificará al usuario dentro del sistema.
    # La base de datos también tendrá una restricción UNIQUE
    # para impedir que dos usuarios tengan el mismo nombre.
    usuario = StringField(
        "Usuario",
        validators=[
            DataRequired(message="El nombre de usuario es obligatorio."),
            Length(
                min=3, max=50, message="El usuario debe tener entre 3 y 50 caracteres."
            ),
        ],
    )

    correo = StringField(
        "Correo electrónico",
        validators=[
            DataRequired(message="El correo electrónico es obligatorio."),
            Length(max=120, message="El correo no puede superar 120 caracteres."),
            validar_correo,
        ],
    )

    telefono = StringField(
        "Teléfono",
        validators=[
            DataRequired(message="El teléfono es obligatorio."),
            Length(max=30, message="El teléfono no puede superar 30 caracteres."),
        ],
    )

    # Contraseña original ingresada por el usuario.
    # Esta contraseña nunca se almacenará directamente
    # en la base de datos.
    password = PasswordField(
        "Contraseña",
        validators=[
            DataRequired(message="La contraseña es obligatoria."),
            Length(
                min=8,
                max=100,
                message=PASSWORD_POLICY_MESSAGE,
            ),
            validar_politica_password,
        ],
    )

    # Se solicita nuevamente la contraseña para comprobar
    # que el usuario no haya cometido un error al escribirla.
    confirmar_password = PasswordField(
        "Confirmar contraseña",
        validators=[
            DataRequired(message="Debe confirmar la contraseña."),
            EqualTo("password", message="Las contraseñas no coinciden."),
        ],
    )

    # Botón para enviar el formulario de registro.
    submit = SubmitField("Registrar usuario")
