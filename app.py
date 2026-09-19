from functools import wraps

from flask import (
    Flask,
    abort,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
)

# Formularios utilizados por los módulos del sistema.
# LoginForm y UsuarioForm se incorporan para la autenticación.
from forms import (
    ProductoForm,
    ClienteForm,
    ProveedorForm,
    FacturacionForm,
    LoginForm,
    UsuarioForm,
    PerfilForm,
    CambioPasswordForm,
    PedidoForm,
    PedidoEstadoForm,
    EmitirFacturaForm,
    PedidoAccionForm,
)

# Funciones utilizadas para conectar Flask con PostgreSQL.
from conexion.conexion import obtener_conexion, inicializar_base_datos
from psycopg2.extras import RealDictCursor

# Herramientas de Flask-Login para gestionar sesiones de usuario.
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)

# Werkzeug permite generar y comprobar el hash de las contraseñas.
# La contraseña original nunca se almacenará en PostgreSQL.
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Modelo de usuario compatible con Flask-Login.
from models import Usuario

import os
import uuid
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen import canvas
from datetime import datetime

# ==========================================================
# CONFIGURACIÓN SEGURA DE LA APLICACIÓN
# ==========================================================

# Carga las variables privadas almacenadas localmente
# en el archivo .env.
load_dotenv()

app = Flask(__name__)

# SECRET_KEY es utilizada por Flask para proteger
# sesiones, mensajes flash y formularios CSRF.
#
# La clave se obtiene desde .env para evitar publicarla
# dentro del código fuente o subirla a GitHub.
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["RECAPTCHA_PUBLIC_KEY"] = os.getenv("RECAPTCHA_PUBLIC_KEY")
app.config["RECAPTCHA_PRIVATE_KEY"] = os.getenv("RECAPTCHA_PRIVATE_KEY")

# Si la clave no está configurada, la aplicación se detiene
# para evitar ejecutarse con una configuración insegura.
if not app.config["SECRET_KEY"]:
    raise RuntimeError("No se encontró SECRET_KEY. " "Configúrala en el archivo .env.")
# ==========================================================
# CONFIGURACIÓN DE FLASK-LOGIN
# ==========================================================

# LoginManager administra la sesión de los usuarios autenticados.
login_manager = LoginManager()

# Se vincula Flask-Login con la aplicación Flask actual.
login_manager.init_app(app)

# Si un usuario intenta entrar a una ruta protegida sin haber
# iniciado sesión, Flask-Login lo enviará automáticamente a /login.
login_manager.login_view = "login"

# Mensaje que se mostrará cuando se intente acceder
# a una página privada sin autenticación.
login_manager.login_message = "Debes iniciar sesión para acceder a esta página."

# Bootstrap utilizará esta categoría para mostrar
# el mensaje como una alerta.
login_manager.login_message_category = "warning"

NOMBRE_EMPRESA = "PC-Fix"
TIPOS_ASISTENCIA = [
    "Mantenimiento Preventivo",
    "Mantenimiento Correctivo",
    "Instalación de Software",
]

EXTENSIONES_PERFIL_PERMITIDAS = {"jpg", "jpeg", "png", "webp"}
PERFILES_UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "perfiles",
)
os.makedirs(PERFILES_UPLOAD_FOLDER, exist_ok=True)


def imagen_perfil_url(nombre_imagen):
    """Devuelve la ruta pública de una imagen de perfil si existe."""
    return nombre_imagen


def normalizar_correo(correo):
    """Normaliza correos para guardar, buscar y comprobar duplicados."""
    return correo.strip().lower() if correo else None


