from flask import Flask, render_template, request, redirect, url_for, flash
from forms import ProductoForm, ClienteForm, ProveedorForm, FacturacionForm
from conexion.conexion import obtener_conexion, inicializar_base_datos
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mi_secreto_super_seguro_123'
NOMBRE_EMPRESA = "PC-Fix"
TIPOS_ASISTENCIA = [
    "Mantenimiento Preventivo",
    "Mantenimiento Correctivo",
    "Instalación de Software"
]

# Inicializar PostgreSQL y cargar sql/esquema.sql
try:
    inicializar_base_datos()
except Exception as err:
    print(f"[AVISO INICIO] Error al inicializar base de datos: {err}")

# ===== Datos de referencia en memoria para módulos complementarios =====
CLIENTES = [
    {"nombre": "Ana Torres", "telefono": "0991234567", "equipo": "Laptop HP Pavilion", "estado": "En revisión"},
    {"nombre": "Luis Mendoza", "telefono": "0987654321", "equipo": "PC de escritorio", "estado": "Entregado"},
    {"nombre": "Karen Salazar", "telefono": "0971122334", "equipo": "MacBook Air", "estado": "En reparación"},
    {"nombre": "Diego Núñez", "telefono": "0965544332", "equipo": "Laptop Lenovo IdeaPad", "estado": "Pendiente"},
]

PROVEEDORES = [
    {"empresa": "TecnoRepuestos S.A.", "contacto": "Ing. Marco Ruiz", "telefono": "022456789", "categoria": "Placas y componentes"},
    {"empresa": "Almacenes Comercial", "contacto": "Sra. Rosa Vega", "telefono": "022998877", "categoria": "Pantallas y baterías"},
    {"empresa": "PC Parts Ecuador", "contacto": "Sr. Pablo Andrade", "telefono": "0987001122", "categoria": "Memorias RAM y SSD"},
]

FACTURAS = [
    {"numero": "FAC-001", "cliente": "Ana Torres", "servicio": "Mantenimiento Preventivo", "fecha": "2026-08-10", "total": 25.00, "estado": "Pagada"},
    {"numero": "FAC-002", "cliente": "Luis Mendoza", "servicio": "Instalación de Software", "fecha": "2026-08-11", "total": 15.00, "estado": "Pagada"},
    {"numero": "FAC-003", "cliente": "Karen Salazar", "servicio": "Mantenimiento Correctivo", "fecha": "2026-08-14", "total": 40.00, "estado": "Pendiente"},
    {"numero": "FAC-004", "cliente": "Diego Núñez", "servicio": "Formateo e Instalación de Windows", "fecha": "2026-08-15", "total": 30.00, "estado": "Pendiente"},
]

def obtener_opciones_proveedores():
    """Recupera la lista de proveedores desde PostgreSQL para poblar el selector del formulario."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id_proveedor, empresa FROM proveedores ORDER BY empresa ASC")
        proveedores = cursor.fetchall()
        cursor.close()
        conn.close()
        opciones = [(0, '-- Sin proveedor asignado --')]
        for p in proveedores:
            opciones.append((p['id_proveedor'], p['empresa']))
        return opciones
    except Exception as e:
        print(f"[ERROR PROVEEDORES] Error al obtener proveedores: {e}")
        return [(0, '-- Sin proveedor asignado --')]

# ===== Rutas Principales =====

@app.route("/")
def index():
    return render_template("index.html", active="inicio", nombre_empresa=NOMBRE_EMPRESA, tipos_asistencia=TIPOS_ASISTENCIA)


@app.route("/conocenos")
def conocenos():
    return render_template("conocenos.html", active="conocenos")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html", active="contacto")


# ===== Módulo de Servicios / Productos (CRUD Completo en PostgreSQL) =====

@app.route("/servicios")
@app.route("/productos")
def servicios():
    """Listar registros mediante SELECT y JOIN con PostgreSQL."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Consulta relacionada entre servicios y proveedores con JOIN
    cursor.execute('''
        SELECT s.id_servicio, s.nombre, s.descripcion, s.precio, s.duracion, s.imagen, s.id_proveedor,
               p.empresa AS proveedor_empresa
        FROM servicios s
        LEFT JOIN proveedores p ON s.id_proveedor = p.id_proveedor
        ORDER BY s.id_servicio ASC
    ''')
    servicios_db = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("servicios.html", active="servicios", servicios=servicios_db)


@app.route("/servicios/nuevo", methods=['GET', 'POST'])
@app.route("/productos/nuevo", methods=['GET', 'POST'])
def nuevo_servicio():
    """Registrar un nuevo registro mediante INSERT INTO parametrizado."""
    form = ProductoForm()
    form.id_proveedor.choices = obtener_opciones_proveedores()
    
    if form.validate_on_submit():
        id_prov = form.id_proveedor.data if form.id_proveedor.data and form.id_proveedor.data != 0 else None
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (form.nombre.data, form.descripcion.data, form.precio.data, form.duracion.data, form.imagen.data, id_prov))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Servicio '{form.nombre.data}' registrado exitosamente en PostgreSQL.", "success")
        return redirect(url_for('servicios'))
        
    return render_template("formulario_producto.html", active="servicios", form=form, titulo="Nuevo Servicio")


