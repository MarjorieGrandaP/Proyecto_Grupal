from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    """
    Formulario utilizado para iniciar sesión en PC-Fix.

    Recibe el nombre de usuario y la contraseña ingresados
    por el usuario. Posteriormente, estos datos serán
    comprobados contra la información almacenada en PostgreSQL.
    """

    # Nombre de usuario registrado en la base de datos.
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

    # La contraseña se recibe mediante PasswordField para que
    # el navegador no muestre los caracteres escritos.
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es obligatoria.')
        ]
    )

    # Botón encargado de enviar el formulario mediante POST.
    submit = SubmitField('Iniciar sesión')