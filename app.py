from flask import Flask, render_template, request, redirect, url_for, flash

# Formularios utilizados por los módulos del sistema.
# LoginForm y UsuarioForm se incorporan para la autenticación.
from forms import (
    ProductoForm,
    ClienteForm,
    ProveedorForm,
    FacturacionForm,
    LoginForm,
    UsuarioForm,
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

# Modelo de usuario compatible con Flask-Login.
from models import Usuario

import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "mi_secreto_super_seguro_123"
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
        SELECT id_usuario, usuario, password
        FROM usuarios
        WHERE id_usuario = %s
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

    if form.validate_on_submit():

        conn = obtener_conexion()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Comprobar si el nombre de usuario ya existe.
        # Esto evita registros duplicados además de la
        # restricción UNIQUE definida en PostgreSQL.
        cursor.execute(
            """
            SELECT id_usuario
            FROM usuarios
            WHERE usuario = %s
            """,
            (form.usuario.data,),
        )

        usuario_existente = cursor.fetchone()

        if usuario_existente:
            cursor.close()
            conn.close()

            flash("Ese nombre de usuario ya está registrado.", "danger")

            return render_template("registro.html", form=form, active="registro")

        # La contraseña escrita por el usuario se transforma
        # en un hash seguro antes de almacenarse.
        #
        # Por ejemplo:
        # PcFix2026  ->  scrypt:32768:8:1$...
        #
        # La contraseña original NO se guarda en PostgreSQL.
        password_hash = generate_password_hash(form.password.data)

        # Registro mediante consulta parametrizada.
        # Los parámetros %s evitan concatenar directamente
        # los valores recibidos desde el formulario.
        cursor.execute(
            """
            INSERT INTO usuarios (usuario, password)
            VALUES (%s, %s)
            """,
            (form.usuario.data, password_hash),
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash(
            "Usuario registrado correctamente. " "Ahora puedes iniciar sesión.",
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

        # Buscar únicamente al usuario indicado.
        cursor.execute(
            """
            SELECT id_usuario, usuario, password
            FROM usuarios
            WHERE usuario = %s
            """,
            (form.usuario.data,),
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
        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html", form=form, active="login")


@app.route("/dashboard")
@login_required
def dashboard():
    """
    Panel privado disponible únicamente para
    usuarios que hayan iniciado sesión.
    """

    return render_template("dashboard.html", active="dashboard")


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
@login_required
def nuevo_servicio():
    """Registrar un nuevo registro mediante INSERT INTO parametrizado."""
    form = ProductoForm()
    form.id_proveedor.choices = obtener_opciones_proveedores()

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
@login_required
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
@login_required
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
@login_required
def clientes():
    return render_template("clientes.html", active="clientes", clientes=CLIENTES)


@app.route("/clientes/nuevo", methods=["GET", "POST"])
@login_required
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
@login_required
def proveedores():
    return render_template(
        "proveedores.html", active="proveedores", proveedores=PROVEEDORES
    )


@app.route("/proveedores/nuevo", methods=["GET", "POST"])
@login_required
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
@login_required
def facturacion():
    return render_template("facturacion.html", active="facturacion", facturas=FACTURAS)


@app.route("/facturacion/nuevo", methods=["GET", "POST"])
@login_required
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

