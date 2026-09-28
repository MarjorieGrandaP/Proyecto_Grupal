from finanzas import IVA_PREDETERMINADO, validar_tarifa, importes
from pagos import registrar_rutas_pagos, resumen_pago, solicitar_anticipo
from forms.producto_form import separar_duracion
from conexion.bootstrap_admin import crear_admin_desde_entorno
from biblioteca import opciones_imagenes, resolver_imagen, registrar_biblioteca
from forms.imagen_servicio_form import ImagenServicioForm
from forms.detalle_servicio_form import DetalleServicioForm
from forms.cancelacion_form import ObservacionPedidoForm
from forms.equipo_form import EquipoPedidoForm
from html import escape
from forms.cancelacion_form import (
    CancelacionForm,
    AnticipoForm,
    MOTIVOS_CLIENTE,
    MOTIVOS_ADMIN,
)
from forms.pedido_estado_form import (
    TRANSICIONES_PEDIDO,
    COLORES_PEDIDO,
    mensaje_estado_pedido,
)
from forms.pedido_form import EditarPedidoForm
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
    LoginForm,
    UsuarioForm,
    PerfilForm,
    CambioPasswordForm,
    PedidoForm,
    PedidoEstadoForm,
    EmitirFacturaForm,
    PedidoAccionForm,
    EliminarForm,
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
app.config["IVA_RATE"] = validar_tarifa(os.getenv("IVA_RATE", IVA_PREDETERMINADO))
for clave_pago in (
    "PAYMENT_BANK",
    "PAYMENT_ACCOUNT_TYPE",
    "PAYMENT_ACCOUNT_NUMBER",
    "PAYMENT_ACCOUNT_HOLDER",
):
    app.config[clave_pago] = os.getenv(clave_pago, "")
app.jinja_env.globals["precio_con_iva"] = lambda precio: importes(
    precio, app.config["IVA_RATE"]
)["total"]


app.jinja_env.globals.update(
    transiciones_pedido=TRANSICIONES_PEDIDO,
    colores_pedido=COLORES_PEDIDO,
    mensaje_estado_pedido=mensaje_estado_pedido,
)


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
    crear_admin_desde_entorno(obtener_conexion)
except Exception as err:
    print(f"[AVISO INICIO] Error al inicializar base de datos: {err}")


def obtener_opciones_proveedores():
    """Recupera la lista de proveedores desde PostgreSQL para poblar el selector del formulario."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id_proveedor, empresa FROM proveedores WHERE activo = TRUE ORDER BY empresa ASC"
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
    return opciones_imagenes(app.root_path, obtener_conexion)


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
    cursor.execute(
        "SELECT id_servicio, nombre FROM servicios WHERE activo = TRUE AND archivado = FALSE ORDER BY nombre ASC"
    )
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
                "SELECT id_servicio FROM servicios WHERE id_servicio = %s AND activo = TRUE AND archivado = FALSE FOR SHARE",
                (form.servicio.data,),
            )
            if not cursor.fetchone():
                flash(
                    "El servicio ya no está disponible para nuevos pedidos.", "warning"
                )
                return redirect(url_for("nuevo_pedido"))
            cursor.execute(
                "SELECT set_config('pcfix.usuario_actor', %s, TRUE)",
                (str(current_user.id),),
            )
            cursor.execute(
                """
                INSERT INTO pedidos (id_usuario, id_servicio, equipo, modelo, descripcion, solicita_factura,
                                     terminos_aceptados, fecha_aceptacion_terminos)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                """,
                (
                    current_user.id,
                    form.servicio.data,
                    form.equipo.data,
                    (form.modelo.data or "").strip() or None,
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
    q = request.args.get("q", "").strip()
    patron = f"%{q}%"
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT p.id_pedido, p.total, p.anticipo_requerido, p.saldo_requerido, p.equipo, p.modelo, p.descripcion, p.estado,
               p.solicita_factura, p.fecha_solicitud, p.fecha_actualizacion,
               (clock_timestamp()::timestamp BETWEEN p.fecha_solicitud
                AND p.fecha_solicitud + INTERVAL '5 minutes') AS dentro_plazo,
               s.nombre AS servicio_nombre,
               COALESCE(s.requiere_entrega_equipo, TRUE) AS requiere_entrega_equipo,
               f.id_factura
        FROM pedidos p
        LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
        LEFT JOIN facturas f ON f.id_pedido = p.id_pedido
        WHERE p.id_usuario = %s
        AND (p.id_pedido::text ILIKE %s OR s.nombre ILIKE %s
             OR p.equipo ILIKE %s OR p.descripcion ILIKE %s OR p.estado ILIKE %s)
        ORDER BY p.fecha_solicitud DESC
        """,
        (current_user.id,) + (patron,) * 5,
    )
    pedidos = cursor.fetchall()
    for pedido in pedidos:
        pedido["pago"] = resumen_pago(cursor, pedido)
    cursor.execute(
        """SELECT p.id_pedido, COALESCE(s.requiere_entrega_equipo, TRUE) AS requiere_entrega_equipo
           FROM pedidos p LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
           WHERE p.id_usuario = %s AND p.estado = 'Listo'
           ORDER BY p.fecha_actualizacion DESC""",
        (current_user.id,),
    )
    pedidos_listos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        "mis_pedidos.html",
        pedidos=pedidos,
        pedidos_listos=pedidos_listos,
        q=q,
        solicitar_factura_form=PedidoAccionForm(),
        cancelar_form=crear_cancelacion_form(),
        active="mis_pedidos",
    )