def verificar_recaptcha(token, remote_ip=None):
    """Verifica el token v2 con Google antes de iniciar el registro."""
    if not token:
        return False, "Confirma que no eres un robot."

    secret = app.config.get("RECAPTCHA_PRIVATE_KEY")
    if not secret:
        return False, "No fue posible validar reCAPTCHA. Inténtalo nuevamente."

    datos = {"secret": secret, "response": token}
    if remote_ip:
        datos["remoteip"] = remote_ip

    solicitud = Request(
        "https://www.google.com/recaptcha/api/siteverify",
        data=urlencode(datos).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urlopen(solicitud, timeout=10) as respuesta:
            resultado = json.loads(respuesta.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return False, "No fue posible validar reCAPTCHA. Inténtalo nuevamente."

    if resultado.get("success") is True:
        return True, None
    return False, "No fue posible validar reCAPTCHA. Inténtalo nuevamente."


def guardar_imagen_perfil(archivo):
    """Valida y guarda una imagen de perfil, devolviendo solo su nombre seguro."""
    if not archivo or not archivo.filename:
        return None

    nombre_seguro = secure_filename(archivo.filename)
    extension = nombre_seguro.rsplit(".", 1)[-1].lower() if "." in nombre_seguro else ""

    if not nombre_seguro or extension not in EXTENSIONES_PERFIL_PERMITIDAS:
        raise ValueError("Solo se permiten imágenes JPG, JPEG, PNG o WEBP.")

    nombre_final = f"perfil_{current_user.id}_{uuid.uuid4().hex}.{extension}"
    archivo.save(os.path.join(PERFILES_UPLOAD_FOLDER, nombre_final))
    return nombre_final


# Inicializar PostgreSQL y cargar sql/esquema.sql
try:
    inicializar_base_datos()
except Exception as err:
    print(f"[AVISO INICIO] Error al inicializar base de datos: {err}")

# ===== Datos de referencia en memoria para módulos complementarios =====
CLIENTES = [
    {
        "nombre": "Ana Torres",
        "telefono": "0991234567",
        "equipo": "Laptop HP Pavilion",
        "estado": "En revisión",
    },
    {
        "nombre": "Luis Mendoza",
        "telefono": "0987654321",
        "equipo": "PC de escritorio",
        "estado": "Entregado",
    },
    {
        "nombre": "Karen Salazar",
        "telefono": "0971122334",
        "equipo": "MacBook Air",
        "estado": "En reparación",
    },
    {
        "nombre": "Diego Núñez",
        "telefono": "0965544332",
        "equipo": "Laptop Lenovo IdeaPad",
        "estado": "Pendiente",
    },
]

PROVEEDORES = [
    {
        "empresa": "TecnoRepuestos S.A.",
        "contacto": "Ing. Marco Ruiz",
        "telefono": "022456789",
        "categoria": "Placas y componentes",
    },
    {
        "empresa": "Almacenes Comercial",
        "contacto": "Sra. Rosa Vega",
        "telefono": "022998877",
        "categoria": "Pantallas y baterías",
    },
    {
        "empresa": "PC Parts Ecuador",
        "contacto": "Sr. Pablo Andrade",
        "telefono": "0987001122",
        "categoria": "Memorias RAM y SSD",
    },
]

FACTURAS = [
    {
        "numero": "FAC-001",
        "cliente": "Ana Torres",
        "servicio": "Mantenimiento Preventivo",
        "fecha": "2026-08-10",
        "total": 25.00,
        "estado": "Pagada",
    },
    {
        "numero": "FAC-002",
        "cliente": "Luis Mendoza",
        "servicio": "Instalación de Software",
        "fecha": "2026-08-11",
        "total": 15.00,
        "estado": "Pagada",
    },
    {
        "numero": "FAC-003",
        "cliente": "Karen Salazar",
        "servicio": "Mantenimiento Correctivo",
        "fecha": "2026-08-14",
        "total": 40.00,
        "estado": "Pendiente",
    },
    {
        "numero": "FAC-004",
        "cliente": "Diego Núñez",
        "servicio": "Formateo e Instalación de Windows",
        "fecha": "2026-08-15",
        "total": 30.00,
        "estado": "Pendiente",
    },
]


def obtener_opciones_proveedores():
    """Recupera la lista de proveedores desde PostgreSQL para poblar el selector del formulario."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id_proveedor, empresa FROM proveedores ORDER BY empresa ASC"
        )
        proveedores = cursor.fetchall()
        cursor.close()
        conn.close()
        opciones = [(0, "-- Sin proveedor asignado --")]
        for p in proveedores:
            opciones.append((p["id_proveedor"], p["empresa"]))
        return opciones
    except Exception as e:
        print(f"[ERROR PROVEEDORES] Error al obtener proveedores: {e}")
        return [(0, "-- Sin proveedor asignado --")]


def obtener_imagenes_servicios():
    """
    Obtiene automáticamente las imágenes disponibles
    dentro de static/img.

    Solo se incluyen archivos cuyo nombre empiece por
    'servicio-' para evitar mostrar imágenes como favicon,
    fotografías del equipo, encabezados u otros recursos.
    """

    carpeta_imagenes = os.path.join(
        app.root_path,
        "static",
        "img",
    )

    extensiones_permitidas = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    )

    opciones = []

    # Verifica que la carpeta exista antes de leerla.
    if not os.path.exists(carpeta_imagenes):
        return opciones

    for archivo in os.listdir(carpeta_imagenes):

        # Solo se aceptan imágenes destinadas a servicios.
        if archivo.lower().startswith("servicio-") and archivo.lower().endswith(
            extensiones_permitidas
        ):
            opciones.append((archivo, archivo))

    # Ordenar alfabéticamente los archivos.
    return sorted(opciones)


# ==========================================================
# RECUPERACIÓN DEL USUARIO AUTENTICADO
# ==========================================================


@login_manager.user_loader
def load_user(user_id):
    """
    Recupera desde PostgreSQL al usuario que mantiene
    una sesión activa.

    Flask-Login guarda únicamente el identificador del usuario
    en la sesión. Cada vez que necesita conocer al usuario actual,
    esta función utiliza ese ID para consultar la tabla usuarios.
    """

    conn = obtener_conexion()

    # RealDictCursor permite acceder a los datos por el nombre
    # de las columnas, por ejemplo: fila["usuario"].
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Consulta parametrizada para recuperar únicamente
    # el usuario correspondiente al ID almacenado en la sesión.
    cursor.execute(
        """
         SELECT u.id_usuario, u.usuario, u.correo, u.password, u.rol,
             p.imagen
         FROM usuarios u
         LEFT JOIN perfiles_usuario p ON p.id_usuario = u.id_usuario
         WHERE u.id_usuario = %s
        """,
        (user_id,),
    )

    fila = cursor.fetchone()

    cursor.close()
    conn.close()

    # desde_fila() convierte el registro de PostgreSQL
    # en el objeto Usuario definido en models.py.
    return Usuario.desde_fila(fila)


# ==========================================================
# SISTEMA DE AUTENTICACIÓN
# ==========================================================


def admin_required(view):
    """
    Protege una ruta para que solo puedan utilizarla administradores.

    Primero exige una sesión válida y después comprueba el rol cargado
    desde PostgreSQL en current_user. Los clientes reciben una respuesta
    403 aunque intenten escribir manualmente la URL administrativa.
    """

    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if current_user.rol != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def cliente_required(view):
    """Protege rutas para que solo las cuentas con rol cliente las utilicen."""

    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if current_user.rol != "cliente":
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def cargar_opciones_servicios():
    """Carga los servicios actuales para los SelectField de los pedidos."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id_servicio, nombre FROM servicios ORDER BY nombre ASC")
    opciones = [
        (servicio["id_servicio"], servicio["nombre"]) for servicio in cursor.fetchall()
    ]
    cursor.close()
    conn.close()
    return opciones


@app.route("/registro", methods=["GET", "POST"])
def registro():
    """
    Permite registrar un nuevo usuario en PostgreSQL.

    La contraseña ingresada nunca se almacena directamente.
    Antes del INSERT se transforma mediante
    generate_password_hash().
    """

    # Si el usuario ya inició sesión, no necesita registrarse
    # nuevamente y se lo envía al panel principal.
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = UsuarioForm()

    formulario_valido = form.validate_on_submit()

    if formulario_valido:
        token = request.form.get("recaptcha_token") or request.form.get(
            "g-recaptcha-response"
        )
        captcha_valido, mensaje_captcha = verificar_recaptcha(
            token, request.remote_addr
        )
        if not captcha_valido:
            flash(mensaje_captcha, "danger")
            return render_template("registro.html", form=form, active="registro")

        correo_normalizado = normalizar_correo(form.correo.data)
        conn = obtener_conexion()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Comprobar ambas unicidades antes del INSERT con parámetros seguros.
            cursor.execute(
                """
                SELECT usuario, correo
                FROM usuarios
                WHERE usuario = %s OR correo = %s
                """,
                (form.usuario.data, correo_normalizado),
            )
            usuario_existente = cursor.fetchone()

            if usuario_existente:
                if usuario_existente["usuario"] == form.usuario.data:
                    flash("Ese nombre de usuario ya está registrado.", "danger")
                else:
                    flash("Ese correo electrónico ya está registrado.", "danger")
                return render_template("registro.html", form=form, active="registro")

            password_hash = generate_password_hash(form.password.data)

            # Usuario y perfil se crean en la misma transacción.
            cursor.execute(
                """
                INSERT INTO usuarios (usuario, correo, password, rol)
                VALUES (%s, %s, %s, 'cliente')
                RETURNING id_usuario
                """,
                (form.usuario.data, correo_normalizado, password_hash),
            )
            id_usuario = cursor.fetchone()["id_usuario"]

            cursor.execute(
                """
                INSERT INTO perfiles_usuario (id_usuario, nombres, apellidos, telefono)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    id_usuario,
                    form.nombres.data,
                    form.apellidos.data,
                    form.telefono.data,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            flash(
                "No fue posible completar el registro. Inténtalo nuevamente.", "danger"
            )
            return render_template("registro.html", form=form, active="registro")
        finally:
            cursor.close()
            conn.close()

        flash(
            "Usuario registrado correctamente. Ahora puedes iniciar sesión.",
            "success",
        )
        return redirect(url_for("login"))

    return render_template("registro.html", form=form, active="registro")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Permite iniciar sesión utilizando un usuario
    previamente registrado en PostgreSQL.

    La contraseña ingresada se compara con el hash
    almacenado mediante check_password_hash().
    """

    # Si ya existe una sesión activa, se evita mostrar
    # nuevamente el formulario de login.
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()

    if form.validate_on_submit():

        conn = obtener_conexion()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        identificador = form.usuario.data.strip()
        correo_login = (
            normalizar_correo(identificador) if "@" in identificador else None
        )

        # Buscar únicamente al usuario indicado.
        cursor.execute(
            """
                 SELECT u.id_usuario, u.usuario, u.correo, u.password, u.rol,
                     p.imagen
                 FROM usuarios u
                 LEFT JOIN perfiles_usuario p ON p.id_usuario = u.id_usuario
                 WHERE u.usuario = %s OR u.correo = %s
            """,
            (identificador, correo_login),
        )

        fila = cursor.fetchone()

        cursor.close()
        conn.close()

        # Convertir el registro de PostgreSQL en el objeto
        # Usuario utilizado por Flask-Login.
        usuario = Usuario.desde_fila(fila)

        # check_password_hash() compara la contraseña escrita
        # con el hash almacenado.
        #
        # En ningún momento necesitamos conocer ni recuperar
        # la contraseña original.
        if usuario and check_password_hash(usuario.password, form.password.data):
            # Crear y mantener la sesión del usuario.
            login_user(usuario)

            flash(f"Bienvenido, {usuario.usuario}.", "success")

            return redirect(url_for("dashboard"))

        # Si el usuario no existe o la contraseña es incorrecta,
        # no se inicia ninguna sesión.
        flash("Usuario, correo o contraseña incorrectos.", "danger")

    return render_template("login.html", form=form, active="login")


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    """Muestra y actualiza el perfil del usuario autenticado."""
    form = PerfilForm()
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute(
        """
        SELECT u.id_usuario, u.usuario, u.correo, u.rol,
               p.nombres, p.apellidos, p.telefono, p.imagen
        FROM usuarios u
        LEFT JOIN perfiles_usuario p ON p.id_usuario = u.id_usuario
        WHERE u.id_usuario = %s
        """,
        (current_user.id,),
    )
    perfil_actual = cursor.fetchone()

    if not perfil_actual:
        cursor.close()
        conn.close()
        abort(404)

    if request.method == "GET":
        form.nombres.data = perfil_actual["nombres"] or ""
        form.apellidos.data = perfil_actual["apellidos"] or ""
        form.correo.data = perfil_actual["correo"] or ""
        form.telefono.data = perfil_actual["telefono"] or ""

    if form.validate_on_submit():
        correo = normalizar_correo(form.correo.data)
        cursor.execute(
            """
            SELECT id_usuario
            FROM usuarios
            WHERE correo = %s AND id_usuario <> %s
            """,
            (correo, current_user.id),
        )
        correo_existente = cursor.fetchone() if correo else None

        if correo_existente:
            flash(
                "Ese correo electrónico ya está utilizado por otro usuario.", "danger"
            )
        else:
            try:
                imagen_nueva = guardar_imagen_perfil(form.imagen.data)
                cursor.execute(
                    """
                    UPDATE usuarios
                    SET correo = %s
                    WHERE id_usuario = %s
                    """,
                    (correo, current_user.id),
                )
                cursor.execute(
                    """
                    INSERT INTO perfiles_usuario (id_usuario, nombres, apellidos, telefono, imagen)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id_usuario) DO UPDATE SET
                        nombres = EXCLUDED.nombres,
                        apellidos = EXCLUDED.apellidos,
                        telefono = EXCLUDED.telefono,
                        imagen = COALESCE(EXCLUDED.imagen, perfiles_usuario.imagen)
                    """,
                    (
                        current_user.id,
                        form.nombres.data,
                        form.apellidos.data,
                        form.telefono.data,
                        imagen_nueva,
                    ),
                )
                conn.commit()
                current_user.correo = correo
                if imagen_nueva:
                    current_user.imagen = imagen_nueva
                flash("Perfil actualizado correctamente.", "success")
                return redirect(url_for("perfil"))
            except ValueError as error:
                conn.rollback()
                flash(str(error), "danger")
            except Exception:
                conn.rollback()
                flash("No fue posible actualizar el perfil.", "danger")

    cursor.close()
    conn.close()
    return render_template(
        "perfil.html",
        form=form,
        perfil=perfil_actual,
        imagen_perfil=imagen_perfil_url(perfil_actual["imagen"]),
        active="perfil",
    )


@app.route("/cambiar-password", methods=["GET", "POST"])
@login_required
def cambiar_password():
    """Permite cambiar la contraseña verificando primero la actual."""
    form = CambioPasswordForm()

    if form.validate_on_submit():
        if not check_password_hash(current_user.password, form.password_actual.data):
            flash("La contraseña actual no es correcta.", "danger")
            return render_template("cambiar_password.html", form=form, active="perfil")

        nuevo_hash = generate_password_hash(form.password_nueva.data)
        conn = obtener_conexion()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE usuarios
                SET password = %s
                WHERE id_usuario = %s
                """,
                (nuevo_hash, current_user.id),
            )
            conn.commit()
            current_user.password = nuevo_hash
            flash("Contraseña actualizada correctamente.", "success")
            return redirect(url_for("perfil"))
        except Exception:
            conn.rollback()
            flash("No fue posible actualizar la contraseña.", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template("cambiar_password.html", form=form, active="perfil")


@app.route("/dashboard")
@login_required
def dashboard():
    """
    Panel privado disponible únicamente para
    usuarios que hayan iniciado sesión.
    """

    if current_user.rol == "cliente":
        conn = obtener_conexion()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE estado NOT IN ('Entregado', 'Cancelado')) AS pendientes
            FROM pedidos
            WHERE id_usuario = %s
            """,
            (current_user.id,),
        )
        resumen = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template(
            "dashboard_cliente.html",
            active="dashboard",
            resumen=resumen,
        )

    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE estado = 'Solicitado') AS solicitados,
               COUNT(*) FILTER (WHERE estado IN ('En revisión', 'En reparación')) AS en_proceso,
               COUNT(*) FILTER (WHERE estado = 'Listo') AS listos,
               COUNT(*) FILTER (WHERE estado = 'Entregado') AS entregados
        FROM pedidos
        """)
    resumen = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template("dashboard.html", active="dashboard", resumen=resumen)


@app.route("/pedido/nuevo", methods=["GET", "POST"])
@cliente_required
def nuevo_pedido():
    """Crea un pedido siempre asociado al cliente autenticado."""
    form = PedidoForm()
    form.servicio.choices = cargar_opciones_servicios()

    if request.method == "GET":
        servicio_parametro = request.args.get("servicio", type=int)
        servicios_validos = {valor for valor, _ in form.servicio.choices}
        if servicio_parametro in servicios_validos:
            form.servicio.data = servicio_parametro

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO pedidos (id_usuario, id_servicio, equipo, descripcion, solicita_factura)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    current_user.id,
                    form.servicio.data,
                    form.equipo.data,
                    form.descripcion.data,
                    form.solicita_factura.data,
                ),
            )
            conn.commit()
            flash("Solicitud enviada correctamente.", "success")
            return redirect(url_for("mis_pedidos"))
        except Exception:
            conn.rollback()
            flash("No fue posible registrar la solicitud.", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template("formulario_pedido.html", form=form, active="mis_pedidos")


@app.route("/mis-pedidos")
@cliente_required
def mis_pedidos():
    """Lista exclusivamente los pedidos del cliente autenticado."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT p.id_pedido, p.equipo, p.descripcion, p.estado,
               p.solicita_factura, p.fecha_solicitud, p.fecha_actualizacion,
               s.nombre AS servicio_nombre,
               f.id_factura
        FROM pedidos p
        LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
        LEFT JOIN facturas f ON f.id_pedido = p.id_pedido
        WHERE p.id_usuario = %s
        ORDER BY p.fecha_solicitud DESC
        """,
        (current_user.id,),
    )
    pedidos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        "mis_pedidos.html",
        pedidos=pedidos,
        solicitar_factura_form=PedidoAccionForm(),
        active="mis_pedidos",
    )


@app.route("/mis-pedidos/<int:id>/solicitar-factura", methods=["POST"])
@cliente_required
def solicitar_factura(id):
    """Solicita factura solo para un pedido perteneciente al cliente actual."""
    form = PedidoAccionForm()
    if not form.validate_on_submit():
        flash("No fue posible validar la solicitud de factura.", "danger")
        return redirect(url_for("mis_pedidos"))

    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE pedidos
        SET solicita_factura = TRUE, fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id_pedido = %s AND id_usuario = %s
        """,
        (id, current_user.id),
    )
    if cursor.rowcount == 0:
        conn.rollback()
        cursor.close()
        conn.close()
        abort(404)
    conn.commit()
    cursor.close()
    conn.close()
    flash("La factura fue solicitada para este pedido.", "success")
    return redirect(url_for("mis_pedidos"))