@app.route("/servicios/editar/<int:id>", methods=['GET', 'POST'])
@app.route("/productos/editar/<int:id>", methods=['GET', 'POST'])
def editar_servicio(id):
    """Modificar un registro existente utilizando WHERE y UPDATE parametrizado."""
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM servicios WHERE id_servicio = %s', (id,))
    servicio = cursor.fetchone()
    
    if not servicio:
        cursor.close()
        conn.close()
        flash("El servicio que intentas editar no existe.", "danger")
        return redirect(url_for('servicios'))
        
    form = ProductoForm()
    form.id_proveedor.choices = obtener_opciones_proveedores()
    
    if request.method == 'GET':
        form.nombre.data = servicio['nombre']
        form.descripcion.data = servicio['descripcion']
        form.precio.data = float(servicio['precio'])
        form.duracion.data = servicio['duracion']
        form.imagen.data = servicio['imagen']
        form.id_proveedor.data = servicio['id_proveedor'] if servicio['id_proveedor'] else 0
        
    if form.validate_on_submit():
        id_prov = form.id_proveedor.data if form.id_proveedor.data and form.id_proveedor.data != 0 else None
        cursor.execute('''
            UPDATE servicios
            SET nombre = %s, descripcion = %s, precio = %s, duracion = %s, imagen = %s, id_proveedor = %s
            WHERE id_servicio = %s
        ''', (form.nombre.data, form.descripcion.data, form.precio.data, form.duracion.data, form.imagen.data, id_prov, id))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Servicio '{form.nombre.data}' actualizado correctamente en PostgreSQL.", "info")
        return redirect(url_for('servicios'))
        
    cursor.close()
    conn.close()
    return render_template("formulario_producto.html", active="servicios", form=form, titulo="Editar Servicio")


@app.route("/servicios/eliminar/<int:id>", methods=['POST'])
@app.route("/productos/eliminar/<int:id>", methods=['POST'])
def eliminar_servicio(id):
    """Eliminar únicamente el registro seleccionado utilizando DELETE FROM ... WHERE."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM servicios WHERE id_servicio = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Servicio eliminado permanentemente de la base de datos.", "warning")
    return redirect(url_for('servicios'))


# ===== Módulos Complementarios (Clientes, Proveedores, Facturación) =====

@app.route("/clientes")
def clientes():
    return render_template("clientes.html", active="clientes", clientes=CLIENTES)

@app.route("/clientes/nuevo", methods=['GET', 'POST'])
def nuevo_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        nuevo_item = {
            "nombre": form.nombre.data,
            "telefono": form.telefono.data,
            "equipo": form.equipo.data,
            "estado": form.estado.data
        }
        CLIENTES.append(nuevo_item)
        flash("Cliente registrado con éxito.", "success")
        return redirect(url_for('clientes'))
    return render_template("formulario_cliente.html", active="clientes", form=form, titulo="Nuevo Cliente")


@app.route("/proveedores")
def proveedores():
    return render_template("proveedores.html", active="proveedores", proveedores=PROVEEDORES)

@app.route("/proveedores/nuevo", methods=['GET', 'POST'])
def nuevo_proveedor():
    form = ProveedorForm()
    if form.validate_on_submit():
        nuevo_item = {
            "empresa": form.empresa.data,
            "contacto": form.contacto.data,
            "telefono": form.telefono.data,
            "categoria": form.categoria.data
        }
        PROVEEDORES.append(nuevo_item)
        flash("Proveedor registrado con éxito.", "success")
        return redirect(url_for('proveedores'))
    return render_template("formulario_proveedor.html", active="proveedores", form=form, titulo="Nuevo Proveedor")


@app.route("/facturacion")
def facturacion():
    return render_template("facturacion.html", active="facturacion", facturas=FACTURAS)

@app.route("/facturacion/nuevo", methods=['GET', 'POST'])
def nueva_factura():
    form = FacturacionForm()
    if form.validate_on_submit():
        nuevo_item = {
            "numero": form.numero.data,
            "cliente": form.cliente.data,
            "servicio": form.servicio.data,
            "fecha": form.fecha.data.strftime('%Y-%m-%d'),
            "total": form.total.data,
            "estado": form.estado.data
        }
        FACTURAS.append(nuevo_item)
        flash("Factura registrada con éxito.", "success")
        return redirect(url_for('facturacion'))
    return render_template("formulario_facturacion.html", active="facturacion", form=form, titulo="Nueva Factura")


if __name__ == "__main__":
    app.run(debug=True)