@app.route("/mis-pedidos/<int:id>/seguimiento")
@app.route("/pedidos/<int:id>/seguimiento")
@login_required
def seguimiento_pedido(id):
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT p.id_pedido, p.estado, p.equipo, p.modelo, p.fecha_entrega, (p.fecha_entrega + INTERVAL '3 months')::date AS garantia_fin,
                          CURRENT_DATE <= (p.fecha_entrega + INTERVAL '3 months')::date AS garantia_vigente, p.anticipo_solicitado, p.anticipo_pagado,
                          COALESCE(s.requiere_entrega_equipo, TRUE) AS requiere_entrega_equipo
                   FROM pedidos p LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
                   WHERE p.id_pedido = %s AND (%s OR p.id_usuario = %s)""",
                (id, current_user.rol == "admin", current_user.id),
            )
            pedido = cursor.fetchone()
            if not pedido:
                abort(404)
            cursor.execute(
                """SELECT h.estado_anterior, h.estado_nuevo, h.fecha_hora,
                          CASE WHEN %s THEN h.observacion END AS observacion,
                          CASE WHEN %s THEN h.motivo_cancelacion END AS motivo_cancelacion,
                          CASE WHEN %s THEN u.usuario END AS actor
                   FROM historial_estado_pedidos h
                   LEFT JOIN usuarios u ON u.id_usuario = h.id_usuario_actor
                   JOIN pedidos p ON p.id_pedido = h.id_pedido
                   WHERE h.id_pedido = %s AND (%s OR p.id_usuario = %s)
                   ORDER BY h.fecha_hora, h.id_historial""",
                (current_user.rol == "admin",) * 3
                + (id, current_user.rol == "admin", current_user.id),
            )
            historial = cursor.fetchall()
            cursor.execute(
                """SELECT o.texto, o.fecha_hora, o.visible_cliente, CASE WHEN %s THEN u.usuario END AS actor
                   FROM observaciones_pedidos o LEFT JOIN usuarios u ON u.id_usuario=o.id_usuario_actor
                   WHERE o.id_pedido=%s AND (%s OR o.visible_cliente=TRUE)
                   ORDER BY o.fecha_hora, o.id_observacion""",
                (current_user.rol == "admin", id, current_user.rol == "admin"),
            )
            observaciones = cursor.fetchall()
    finally:
        conn.close()
    return render_template(
        (
            (
                "components/observaciones_pedido.html"
                if request.args.get("seccion") == "observaciones"
                else "components/linea_tiempo.html"
            )
            if request.args.get("modal") == "1"
            else "seguimiento_pedido.html"
        ),
        pedido=pedido,
        historial=historial,
        observaciones=observaciones,
        active="mis_pedidos",
    )


MENSAJE_PEDIDO_BLOQUEADO = (
    "Este pedido ya está siendo procesado y no puede modificarse ni cancelarse desde el portal. "
    "Comunícate con el administrador si necesitas realizar un cambio."
)


def pedido_propio_bloqueado(cursor, id):
    """Bloquea el pedido propio durante la validación y el UPDATE."""
    cursor.execute(
        "SELECT * FROM pedidos WHERE id_pedido = %s AND id_usuario = %s FOR UPDATE",
        (id, current_user.id),
    )
    pedido = cursor.fetchone()
    if not pedido:
        abort(404)
    cursor.execute("SELECT 1 FROM facturas WHERE id_pedido = %s", (id,))
    tiene_factura = cursor.fetchone() is not None
    return pedido, pedido["estado"] == "Solicitado" and not tiene_factura


@app.route("/mis-pedidos/<int:id>/editar", methods=["GET", "POST"])
@cliente_required
def editar_pedido(id):
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            pedido, permitido = pedido_propio_bloqueado(cursor, id)
            if not permitido:
                flash(MENSAJE_PEDIDO_BLOQUEADO, "warning")
                return redirect(url_for("mis_pedidos"))
            form = EditarPedidoForm()
            cursor.execute(
                """SELECT id_servicio, nombre, activo, archivado FROM servicios
                   WHERE (activo = TRUE AND archivado = FALSE) OR id_servicio = %s ORDER BY nombre""",
                (pedido["id_servicio"],),
            )
            form.servicio.choices = [
                (
                    r["id_servicio"],
                    r["nombre"]
                    + (
                        " (Archivado, actual)"
                        if r["archivado"]
                        else " (En pausa, actual)" if not r["activo"] else ""
                    ),
                )
                for r in cursor.fetchall()
            ]
            if request.method == "GET":
                form.servicio.data = pedido["id_servicio"]
                form.equipo.data = pedido["equipo"]
                form.modelo.data = pedido["modelo"]
                form.descripcion.data = pedido["descripcion"]
            if form.validate_on_submit():
                # Revalidar y bloquear el servicio seleccionado frente a una pausa concurrente.
                cursor.execute(
                    """SELECT id_servicio FROM servicios
                       WHERE id_servicio = %s AND ((activo = TRUE AND archivado = FALSE) OR id_servicio = %s)
                       FOR SHARE""",
                    (form.servicio.data, pedido["id_servicio"]),
                )
                if not cursor.fetchone():
                    form.servicio.errors.append("Selecciona un servicio activo.")
                else:
                    cursor.execute(
                        """UPDATE pedidos
                           SET id_servicio = %s, equipo = %s, modelo = %s, descripcion = %s,
                               fecha_actualizacion = CURRENT_TIMESTAMP
                           WHERE id_pedido = %s AND id_usuario = %s AND estado = 'Solicitado'
                             AND NOT EXISTS (SELECT 1 FROM facturas WHERE id_pedido = %s)""",
                        (
                            form.servicio.data,
                            form.equipo.data,
                            (form.modelo.data or "").strip() or None,
                            form.descripcion.data,
                            id,
                            current_user.id,
                            id,
                        ),
                    )
                    conn.commit()
                    flash("Pedido actualizado correctamente.", "success")
                    return redirect(url_for("mis_pedidos"))
            return render_template(
                "formulario_pedido.html", form=form, editando=True, active="mis_pedidos"
            )
    finally:
        conn.close()


def crear_cancelacion_form(admin=False):
    form = CancelacionForm()
    motivos = MOTIVOS_ADMIN if admin else MOTIVOS_CLIENTE
    form.motivo.choices = [("", "Selecciona un motivo")] + [(m, m) for m in motivos]
    return form


def procesar_cancelacion(id, admin=False):
    form = crear_cancelacion_form(admin)
    if not form.validate_on_submit():
        abort(
            400,
            description="Selecciona un motivo válido y completa la observación si eliges Otro.",
        )
    destino = "pedidos_admin" if admin else "mis_pedidos"
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT p.*,
                   (clock_timestamp()::timestamp BETWEEN fecha_solicitud
                    AND fecha_solicitud + INTERVAL '5 minutes') AS dentro_plazo
                   FROM pedidos p WHERE id_pedido = %s AND (%s OR id_usuario = %s)
                   FOR UPDATE""",
                (id, admin, current_user.id),
            )
            pedido = cursor.fetchone()
            if not pedido:
                abort(404)
            cursor.execute("SELECT 1 FROM facturas WHERE id_pedido = %s", (id,))
            facturado = cursor.fetchone() is not None
            permitido = (
                pedido["estado"] not in ("Entregado", "Cancelado")
                if admin
                else pedido["estado"] == "Solicitado"
            )
            if facturado or not permitido:
                flash(MENSAJE_PEDIDO_BLOQUEADO, "warning")
                return redirect(url_for(destino))
            if not admin:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM pagos WHERE id_pedido=%s AND estado='Confirmado') AS pago_confirmado",
                    (id,),
                )
                if cursor.fetchone()["pago_confirmado"]:
                    flash(
                        "Ya existe un pago confirmado. Comunícate con administración para solicitar la cancelación.",
                        "warning",
                    )
                    return redirect(url_for(destino))
            if not admin and not pedido["dentro_plazo"]:
                flash(
                    "Solo puedes cancelar durante los primeros 5 minutos desde la creación del pedido.",
                    "warning",
                )
                return redirect(url_for(destino))
            cursor.execute(
                "SELECT set_config('pcfix.usuario_actor', %s, TRUE)",
                (str(current_user.id),),
            )
            cursor.execute(
                """UPDATE pedidos SET estado='Cancelado', motivo_cancelacion=%s,
                          observacion=%s, cancelado_por=%s, fecha_cancelacion=CURRENT_TIMESTAMP,
                          fecha_actualizacion=CURRENT_TIMESTAMP
                   WHERE id_pedido=%s
                     AND (%s OR clock_timestamp()::timestamp BETWEEN fecha_solicitud
                          AND fecha_solicitud + INTERVAL '5 minutes')""",
                (
                    form.motivo.data,
                    (form.observacion.data or "").strip() or None,
                    current_user.id,
                    id,
                    admin,
                ),
            )
            if cursor.rowcount == 0:
                flash("La ventana de 5 minutos para cancelar ha finalizado.", "warning")
                return redirect(url_for(destino))
        conn.commit()
        flash("Pedido cancelado. Permanece en el historial.", "success")
    finally:
        conn.close()
    return redirect(url_for(destino))