@app.route("/pedidos")
@admin_required
def pedidos_admin():
    """Muestra todos los pedidos para gestión administrativa."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT p.id_pedido, p.equipo, p.descripcion, p.estado,
               p.solicita_factura, p.fecha_solicitud, p.fecha_actualizacion,
             u.usuario, u.correo,
             pu.nombres, pu.apellidos,
               s.nombre AS servicio_nombre,
               f.id_factura
        FROM pedidos p
        JOIN usuarios u ON u.id_usuario = p.id_usuario
         LEFT JOIN perfiles_usuario pu ON pu.id_usuario = u.id_usuario
        LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
        LEFT JOIN facturas f ON f.id_pedido = p.id_pedido
        ORDER BY p.fecha_solicitud DESC
        """)
    pedidos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        "pedidos_admin.html",
        pedidos=pedidos,
        estado_form=PedidoEstadoForm(),
        emitir_form=EmitirFacturaForm(),
        active="pedidos",
    )


@app.route("/pedidos/<int:id>/estado", methods=["POST"])
@admin_required
def actualizar_estado_pedido(id):
    """Actualiza el estado usando únicamente los valores definidos por el formulario."""
    form = PedidoEstadoForm()
    if not form.validate_on_submit():
        flash("Selecciona un estado válido.", "danger")
        return redirect(url_for("pedidos_admin"))

    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT p.id_pedido, f.id_factura
        FROM pedidos p
        LEFT JOIN facturas f ON f.id_pedido = p.id_pedido
        WHERE p.id_pedido = %s
        """,
        (id,),
    )
    pedido = cursor.fetchone()

    if not pedido:
        conn.close()
        abort(404)

    if form.estado.data == "Cancelado" and pedido["id_factura"]:
        conn.rollback()
        cursor.close()
        conn.close()
        flash(
            "No se puede cancelar un pedido que ya tiene una factura emitida.",
            "danger",
        )
        return redirect(url_for("pedidos_admin"))

    cursor.execute(
        """
        UPDATE pedidos
        SET estado = %s, fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id_pedido = %s
        """,
        (form.estado.data, id),
    )
    if cursor.rowcount == 0:
        conn.rollback()
        cursor.close()
        conn.close()
        abort(404)
    conn.commit()
    cursor.close()
    conn.close()
    flash("Estado del pedido actualizado.", "success")
    return redirect(url_for("pedidos_admin"))


@app.route("/pedidos/<int:id>/factura", methods=["POST"])
@admin_required
def emitir_factura(id):
    """Emite una sola factura vinculada al pedido y a su usuario."""
    form = EmitirFacturaForm()
    if not form.validate_on_submit():
        flash("No fue posible validar la emisión de la factura.", "danger")
        return redirect(url_for("pedidos_admin"))

    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT p.id_pedido, p.id_usuario, p.id_servicio, p.equipo,
               p.solicita_factura, s.nombre AS servicio_nombre,
               s.precio, f.id_factura
        FROM pedidos p
        LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
        LEFT JOIN facturas f ON f.id_pedido = p.id_pedido
        WHERE p.id_pedido = %s
        """,
        (id,),
    )
    pedido = cursor.fetchone()

    if not pedido:
        cursor.close()
        conn.close()
        abort(404)
    if pedido["id_factura"]:
        conn.close()
        flash("Este pedido ya tiene una factura emitida.", "warning")
        return redirect(url_for("pedidos_admin"))
    if not pedido["solicita_factura"]:
        conn.close()
        flash("El cliente todavía no ha solicitado factura.", "warning")
        return redirect(url_for("pedidos_admin"))

    numero = f"FAC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{id}"
    cursor.execute(
        """
        INSERT INTO facturas (numero, id_cliente, id_servicio, fecha, total, estado, id_usuario, id_pedido)
        VALUES (%s, NULL, %s, CURRENT_DATE, %s, 'Pendiente', %s, %s)
        """,
        (
            numero,
            pedido["id_servicio"],
            pedido["precio"] or 0,
            pedido["id_usuario"],
            id,
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash(f"Factura {numero} emitida correctamente.", "success")
    return redirect(url_for("pedidos_admin"))


@app.route("/mis-facturas")
@cliente_required
def mis_facturas():
    """Lista exclusivamente las facturas del cliente autenticado."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT f.id_factura, f.numero, f.fecha, f.total, f.estado,
               f.id_pedido, p.equipo, s.nombre AS servicio_nombre
        FROM facturas f
        LEFT JOIN pedidos p ON p.id_pedido = f.id_pedido
        LEFT JOIN servicios s ON s.id_servicio = f.id_servicio
        WHERE f.id_usuario = %s
        ORDER BY f.fecha DESC, f.id_factura DESC
        """,
        (current_user.id,),
    )
    facturas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        "mis_facturas.html", facturas=facturas, active="mis_facturas"
    )


