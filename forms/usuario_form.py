from .nombre_personal import campo_nombre_personal
from wtforms.validators import Regexp
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

    nombres = campo_nombre_personal("Nombres")

    apellidos = campo_nombre_personal("Apellidos")

    # Nombre que identificará al usuario dentro del sistema.
    # La base de datos también tendrá una restricción UNIQUE
    # para impedir que dos usuarios tengan el mismo nombre.
    usuario = StringField(
        "Usuario",
        render_kw={"pattern": "[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,50}", "title": "El usuario debe contener únicamente letras y tener entre 3 y 50 caracteres."},
        validators=[
            Regexp(r"\A[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,50}\Z", message="El usuario debe contener únicamente letras y tener entre 3 y 50 caracteres."),
            DataRequired(message="El usuario debe contener únicamente letras y tener entre 3 y 50 caracteres."),
            Length(
                min=3, max=50, message="El usuario debe contener únicamente letras y tener entre 3 y 50 caracteres."
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
        render_kw={"inputmode": "numeric", "pattern": "[0-9]+"},
        validators=[
            DataRequired(message="El teléfono es obligatorio."),
            Regexp(r"\A[0-9]+\Z", message="El teléfono debe contener solo dígitos."),
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