@app.route("/mis-pedidos/<int:id>/cancelar", methods=["POST"])
@cliente_required
def cancelar_pedido(id):
    return procesar_cancelacion(id)


@app.route("/pedidos/<int:id>/cancelar", methods=["POST"])
@admin_required
def cancelar_pedido_admin(id):
    return procesar_cancelacion(id, admin=True)


@app.route("/pedidos/<int:id>/anticipo", methods=["POST"])
@admin_required
def registrar_anticipo(id):
    form = AnticipoForm()
    if not form.validate_on_submit():
        abort(400)
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                solicitar_anticipo(cursor, id, app.config["IVA_RATE"])
            except ValueError as error:
                flash(str(error), "warning")
                return redirect(url_for("pedidos_admin"))
        conn.commit()
        flash(
            "Anticipo solicitado. Se requiere un comprobante y su verificación administrativa.",
            "success",
        )
    finally:
        conn.close()
    return redirect(url_for("pedidos_admin"))


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
        WHERE id_pedido = %s AND id_usuario = %s AND estado <> 'Cancelado'
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
    q = request.args.get("q", "").strip()
    estados = [valor for valor, _ in PedidoEstadoForm().estado.choices]
    estado = request.args.get("estado", "")
    if estado not in estados:
        estado = ""
    factura = request.args.get("factura", "")
    facturas_filtro = {
        "": "TRUE",
        "no_solicitada": "p.solicita_factura = FALSE AND f.id_factura IS NULL",
        "solicitada": "p.solicita_factura = TRUE AND f.id_factura IS NULL",
        "emitida": "f.id_factura IS NOT NULL",
    }
    if factura not in facturas_filtro:
        factura = ""
    fecha = request.args.get("fecha", "")
    try:
        fecha_param = datetime.strptime(fecha, "%Y-%m-%d").date() if fecha else None
    except ValueError:
        fecha = ""
        fecha_param = None
    orden = request.args.get("orden", "recientes")
    ordenes = {
        "recientes": "p.fecha_solicitud DESC, p.id_pedido DESC",
        "antiguos": "p.fecha_solicitud ASC, p.id_pedido ASC",
    }
    if orden not in ordenes:
        orden = "recientes"
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT p.id_pedido, p.total, p.anticipo_requerido, p.saldo_requerido, p.equipo, p.modelo, p.descripcion, p.estado,
               p.solicita_factura, p.fecha_solicitud, p.fecha_actualizacion, p.anticipo_solicitado, p.anticipo_pagado,
             u.usuario, u.correo,
             pu.nombres, pu.apellidos,
               s.nombre AS servicio_nombre,
               f.id_factura, f.numero AS factura_numero, f.estado AS factura_estado,
               d.diagnostico, d.trabajo_realizado, d.repuestos, d.recomendaciones,
               p.fecha_entrega, (p.fecha_entrega + INTERVAL '3 months')::date AS garantia_fin,
               CURRENT_DATE <= (p.fecha_entrega + INTERVAL '3 months')::date AS garantia_vigente
        FROM pedidos p
        JOIN usuarios u ON u.id_usuario = p.id_usuario
         LEFT JOIN perfiles_usuario pu ON pu.id_usuario = u.id_usuario
        LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
        LEFT JOIN facturas f ON f.id_pedido = p.id_pedido
        LEFT JOIN detalle_servicio d ON d.id_pedido = p.id_pedido
        WHERE (CONCAT_WS(' ', pu.nombres, pu.apellidos) ILIKE %s
               OR u.usuario ILIKE %s OR u.correo ILIKE %s OR s.nombre ILIKE %s
               OR p.equipo ILIKE %s OR p.descripcion ILIKE %s OR p.id_pedido::text ILIKE %s)
          AND (%s = '' OR p.estado = %s)
          AND (%s::date IS NULL OR p.fecha_solicitud::date = %s::date)
          AND ("""
        + facturas_filtro[factura]
        + """)
        ORDER BY """
        + ordenes[orden],
        (f"%{q}%",) * 7 + (estado, estado, fecha_param, fecha_param),
    )
    pedidos = cursor.fetchall()
    for pedido in pedidos:
        pedido["pago"] = resumen_pago(cursor, pedido)
    cursor.close()
    conn.close()
    return render_template(
        "pedidos_admin.html",
        pedidos=pedidos,
        q=q,
        estado=estado,
        estados=estados,
        factura=factura,
        fecha=fecha,
        orden=orden,
        estado_form=PedidoEstadoForm(),
        cancelar_form=crear_cancelacion_form(True),
        anticipo_form=AnticipoForm(),
        emitir_form=EmitirFacturaForm(),
        equipo_form=EquipoPedidoForm(),
        tecnico_form=DetalleServicioForm(),
        observacion_form=ObservacionPedidoForm(),
        active="pedidos",
    )


@app.route("/auditoria")
@admin_required
def auditoria():
    """Consulta el historial de cambios registrado por los triggers PostgreSQL."""
    tabla = request.args.get("tabla", "").strip()
    operacion = request.args.get("operacion", "").strip().upper()
    fecha = request.args.get("fecha", "").strip()

    tablas_permitidas = {
        "usuarios",
        "perfiles_usuario",
        "servicios",
        "pedidos",
        "facturas",
        "clientes",
        "proveedores",
    }
    operaciones_permitidas = {"INSERT", "UPDATE", "DELETE"}

    condiciones = []
    parametros = []
    if tabla in tablas_permitidas:
        condiciones.append("tabla = %s")
        parametros.append(tabla)
    else:
        tabla = ""

    if operacion in operaciones_permitidas:
        condiciones.append("operacion = %s")
        parametros.append(operacion)
    else:
        operacion = ""

    if fecha:
        condiciones.append("fecha_hora::date = %s")
        parametros.append(fecha)

    consulta = """
        SELECT id_auditoria, fecha_hora, tabla, operacion, id_registro,
               usuario_bd, datos_anteriores, datos_nuevos
        FROM auditoria
    """
    if condiciones:
        consulta += " WHERE " + " AND ".join(condiciones)
    consulta += " ORDER BY fecha_hora DESC"

    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(consulta, tuple(parametros))
    registros = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "auditoria.html",
        registros=registros,
        tabla=tabla,
        operacion=operacion,
        fecha=fecha,
        active="auditoria",
    )


@app.route("/pedidos/<int:id>/detalle-servicio", methods=["POST"])
@admin_required
def guardar_detalle_servicio(id):
    form = DetalleServicioForm()
    if not form.validate_on_submit():
        flash(
            "No se guardó la información técnica. Revisa el formulario (máximo 10000 caracteres por campo).",
            "warning",
        )
        return redirect(url_for("pedidos_admin"))
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id_pedido FROM pedidos WHERE id_pedido=%s FOR SHARE", (id,)
            )
            if not cursor.fetchone():
                abort(404)
            cursor.execute(
                """INSERT INTO detalle_servicio
                   (id_pedido,diagnostico,trabajo_realizado,repuestos,recomendaciones,actualizado_por)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id_pedido) DO UPDATE SET
                       diagnostico=EXCLUDED.diagnostico, trabajo_realizado=EXCLUDED.trabajo_realizado,
                       repuestos=EXCLUDED.repuestos, recomendaciones=EXCLUDED.recomendaciones,
                       actualizado_por=EXCLUDED.actualizado_por, fecha_actualizacion=CURRENT_TIMESTAMP""",
                (
                    id,
                    form.diagnostico.data,
                    form.trabajo_realizado.data,
                    form.repuestos.data,
                    form.recomendaciones.data,
                    current_user.id,
                ),
            )
        conn.commit()
        flash("Expediente técnico actualizado y auditado.", "success")
    finally:
        conn.close()
    return redirect(url_for("pedidos_admin"))


@app.route("/pedidos/<int:id>/observaciones", methods=["POST"])
@admin_required
def agregar_observacion_pedido(id):
    form = ObservacionPedidoForm()
    if not form.validate_on_submit():
        flash("Escribe una observación de entre 1 y 2000 caracteres.", "warning")
        return redirect(url_for("pedidos_admin"))
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id_pedido FROM pedidos WHERE id_pedido=%s FOR SHARE", (id,)
            )
            if not cursor.fetchone():
                abort(404)
            cursor.execute(
                """INSERT INTO observaciones_pedidos (id_pedido,texto,id_usuario_actor,visible_cliente)
                   VALUES (%s,%s,%s,%s) RETURNING id_observacion""",
                (
                    id,
                    form.texto.data.strip(),
                    current_user.id,
                    form.visible_cliente.data,
                ),
            )
            ident = cursor.fetchone()[0]
            cursor.execute(
                """INSERT INTO auditoria (tabla,operacion,id_registro,datos_nuevos,usuario_bd)
                   SELECT 'observaciones_pedidos','INSERT',id_observacion::text,to_jsonb(o),CURRENT_USER
                   FROM observaciones_pedidos o WHERE id_observacion=%s""",
                (ident,),
            )
        conn.commit()
        flash("Observación añadida al seguimiento.", "success")
    finally:
        conn.close()
    return redirect(url_for("pedidos_admin"))


@app.route("/pedidos/<int:id>/equipo", methods=["GET", "POST"])
@admin_required
def corregir_equipo_pedido(id):
    """Corrección administrativa de datos; no cambia estado, propietario ni facturas."""
    form = EquipoPedidoForm()
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id_pedido, equipo, modelo, descripcion FROM pedidos WHERE id_pedido=%s FOR UPDATE",
                (id,),
            )
            pedido = cursor.fetchone()
            if not pedido:
                abort(404)
            if request.method == "GET":
                form.equipo.data = pedido["equipo"]
                form.modelo.data = pedido["modelo"]
                form.descripcion.data = pedido["descripcion"]
            if form.validate_on_submit():
                cursor.execute(
                    """UPDATE pedidos SET equipo=%s, modelo=%s, descripcion=%s, fecha_actualizacion=CURRENT_TIMESTAMP
                       WHERE id_pedido=%s""",
                    (
                        form.equipo.data,
                        (form.modelo.data or "").strip() or None,
                        (
                            (form.descripcion.data or "").strip()
                            if "descripcion" in request.form
                            else pedido["descripcion"]
                        ),
                        id,
                    ),
                )
                conn.commit()
                flash(
                    "Datos del equipo corregidos. Las facturas emitidas conservan sus datos históricos.",
                    "success",
                )
                return redirect(url_for("pedidos_admin"))
        return render_template(
            "corregir_equipo_pedido.html", form=form, pedido=pedido, active="pedidos"
        )
    finally:
        conn.close()


@app.route("/pedidos/<int:id>/estado", methods=["POST"])
@admin_required
def actualizar_estado_pedido(id):
    form = PedidoEstadoForm()
    if not form.validate_on_submit():
        flash("No se puede regresar a un estado anterior del pedido.", "warning")
        return redirect(url_for("pedidos_admin"))
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM pedidos WHERE id_pedido = %s FOR UPDATE", (id,)
            )
            pedido = cursor.fetchone()
            if not pedido:
                abort(404)
            actual = pedido["estado"]
            destino = form.estado.data
            if destino == actual:
                return redirect(url_for("pedidos_admin"))
            if destino not in TRANSICIONES_PEDIDO.get(actual, ()):
                flash(
                    "No se puede regresar a un estado anterior del pedido.", "warning"
                )
                return redirect(url_for("pedidos_admin"))
            pago = resumen_pago(cursor, pedido)
            if destino == "En reparación" and not pago["anticipo_confirmado"]:
                flash(
                    "Debes confirmar el anticipo o el pago completo antes de iniciar la reparación.",
                    "warning",
                )
                return redirect(url_for("pedidos_admin"))
            if destino == "Entregado" and not pago["pago_completo"]:
                flash("Debes confirmar el pago completo antes de entregar.", "warning")
                return redirect(url_for("pedidos_admin"))
            cursor.execute(
                "SELECT set_config('pcfix.usuario_actor', %s, TRUE)",
                (str(current_user.id),),
            )
            cursor.execute(
                """UPDATE pedidos SET estado = %s, fecha_actualizacion = CURRENT_TIMESTAMP,
                          observacion = %s
                   WHERE id_pedido = %s""",
                (destino, (form.observacion.data or "").strip() or None, id),
            )
        conn.commit()
    finally:
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
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Serializa emisiones y cambios de estado del mismo pedido.
            cursor.execute(
                """
                SELECT p.id_pedido, p.id_usuario, p.id_servicio, p.estado,
                       p.solicita_factura, p.equipo, p.modelo, p.subtotal, p.porcentaje_iva, p.valor_iva, p.total, p.anticipo_requerido, p.saldo_requerido, s.nombre AS servicio_nombre, s.precio
                FROM pedidos p
                LEFT JOIN servicios s ON s.id_servicio = p.id_servicio
                WHERE p.id_pedido = %s
                FOR UPDATE OF p
                """,
                (id,),
            )
            pedido = cursor.fetchone()
            if not pedido:
                abort(404)
            # Consulta independiente después del bloqueo: ve emisiones concurrentes.
            cursor.execute(
                "SELECT id_factura FROM facturas WHERE id_pedido = %s", (id,)
            )
            if cursor.fetchone():
                flash("Este pedido ya tiene una factura emitida.", "warning")
                return redirect(url_for("pedidos_admin"))
            if pedido["estado"] == "Cancelado":
                flash("No se puede facturar un pedido cancelado.", "warning")
                return redirect(url_for("pedidos_admin"))
            if not pedido["solicita_factura"]:
                flash("El cliente todavía no ha solicitado factura.", "warning")
                return redirect(url_for("pedidos_admin"))
            pago = resumen_pago(cursor, pedido)
            if not pago["pago_completo"]:
                flash(
                    "La factura final solo puede emitirse después de confirmar el pago total con IVA.",
                    "warning",
                )
                return redirect(url_for("pedidos_admin"))
            if pedido["servicio_nombre"] is None or pedido["precio"] is None:
                flash(
                    "El pedido no tiene un servicio con precio disponible para facturar.",
                    "warning",
                )
                return redirect(url_for("pedidos_admin"))

            if pedido["total"] is None:
                flash("El pedido no tiene un total de pago registrado.", "warning")
                return redirect(url_for("pedidos_admin"))
            valores = pedido
            estado_factura = "Pagada"
            numero = f"FAC-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{id}"
            cursor.execute(
                """
                INSERT INTO facturas (
                    numero, id_cliente, id_servicio, fecha, total, estado,
                    id_usuario, id_pedido, servicio_nombre, equipo_nombre, equipo_modelo, subtotal, porcentaje_iva, valor_iva
                )
                VALUES (%s, NULL, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_pedido) WHERE id_pedido IS NOT NULL DO NOTHING
                RETURNING id_factura
                """,
                (
                    numero,
                    pedido["id_servicio"],
                    valores["total"],
                    estado_factura,
                    pedido["id_usuario"],
                    pedido["id_pedido"],
                    pedido["servicio_nombre"],
                    pedido["equipo"],
                    pedido["modelo"] or "",
                    valores["subtotal"],
                    valores["porcentaje_iva"],
                    valores["valor_iva"],
                ),
            )
            emitida = cursor.fetchone()
        conn.commit()
        if emitida:
            flash(f"Factura {numero} emitida correctamente.", "success")
        else:
            flash("Este pedido ya tiene una factura emitida.", "warning")
    finally:
        conn.close()
    return redirect(url_for("pedidos_admin"))


@app.route("/mis-facturas")
@cliente_required
def mis_facturas():
    """Lista exclusivamente las facturas del cliente autenticado."""
    q = request.args.get("q", "").strip()
    patron = f"%{q}%"
    estados_permitidos = ("Pendiente", "Pagada")
    estado = request.args.get("estado", "")
    if estado not in estados_permitidos:
        estado = ""
    ordenes = {
        "recientes": "f.fecha DESC, f.id_factura DESC",
        "antiguas": "f.fecha ASC, f.id_factura ASC",
        "mayor_total": "f.total DESC, f.id_factura DESC",
        "menor_total": "f.total ASC, f.id_factura ASC",
        "numero": "f.numero ASC, f.id_factura ASC",
    }
    orden = request.args.get("orden", "recientes")
    if orden not in ordenes:
        orden = "recientes"
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Solo se concatena una cláusula constante de la lista permitida.
    cursor.execute(
        """
        SELECT f.id_factura, f.numero, f.fecha, f.total, f.estado,
               f.id_pedido, COALESCE(f.equipo_nombre, p.equipo) AS equipo,
               COALESCE(f.equipo_modelo, p.modelo) AS modelo, COALESCE(f.servicio_nombre, s.nombre, 'Servicio no disponible') AS servicio_nombre
        FROM facturas f
        LEFT JOIN pedidos p ON p.id_pedido = f.id_pedido
        LEFT JOIN servicios s ON s.id_servicio = f.id_servicio
        WHERE f.id_usuario = %s
        AND (f.numero ILIKE %s
             OR COALESCE(f.servicio_nombre, s.nombre, 'Servicio no disponible') ILIKE %s
             OR f.estado ILIKE %s OR COALESCE(f.equipo_nombre, p.equipo) ILIKE %s OR f.id_pedido::text ILIKE %s)
        AND (%s = '' OR f.estado = %s)
        ORDER BY """ + ordenes[orden],
        (current_user.id,) + (patron,) * 5 + (estado, estado),
    )
    facturas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        "mis_facturas.html",
        facturas=facturas,
        q=q,
        estado=estado,
        orden=orden,
        active="mis_facturas",
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
         SELECT f.id_factura, f.numero, f.fecha, f.total, f.estado, f.subtotal, f.porcentaje_iva, f.valor_iva,
               f.id_pedido, COALESCE(f.equipo_nombre, p.equipo) AS equipo,
               COALESCE(f.equipo_modelo, p.modelo) AS modelo,
             COALESCE((SELECT SUM(pg.monto) FROM pagos pg WHERE pg.id_pedido=f.id_pedido
                    AND pg.tipo_pago='anticipo' AND pg.estado='Confirmado'),0) AS anticipo_aplicado,
             COALESCE((SELECT SUM(pg.monto) FROM pagos pg WHERE pg.id_pedido=f.id_pedido
                    AND pg.tipo_pago IN ('saldo','total') AND pg.estado='Confirmado'),
                   CASE WHEN f.estado='Pagada' THEN f.total ELSE 0 END) AS saldo_pagado,
               u.usuario, u.correo,
               pu.nombres, pu.apellidos,
               COALESCE(f.servicio_nombre, s.nombre, 'Servicio no disponible') AS servicio_nombre
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
    for fila in cliente_data[1:]:
        fila[1] = Paragraph(escape(fila[1]), styles["Normal"])
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
    _, cliente_altura = cliente_tabla.wrapOn(documento, ancho, 200)
    cliente_y = 665 - cliente_altura
    cliente_tabla.drawOn(documento, 72, cliente_y)

    documento.setFont("Helvetica-Bold", 11)
    documento.drawString(72, cliente_y - 24, "DETALLE DEL SERVICIO")
    precio = (
        factura["subtotal"] if factura["subtotal"] is not None else factura["total"]
    )
    equipo_detalle = "Equipo: " + escape(factura["equipo"] or "No especificado")
    if factura["modelo"]:
        equipo_detalle += "<br/>Modelo: " + escape(factura["modelo"])
    detalle_data = [
        ["Servicio", "Equipo", "Cantidad", "Precio base"],
        [
            Paragraph(
                escape(factura["servicio_nombre"] or "Servicio no disponible"),
                styles["Normal"],
            ),
            Paragraph(equipo_detalle, styles["Normal"]),
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
    _, detalle_altura = detalle_tabla.wrapOn(documento, ancho, 200)
    detalle_y = cliente_y - 40 - detalle_altura
    detalle_tabla.drawOn(documento, 72, detalle_y)

    resumen_data = [
        [
            "Subtotal" if factura["subtotal"] is not None else "Importe histórico",
            f"${precio:.2f}",
        ]
    ]
    if factura["porcentaje_iva"] is not None:
        resumen_data.append(
            [
                "IVA ("
                + format(factura["porcentaje_iva"] * 100, ".2f").rstrip("0").rstrip(".")
                + " %)",
                f"${factura['valor_iva']:.2f}",
            ]
        )
    else:
        resumen_data.append(["IVA histórico", "No desglosado"])
    resumen_data.append(["TOTAL", f"${factura['total']:.2f}"])
    if factura["subtotal"] is not None:
        resumen_data += [
            ["Anticipo aplicado", f"${factura['anticipo_aplicado']:.2f}"],
            ["Saldo pagado", f"${factura['saldo_pagado']:.2f}"],
            ["Saldo pendiente", "$0.00"],
        ]
    estado_pdf = "PAGADO" if factura["estado"] == "Pagada" else factura["estado"]
    resumen_data.append(["Estado de pago", estado_pdf])
    resumen_tabla = Table(
        resumen_data, colWidths=[1.8 * inch, 1.2 * inch], hAlign="RIGHT"
    )
    resumen_tabla.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("FONTSIZE", (0, 2), (-1, 2), 13),
                ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#112248")),
                ("LINEABOVE", (0, 2), (-1, 2), 1, colors.HexColor("#d4af37")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    _, resumen_altura = resumen_tabla.wrapOn(documento, ancho, letter[1])
    resumen_y = detalle_y - 18 - resumen_altura
    if resumen_y < 90:
        documento.showPage()
        resumen_y = letter[1] - 72 - resumen_altura
    resumen_tabla.drawOn(documento, letter[0] - 72 - 3.0 * inch, resumen_y)

    garantia_nota = Paragraph(
        "<b>Garantía del servicio:</b><br/>"
        "El servicio realizado cuenta con una garantía de 3 meses, sujeta a los términos y condiciones de PC-Fix. "
        "La garantía cubre únicamente fallas relacionadas directamente con el trabajo realizado.<br/><br/>"
        "Consulta los términos y condiciones y la política de garantía de PC-Fix para conocer coberturas y exclusiones.",
        styles["Normal"],
    )
    _, nota_altura = garantia_nota.wrap(ancho, 150)
    nota_y = min(110, resumen_y - nota_altura - 24)
    if nota_y < 90:
        documento.showPage()
        nota_y = letter[1] - 72 - nota_altura
    garantia_nota.drawOn(documento, 72, nota_y)
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


@app.route("/terminos")
def terminos():
    return render_template("condiciones.html", garantia=False)


@app.route("/garantia")
def garantia():
    return render_template("condiciones.html", garantia=True)


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
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "todos")
    estados = {
        "todos": "s.archivado = FALSE",
        "activos": "s.activo = TRUE AND s.archivado = FALSE",
        "pausados": "s.activo = FALSE AND s.archivado = FALSE",
        "archivados": "s.archivado = TRUE",
    }
    if estado not in estados:
        estado = "todos"
    ordenes = {
        "nombre": "s.nombre ASC, s.id_servicio ASC",
        "menor_precio": "s.precio ASC, s.id_servicio ASC",
        "mayor_precio": "s.precio DESC, s.id_servicio DESC",
        "recientes": "s.id_servicio DESC",
    }
    orden = request.args.get("orden", "nombre")
    if orden not in ordenes:
        orden = "nombre"
    proveedor = request.args.get("proveedor", type=int)
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id_proveedor, empresa FROM proveedores ORDER BY empresa"
            )
            proveedores_filtro = cursor.fetchall()
            if proveedor not in {r["id_proveedor"] for r in proveedores_filtro}:
                proveedor = None
            condicion = (
                estados[estado] if current_user.rol == "admin" else estados["activos"]
            )
            if current_user.rol != "admin":
                estado = "activos"
            cursor.execute(
                """SELECT s.*, p.empresa AS proveedor_empresa
                   FROM servicios s LEFT JOIN proveedores p ON s.id_proveedor = p.id_proveedor
                   WHERE ("""
                + condicion
                + """)
                     AND (%s IS NULL OR s.id_proveedor = %s)
                     AND (s.nombre ILIKE %s OR s.descripcion ILIKE %s
                          OR p.empresa ILIKE %s OR s.duracion ILIKE %s)
                   ORDER BY """
                + ordenes[orden],
                (proveedor, proveedor) + (f"%{q}%",) * 4,
            )
            servicios_db = cursor.fetchall()
    finally:
        conn.close()
    return render_template(
        "servicios.html",
        active="servicios",
        servicios=servicios_db,
        q=q,
        estado=estado,
        proveedor=proveedor,
        orden=orden,
        proveedores_filtro=proveedores_filtro,
        eliminar_form=EliminarForm(),
    )


def nombre_servicio_duplicado(cursor, nombre, excluir=None):
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(LOWER(BTRIM(%s))))", (nombre,)
    )
    cursor.execute(
        """SELECT archivado FROM servicios
           WHERE LOWER(BTRIM(nombre)) = LOWER(BTRIM(%s))
             AND (%s IS NULL OR id_servicio <> %s)
           ORDER BY archivado ASC LIMIT 1""",
        (nombre, excluir, excluir),
    )
    fila = cursor.fetchone()
    if fila is None:
        return None
    archivado = fila["archivado"] if isinstance(fila, dict) else fila[0]
    return (
        "Ya existe un servicio archivado con ese nombre. Puedes restaurarlo en lugar de crear uno nuevo."
        if archivado
        else "Ya existe un servicio con ese nombre."
    )


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
        form.nombre.data = form.nombre.data.strip()
        duplicado = nombre_servicio_duplicado(cursor, form.nombre.data, None)
        if duplicado:
            conn.rollback()
            cursor.close()
            conn.close()
            form.nombre.errors.append(duplicado)
            return render_template(
                "formulario_producto.html",
                imagen_form=ImagenServicioForm(),
                active="servicios",
                form=form,
                titulo="Nuevo Servicio",
            )
        try:
            imagen, id_imagen = resolver_imagen(cursor, form.imagen.data)
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            form.imagen.errors.append(str(error))
            return render_template(
                "formulario_producto.html",
                imagen_form=ImagenServicioForm(),
                form=form,
                titulo="Nuevo Servicio",
                active="servicios",
            )
        cursor.execute(
            """
            INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor, requiere_entrega_equipo, id_imagen, duracion_cantidad, duracion_unidad)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                form.nombre.data,
                form.descripcion.data,
                form.precio.data,
                form.duracion.data,
                imagen,
                id_prov,
                form.requiere_entrega_equipo.data == "si",
                id_imagen,
                form.duracion_cantidad.data,
                form.duracion_unidad.data,
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
        imagen_form=ImagenServicioForm(),
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
    if servicio["id_proveedor"] and servicio["id_proveedor"] not in dict(
        form.id_proveedor.choices
    ):
        cursor.execute(
            "SELECT empresa FROM proveedores WHERE id_proveedor = %s",
            (servicio["id_proveedor"],),
        )
        proveedor_actual = cursor.fetchone()
        if proveedor_actual:
            form.id_proveedor.choices.append(
                (
                    servicio["id_proveedor"],
                    proveedor_actual["empresa"] + " (Inactivo, asignado)",
                )
            )
    form.imagen.choices = obtener_imagenes_servicios()

    if request.method == "GET":
        form.requiere_entrega_equipo.data = (
            "si" if servicio["requiere_entrega_equipo"] else "no"
        )
        form.nombre.data = servicio["nombre"]
        form.descripcion.data = servicio["descripcion"]
        form.precio.data = servicio["precio"]
        form.duracion.data = servicio["duracion"]
        form.duracion_cantidad.data, form.duracion_unidad.data = separar_duracion(
            servicio["duracion"]
        )
        form.imagen.data = (
            f"bd:{servicio['id_imagen']}"
            if servicio["id_imagen"]
            else servicio["imagen"]
        )
        form.id_proveedor.data = (
            servicio["id_proveedor"] if servicio["id_proveedor"] else 0
        )

    if form.validate_on_submit():
        id_prov = (
            form.id_proveedor.data
            if form.id_proveedor.data and form.id_proveedor.data != 0
            else None
        )
        form.nombre.data = form.nombre.data.strip()
        duplicado = nombre_servicio_duplicado(cursor, form.nombre.data, id)
        if duplicado:
            conn.rollback()
            cursor.close()
            conn.close()
            form.nombre.errors.append(duplicado)
            return render_template(
                "formulario_producto.html",
                imagen_form=ImagenServicioForm(),
                active="servicios",
                form=form,
                titulo="Editar Servicio",
            )
        try:
            imagen, id_imagen = resolver_imagen(
                cursor, form.imagen.data, servicio["imagen"]
            )
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            form.imagen.errors.append(str(error))
            return render_template(
                "formulario_producto.html",
                imagen_form=ImagenServicioForm(),
                form=form,
                titulo="Editar Servicio",
                active="servicios",
            )
        cursor.execute(
            """
            UPDATE servicios
            SET nombre = %s, descripcion = %s, precio = %s, duracion = %s, imagen = %s, id_proveedor = %s, requiere_entrega_equipo = %s, id_imagen = %s, duracion_cantidad = %s, duracion_unidad = %s
            WHERE id_servicio = %s
        """,
            (
                form.nombre.data,
                form.descripcion.data,
                form.precio.data,
                form.duracion.data,
                imagen,
                id_prov,
                form.requiere_entrega_equipo.data == "si",
                id_imagen,
                form.duracion_cantidad.data,
                form.duracion_unidad.data,
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
        imagen_form=ImagenServicioForm(),
        active="servicios",
        form=form,
        titulo="Editar Servicio",
    )


def cambiar_activo(tabla, clave, id, activo):
    """Los nombres SQL son constantes internas; los valores son parámetros."""
    form = EliminarForm()
    if not form.validate_on_submit():
        abort(400)
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE {tabla} SET activo = %s WHERE {clave} = %s"
                + (" AND archivado = FALSE" if tabla == "servicios" else ""),
                (activo, id),
            )
            if cursor.rowcount == 0:
                abort(404)
        conn.commit()
    finally:
        conn.close()
    if tabla == "servicios":
        flash("Servicio reactivado." if activo else "Servicio en pausa.", "success")
    else:
        flash("Registro activado." if activo else "Registro desactivado.", "success")
    return redirect(url_for(tabla))