@app.route("/facturas/<int:id>/pdf")
@login_required
def descargar_factura(id):
    """Genera un PDF y limita el acceso del cliente a sus propias facturas."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if current_user.rol == "admin":
        filtro = "f.id_factura = %s"
        parametros = (id,)
    else:
        filtro = "f.id_factura = %s AND f.id_usuario = %s"
        parametros = (id, current_user.id)

    cursor.execute(
        f"""
        SELECT f.id_factura, f.numero, f.fecha, f.total,
               f.id_pedido, p.equipo,
               u.usuario, u.correo,
               pu.nombres, pu.apellidos,
               s.nombre AS servicio_nombre
        FROM facturas f
        LEFT JOIN usuarios u ON u.id_usuario = f.id_usuario
        LEFT JOIN perfiles_usuario pu ON pu.id_usuario = u.id_usuario
        LEFT JOIN pedidos p ON p.id_pedido = f.id_pedido
        LEFT JOIN servicios s ON s.id_servicio = f.id_servicio
        WHERE {filtro}
        """,
        parametros,
    )
    factura = cursor.fetchone()
    cursor.close()
    conn.close()

    if not factura:
        abort(404)

    buffer = BytesIO()
    documento = canvas.Canvas(buffer, pagesize=letter)
    documento.setTitle(f"Factura {factura['numero']}")
    styles = getSampleStyleSheet()
    ancho = letter[0] - 2 * inch

    # Encabezado textual profesional, sin depender de un logotipo externo.
    documento.setFillColor(colors.HexColor("#112248"))
    documento.setFont("Helvetica-Bold", 24)
    documento.drawString(72, 735, "PC-Fix")
    documento.setFont("Helvetica", 10)
    documento.setFillColor(colors.HexColor("#4b5563"))
    documento.drawString(72, 718, "Servicio técnico de equipos informáticos")
    documento.setFillColor(colors.HexColor("#111827"))
    documento.setFont("Helvetica-Bold", 19)
    documento.drawRightString(letter[0] - 72, 735, "FACTURA")
    documento.setFont("Helvetica", 10)
    documento.drawRightString(letter[0] - 72, 718, f"N.º {factura['numero']}")
    documento.drawRightString(letter[0] - 72, 702, f"Fecha: {factura['fecha']}")
    documento.setStrokeColor(colors.HexColor("#d4af37"))
    documento.setLineWidth(2)
    documento.line(72, 682, letter[0] - 72, 682)

    nombre_cliente = f"{factura['nombres'] or ''} {factura['apellidos'] or ''}".strip()
    cliente_data = [
        [Paragraph("<b>DATOS DEL CLIENTE</b>", styles["Normal"]), ""],
        ["Nombre completo", nombre_cliente or factura["usuario"] or "No registrado"],
        ["Usuario", factura["usuario"] or "No registrado"],
        ["Correo", factura["correo"] or "No registrado"],
        ["Identificador del pedido", str(factura["id_pedido"] or "No vinculado")],
    ]
    cliente_tabla = Table(cliente_data, colWidths=[1.7 * inch, ancho - 1.7 * inch])
    cliente_tabla.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#e8eef8")),
                ("TEXTCOLOR", (0, 0), (1, 0), colors.HexColor("#112248")),
                ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    cliente_tabla.wrapOn(documento, ancho, 150)
    cliente_tabla.drawOn(documento, 72, 565)

    precio = float(factura["total"] or 0)
    detalle_data = [
        ["Servicio", "Equipo", "Cantidad", "Precio"],
        [
            Paragraph(
                factura["servicio_nombre"] or "Servicio no disponible", styles["Normal"]
            ),
            Paragraph(factura["equipo"] or "No especificado", styles["Normal"]),
            "1",
            f"${precio:.2f}",
        ],
    ]
    detalle_tabla = Table(
        detalle_data, colWidths=[2.35 * inch, 2.15 * inch, 0.7 * inch, 1.0 * inch]
    )
    detalle_tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#112248")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9ca3af")),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    detalle_tabla.wrapOn(documento, ancho, 100)
    detalle_tabla.drawOn(documento, 72, 480)

    resumen_data = [["Subtotal", f"${precio:.2f}"], ["TOTAL", f"${precio:.2f}"]]
    resumen_tabla = Table(
        resumen_data, colWidths=[1.5 * inch, 1.2 * inch], hAlign="RIGHT"
    )
    resumen_tabla.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 13),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#112248")),
                ("LINEABOVE", (0, 1), (-1, 1), 1, colors.HexColor("#d4af37")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    resumen_tabla.wrapOn(documento, ancho, 70)
    resumen_tabla.drawOn(documento, letter[0] - 72 - 2.7 * inch, 385)

    documento.setFillColor(colors.HexColor("#4b5563"))
    documento.setFont("Helvetica-Oblique", 9)
    documento.drawCentredString(letter[0] / 2, 70, "Gracias por confiar en PC-Fix.")
    documento.drawCentredString(
        letter[0] / 2, 54, "Documento generado por el sistema PC-Fix."
    )
    documento.save()
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"factura-{factura['numero']}.pdf",
    )


@app.route("/logout")
@login_required
def logout():
    """
    Finaliza la sesión del usuario autenticado.
    """

    # Elimina la sesión administrada por Flask-Login.
    logout_user()

    flash("La sesión se cerró correctamente.", "info")

    return redirect(url_for("login"))


# ===== Rutas Principales =====


@app.route("/")
def index():
    return render_template(
        "index.html",
        active="inicio",
        nombre_empresa=NOMBRE_EMPRESA,
        tipos_asistencia=TIPOS_ASISTENCIA,
    )


@app.route("/conocenos")
def conocenos():
    return render_template("conocenos.html", active="conocenos")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html", active="contacto")


# ===== Módulo de Servicios / Productos (CRUD Completo en PostgreSQL) =====


@app.route("/servicios")
@app.route("/productos")
@login_required
def servicios():
    """Listar registros mediante SELECT y JOIN con PostgreSQL."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Consulta relacionada entre servicios y proveedores con JOIN
    cursor.execute("""
        SELECT s.id_servicio, s.nombre, s.descripcion, s.precio, s.duracion, s.imagen, s.id_proveedor,
               p.empresa AS proveedor_empresa
        FROM servicios s
        LEFT JOIN proveedores p ON s.id_proveedor = p.id_proveedor
        ORDER BY s.id_servicio ASC
    """)
    servicios_db = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("servicios.html", active="servicios", servicios=servicios_db)


