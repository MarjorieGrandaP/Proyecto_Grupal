from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed


class ImagenServicioForm(FlaskForm):
    archivo = FileField("Imagen", validators=[
        FileRequired(message="Selecciona una imagen."),
        FileAllowed(["jpg", "jpeg", "png", "webp"], "Solo se permiten JPG, JPEG, PNG o WEBP."),
    ])