@app.route("/servicios/eliminar/<int:id>", methods=["POST"])
@app.route("/servicios/desactivar/<int:id>", methods=["POST"])
@app.route("/productos/eliminar/<int:id>", methods=["POST"])
@admin_required
def eliminar_servicio(id):
    return cambiar_activo("servicios", "id_servicio", id, False)


@app.route("/servicios/activar/<int:id>", methods=["POST"])
@admin_required
def activar_servicio(id):
    return cambiar_activo("servicios", "id_servicio", id, True)


def cambiar_archivado_servicio(id, archivado):
    form = EliminarForm()
    if not form.validate_on_submit():
        abort(400)
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE servicios SET archivado = %s, activo = FALSE
                   WHERE id_servicio = %s""",
                (archivado, id),
            )
            if cursor.rowcount == 0:
                abort(404)
        conn.commit()
    finally:
        conn.close()
    flash(
        (
            "Servicio archivado. Permanece en el historial."
            if archivado
            else "Servicio restaurado en pausa. Puedes reactivarlo cuando esté disponible."
        ),
        "success",
    )
    return redirect(url_for("servicios"))


@app.route("/servicios/<int:id>/archivar", methods=["POST"])
@admin_required
def archivar_servicio(id):
    return cambiar_archivado_servicio(id, True)


@app.route("/servicios/<int:id>/restaurar", methods=["POST"])
@admin_required
def restaurar_servicio(id):
    return cambiar_archivado_servicio(id, False)


# ===== Módulos Complementarios (Clientes, Proveedores, Facturación) =====


@app.route("/clientes")
@admin_required
def clientes():
    q = request.args.get("q", "").strip()
    estados = ["En revisión", "En reparación", "Entregado", "Pendiente"]
    estado = request.args.get("estado", "")
    if estado not in estados:
        estado = ""
    registro = request.args.get("registro", "")
    if registro not in ("activos", "inactivos"):
        registro = ""
    activo = {"activos": True, "inactivos": False}.get(registro)
    ordenes = {
        "nombre": "nombre ASC, id_cliente ASC",
        "recientes": "id_cliente DESC",
        "antiguos": "id_cliente ASC",
    }
    orden = request.args.get("orden", "nombre")
    if orden not in ordenes:
        orden = "nombre"
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT id_cliente, nombre, cedula, telefono, correo, equipo, modelo, estado, activo
                   FROM clientes
                   WHERE (nombre ILIKE %s OR cedula ILIKE %s OR telefono ILIKE %s
                          OR correo ILIKE %s OR equipo ILIKE %s)
                     AND (%s = '' OR estado = %s)
                     AND (%s IS NULL OR activo = %s)
                   ORDER BY """
                + ordenes[orden],
                (f"%{q}%",) * 5 + (estado, estado, activo, activo),
            )
            clientes_db = cursor.fetchall()
    finally:
        conn.close()
    return render_template(
        "clientes.html",
        active="clientes",
        clientes=clientes_db,
        q=q,
        estado=estado,
        estados=estados,
        registro=registro,
        orden=orden,
        eliminar_form=EliminarForm(),
    )


