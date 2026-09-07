from flask import Flask, render_template, request, redirect, url_for
from forms import ProductoForm, ClienteForm, ProveedorForm, FacturacionForm
import sqlite3
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mi_secreto_super_seguro_123'
NOMBRE_EMPRESA = "PC-Fix" #Variable visible
TIPOS_ASISTENCIA = [            #tipos de mantenimiento
    "Mantenimiento Preventivo",
    "Mantenimiento Correctivo",
    "Instalación de Software"
]
# ===== Datos de ejemplo (sin base de datos en esta etapa) =====

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'pcfix.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Crear tabla de productos/servicios
    conn.execute('''
        CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            precio REAL NOT NULL,
            duracion TEXT NOT NULL,
            imagen TEXT NOT NULL
        )
    ''')
    
    # Verificar si está vacía para insertar datos iniciales
    cursor = conn.execute('SELECT COUNT(*) FROM servicios')
    count = cursor.fetchone()[0]
    
    if count == 0:
        initial_data = [
            ("Mantenimiento Preventivo", "Limpieza interna profunda, cambio de pasta térmica de alta calidad y revisión exhaustiva de componentes.", 25.00, "1 hora", "servicio-1.jpg"),
            ("Mantenimiento Correctivo", "Diagnóstico preciso, reparación a nivel de placa y reemplazo de hardware dañado.", 40.00, "2 horas", "servicio-2.jpg"),
            ("Optimización y Limpieza", "Aceleramos el rendimiento de tu sistema operativo y eliminamos virus o malware.", 20.00, "45 minutos", "servicio-3.jpg"),
            ("Instalación de Software", "Instalación desde cero y actualización de sistemas operativos y programas esenciales.", 15.00, "30 minutos", "servicio-4.jpg"),
            ("Formateo e Instalación de Windows", "Formateo seguro del disco, instalación de Windows y configuración de controladores.", 30.00, "1.5 horas", "servicio-4.jpg"),
            ("Recuperación de Datos", "Recuperación de información vital desde discos dañados, USB o tarjetas de memoria.", 60.00, "Variable", "servicio-1.jpg")
        ]
        conn.executemany('INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen) VALUES (?, ?, ?, ?, ?)', initial_data)
        
    conn.commit()
    conn.close()

init_db()

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

# ===== Rutas =====

@app.route("/")
def index():
    return render_template("index.html", active="inicio", nombre_empresa=NOMBRE_EMPRESA, tipos_asistencia=TIPOS_ASISTENCIA)


@app.route("/conocenos")
def conocenos():
    return render_template("conocenos.html", active="conocenos")


@app.route("/servicios")
def servicios():
    conn = get_db_connection()
    servicios_db = conn.execute('SELECT * FROM servicios').fetchall()
    conn.close()
    return render_template("servicios.html", active="servicios", servicios=servicios_db)

@app.route("/servicios/nuevo", methods=['GET', 'POST'])
def nuevo_servicio():
    form = ProductoForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        conn.execute('INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen) VALUES (?, ?, ?, ?, ?)',
                     (form.nombre.data, form.descripcion.data, form.precio.data, form.duracion.data, form.imagen.data))
        conn.commit()
        conn.close()
        return redirect(url_for('servicios'))
    return render_template("formulario_producto.html", active="servicios", form=form, titulo="Nuevo Servicio")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html", active="contacto")


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
        return redirect(url_for('facturacion'))
    return render_template("formulario_facturacion.html", active="facturacion", form=form, titulo="Nueva Factura")


if __name__ == "__main__":
    app.run(debug=True)