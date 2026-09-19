from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo


class UsuarioForm(FlaskForm):
    """
    Formulario utilizado para registrar nuevos usuarios.

    Antes de almacenar la contraseña en PostgreSQL,
    app.py la transformará mediante generate_password_hash(),
    evitando guardarla en texto plano.
    """

    # Nombre que identificará al usuario dentro del sistema.
    # La base de datos también tendrá una restricción UNIQUE
    # para impedir que dos usuarios tengan el mismo nombre.
    usuario = StringField(
        'Usuario',
        validators=[
            DataRequired(message='El nombre de usuario es obligatorio.'),
            Length(
                min=3,
                max=50,
                message='El usuario debe tener entre 3 y 50 caracteres.'
            )
        ]
    )

    # Contraseña original ingresada por el usuario.
    # Esta contraseña nunca se almacenará directamente
    # en la base de datos.
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es obligatoria.'),
            Length(
                min=6,
                max=100,
                message='La contraseña debe tener al menos 6 caracteres.'
            )
        ]
    )

    # Se solicita nuevamente la contraseña para comprobar
    # que el usuario no haya cometido un error al escribirla.
    confirmar_password = PasswordField(
        'Confirmar contraseña',
        validators=[
            DataRequired(message='Debe confirmar la contraseña.'),
            EqualTo(
                'password',
                message='Las contraseñas no coinciden.'
            )
        ]
    )

    # Botón para enviar el formulario de registro.
    submit = SubmitField('Registrar usuario')