@app.route("/clientes/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO clientes (nombre, cedula, telefono, correo, equipo, modelo, estado)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                form.nombre.data,
                form.cedula.data,
                form.telefono.data,
                normalizar_correo(form.correo.data),
                form.equipo.data,
                (form.modelo.data or "").strip() or None,
                form.estado.data,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Cliente registrado con éxito.", "success")
        return redirect(url_for("clientes"))
    return render_template(
        "formulario_cliente.html", active="clientes", form=form, titulo="Nuevo Cliente"
    )


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_cliente(id):
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT id_cliente, nombre, cedula, telefono, correo, equipo, modelo, estado FROM clientes WHERE id_cliente = %s",
        (id,),
    )
    cliente = cursor.fetchone()
    if not cliente:
        cursor.close()
        conn.close()
        abort(404)
    form = ClienteForm()
    if request.method == "GET":
        form.nombre.data = cliente["nombre"]
        form.cedula.data = cliente["cedula"]
        form.telefono.data = cliente["telefono"]
        form.correo.data = cliente["correo"]
        form.equipo.data = cliente["equipo"]
        form.modelo.data = cliente["modelo"]
        form.estado.data = cliente["estado"]
    elif form.validate_on_submit():
        cursor.execute(
            """UPDATE clientes SET nombre = %s, cedula = %s, telefono = %s,
               correo = %s, equipo = %s, modelo = %s, estado = %s WHERE id_cliente = %s""",
            (
                form.nombre.data,
                form.cedula.data,
                form.telefono.data,
                normalizar_correo(form.correo.data),
                form.equipo.data,
                (form.modelo.data or "").strip() or None,
                form.estado.data,
                id,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Cliente actualizado con éxito.", "success")
        return redirect(url_for("clientes"))
    cursor.close()
    conn.close()
    return render_template(
        "formulario_cliente.html", active="clientes", form=form, titulo="Editar Cliente"
    )


@app.route("/clientes/eliminar/<int:id>", methods=["POST"])
@app.route("/clientes/desactivar/<int:id>", methods=["POST"])
@admin_required
def eliminar_cliente(id):
    return cambiar_activo("clientes", "id_cliente", id, False)


@app.route("/clientes/activar/<int:id>", methods=["POST"])
@admin_required
def activar_cliente(id):
    return cambiar_activo("clientes", "id_cliente", id, True)


@app.route("/proveedores")
@admin_required
def proveedores():
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT id_proveedor, empresa, contacto, telefono, categoria, activo FROM proveedores ORDER BY id_proveedor"
    )
    proveedores = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        "proveedores.html",
        active="proveedores",
        proveedores=proveedores,
        eliminar_form=EliminarForm(),
    )


