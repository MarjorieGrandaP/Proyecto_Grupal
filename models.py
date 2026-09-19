from flask_login import UserMixin


class Usuario(UserMixin):
    """
    Modelo de usuario utilizado por Flask-Login.

    UserMixin proporciona los métodos básicos que Flask-Login necesita
    para gestionar la autenticación y la sesión del usuario.
    """

    def __init__(self, id_usuario, usuario, password):
        # Flask-Login utiliza el atributo "id" para identificar
        # de forma única al usuario que mantiene una sesión activa.
        self.id = str(id_usuario)

        # Nombre de usuario que posteriormente puede mostrarse
        # en la interfaz mediante current_user.usuario.
        self.usuario = usuario

        # Aquí se almacena el hash recuperado desde PostgreSQL.
        # No debe contener la contraseña escrita en texto plano.
        self.password = password

    @staticmethod
    def desde_fila(fila):
        """
        Convierte una fila obtenida desde PostgreSQL
        en un objeto Usuario compatible con Flask-Login.
        """

        # Si la consulta no encontró ningún usuario,
        # se devuelve None para indicar que no existe.
        if fila is None:
            return None

        # Se crea el objeto Usuario utilizando los valores
        # recuperados desde la tabla usuarios.
        return Usuario(
            fila["id_usuario"],
            fila["usuario"],
            fila["password"]
        )