@app.route("/servicios/nuevo", methods=["GET", "POST"])
@app.route("/productos/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_servicio():
    """Registrar un nuevo registro mediante INSERT INTO parametrizado."""
    form = ProductoForm()
    form.id_proveedor.choices = obtener_opciones_proveedores()
    # Cargar automáticamente las imágenes disponibles.
    form.imagen.choices = obtener_imagenes_servicios()
    if form.validate_on_submit():
        id_prov = (
            form.id_proveedor.data
            if form.id_proveedor.data and form.id_proveedor.data != 0
            else None
        )
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (
                form.nombre.data,
                form.descripcion.data,
                form.precio.data,
                form.duracion.data,
                form.imagen.data,
                id_prov,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash(
            f"Servicio '{form.nombre.data}' registrado exitosamente en PostgreSQL.",
            "success",
        )
        return redirect(url_for("servicios"))

    return render_template(
        "formulario_producto.html",
        active="servicios",
        form=form,
        titulo="Nuevo Servicio",
    )


@app.route("/servicios/editar/<int:id>", methods=["GET", "POST"])
@app.route("/productos/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_servicio(id):
    """Modificar un registro existente utilizando WHERE y UPDATE parametrizado."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM servicios WHERE id_servicio = %s", (id,))
    servicio = cursor.fetchone()

    if not servicio:
        cursor.close()
        conn.close()
        flash("El servicio que intentas editar no existe.", "danger")
        return redirect(url_for("servicios"))

    form = ProductoForm()
    form.id_proveedor.choices = obtener_opciones_proveedores()
    form.imagen.choices = obtener_imagenes_servicios()

    if request.method == "GET":
        form.nombre.data = servicio["nombre"]
        form.descripcion.data = servicio["descripcion"]
        form.precio.data = float(servicio["precio"])
        form.duracion.data = servicio["duracion"]
        form.imagen.data = servicio["imagen"]
        form.id_proveedor.data = (
            servicio["id_proveedor"] if servicio["id_proveedor"] else 0
        )

    if form.validate_on_submit():
        id_prov = (
            form.id_proveedor.data
            if form.id_proveedor.data and form.id_proveedor.data != 0
            else None
        )
        cursor.execute(
            """
            UPDATE servicios
            SET nombre = %s, descripcion = %s, precio = %s, duracion = %s, imagen = %s, id_proveedor = %s
            WHERE id_servicio = %s
        """,
            (
                form.nombre.data,
                form.descripcion.data,
                form.precio.data,
                form.duracion.data,
                form.imagen.data,
                id_prov,
                id,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash(
            f"Servicio '{form.nombre.data}' actualizado correctamente en PostgreSQL.",
            "info",
        )
        return redirect(url_for("servicios"))

    cursor.close()
    conn.close()
    return render_template(
        "formulario_producto.html",
        active="servicios",
        form=form,
        titulo="Editar Servicio",
    )


@app.route("/servicios/eliminar/<int:id>", methods=["POST"])
@app.route("/productos/eliminar/<int:id>", methods=["POST"])
@admin_required
def eliminar_servicio(id):
    """Eliminar únicamente el registro seleccionado utilizando DELETE FROM ... WHERE."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM servicios WHERE id_servicio = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Servicio eliminado permanentemente de la base de datos.", "warning")
    return redirect(url_for("servicios"))


# ===== Módulos Complementarios (Clientes, Proveedores, Facturación) =====


@app.route("/clientes")
@admin_required
def clientes():
    return render_template("clientes.html", active="clientes", clientes=CLIENTES)


@app.route("/clientes/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        nuevo_item = {
            "nombre": form.nombre.data,
            "telefono": form.telefono.data,
            "equipo": form.equipo.data,
            "estado": form.estado.data,
        }
        CLIENTES.append(nuevo_item)
        flash("Cliente registrado con éxito.", "success")
        return redirect(url_for("clientes"))
    return render_template(
        "formulario_cliente.html", active="clientes", form=form, titulo="Nuevo Cliente"
    )


@app.route("/proveedores")
@admin_required
def proveedores():
    return render_template(
        "proveedores.html", active="proveedores", proveedores=PROVEEDORES
    )


@app.route("/proveedores/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_proveedor():
    form = ProveedorForm()
    if form.validate_on_submit():
        nuevo_item = {
            "empresa": form.empresa.data,
            "contacto": form.contacto.data,
            "telefono": form.telefono.data,
            "categoria": form.categoria.data,
        }
        PROVEEDORES.append(nuevo_item)
        flash("Proveedor registrado con éxito.", "success")
        return redirect(url_for("proveedores"))
    return render_template(
        "formulario_proveedor.html",
        active="proveedores",
        form=form,
        titulo="Nuevo Proveedor",
    )


@app.route("/facturacion")
@admin_required
def facturacion():
    return render_template("facturacion.html", active="facturacion", facturas=FACTURAS)


@app.route("/facturacion/nuevo", methods=["GET", "POST"])
@admin_required
def nueva_factura():
    form = FacturacionForm()
    if form.validate_on_submit():
        nuevo_item = {
            "numero": form.numero.data,
            "cliente": form.cliente.data,
            "servicio": form.servicio.data,
            "fecha": form.fecha.data.strftime("%Y-%m-%d"),
            "total": form.total.data,
            "estado": form.estado.data,
        }
        FACTURAS.append(nuevo_item)
        flash("Factura registrada con éxito.", "success")
        return redirect(url_for("facturacion"))
    return render_template(
        "formulario_facturacion.html",
        active="facturacion",
        form=form,
        titulo="Nueva Factura",
    )


if __name__ == "__main__":
    app.run(debug=True)