@app.route("/proveedores/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_proveedor():
    form = ProveedorForm()
    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO proveedores (empresa, contacto, telefono, categoria)
               VALUES (%s, %s, %s, %s)""",
            (
                form.empresa.data,
                form.contacto.data,
                form.telefono.data,
                form.categoria.data,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Proveedor registrado con éxito.", "success")
        return redirect(url_for("proveedores"))
    return render_template(
        "formulario_proveedor.html",
        active="proveedores",
        form=form,
        titulo="Nuevo Proveedor",
    )


@app.route("/proveedores/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_proveedor(id):
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT id_proveedor, empresa, contacto, telefono, categoria FROM proveedores WHERE id_proveedor = %s",
        (id,),
    )
    proveedor = cursor.fetchone()
    if not proveedor:
        cursor.close()
        conn.close()
        abort(404)
    form = ProveedorForm()
    if request.method == "GET":
        form.empresa.data = proveedor["empresa"]
        form.contacto.data = proveedor["contacto"]
        form.telefono.data = proveedor["telefono"]
        form.categoria.data = proveedor["categoria"]
    elif form.validate_on_submit():
        cursor.execute(
            """UPDATE proveedores SET empresa = %s, contacto = %s,
               telefono = %s, categoria = %s WHERE id_proveedor = %s""",
            (
                form.empresa.data,
                form.contacto.data,
                form.telefono.data,
                form.categoria.data,
                id,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Proveedor actualizado con éxito.", "success")
        return redirect(url_for("proveedores"))
    cursor.close()
    conn.close()
    return render_template(
        "formulario_proveedor.html",
        active="proveedores",
        form=form,
        titulo="Editar Proveedor",
    )


@app.route("/proveedores/eliminar/<int:id>", methods=["POST"])
@app.route("/proveedores/desactivar/<int:id>", methods=["POST"])
@admin_required
def eliminar_proveedor(id):
    return cambiar_activo("proveedores", "id_proveedor", id, False)


@app.route("/proveedores/activar/<int:id>", methods=["POST"])
@admin_required
def activar_proveedor(id):
    return cambiar_activo("proveedores", "id_proveedor", id, True)


@app.route("/facturacion")
@admin_required
def facturacion():
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""SELECT f.numero,
                  COALESCE(c.nombre, NULLIF(CONCAT_WS(' ', pu.nombres, pu.apellidos), ''), u.usuario, u.correo, 'Sin cliente') AS cliente,
                  COALESCE(f.servicio_nombre, s.nombre, 'Servicio no disponible') AS servicio, f.fecha, f.total, f.estado,
                  f.equipo_nombre AS equipo, f.equipo_modelo AS modelo
           FROM facturas f
           LEFT JOIN clientes c ON c.id_cliente = f.id_cliente
           LEFT JOIN servicios s ON s.id_servicio = f.id_servicio
           LEFT JOIN usuarios u ON u.id_usuario = f.id_usuario
           LEFT JOIN perfiles_usuario pu ON pu.id_usuario = u.id_usuario
           ORDER BY f.fecha DESC, f.id_factura DESC""")
    facturas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("facturacion.html", active="facturacion", facturas=facturas)


@app.route("/facturacion/nuevo", methods=["GET", "POST"])
@admin_required
def nueva_factura():
    """Compatibilidad con enlaces antiguos: no crea facturas manuales."""
    flash("Las facturas se emiten desde pedidos entregados.", "info")
    return redirect(url_for("pedidos_admin"))


registrar_biblioteca(app, admin_required, lambda: obtener_conexion())
registrar_rutas_pagos(app, admin_required, cliente_required, lambda: obtener_conexion())


if __name__ == "__main__":
    app.run(debug=True, host="localhost")
