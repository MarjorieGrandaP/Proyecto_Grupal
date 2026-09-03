from flask import Flask, render_template, request, redirect, url_for
from forms import ProductoForm, ClienteForm, ProveedorForm, FacturacionForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mi_secreto_super_seguro_123'
NOMBRE_EMPRESA = "PC-Fix" #Variable visible
TIPOS_ASISTENCIA = [            #tipos de mantenimiento
    "Mantenimiento Preventivo",
    "Mantenimiento Correctivo",
    "Instalación de Software"
]
# ===== Datos de ejemplo (sin base de datos en esta etapa) =====

SERVICIOS = [
    {
        "nombre": "Mantenimiento Preventivo",
        "descripcion": "Limpieza interna profunda, cambio de pasta térmica de alta calidad y revisión exhaustiva de componentes.",
        "precio": 25.00,
        "duracion": "1 hora",
        "imagen": "servicio-1.jpg",
    },
    {
        "nombre": "Mantenimiento Correctivo",
        "descripcion": "Diagnóstico preciso, reparación a nivel de placa y reemplazo de hardware dañado.",
        "precio": 40.00,
        "duracion": "2 horas",
        "imagen": "servicio-2.jpg",
    },
    {
        "nombre": "Optimización y Limpieza",
        "descripcion": "Aceleramos el rendimiento de tu sistema operativo y eliminamos virus o malware.",
        "precio": 20.00,
        "duracion": "45 minutos",
        "imagen": "servicio-3.jpg",
    },
    {
        "nombre": "Instalación de Software",
        "descripcion": "Instalación desde cero y actualización de sistemas operativos y programas esenciales.",
        "precio": 15.00,
        "duracion": "30 minutos",
        "imagen": "servicio-4.jpg",
    },
    {
        "nombre": "Formateo e Instalación de Windows",
        "descripcion": "Formateo seguro del disco, instalación de Windows y configuración de controladores.",
        "precio": 30.00,
        "duracion": "1.5 horas",
        "imagen": "servicio-4.jpg",
    },
    {
        "nombre": "Recuperación de Datos",
        "descripcion": "Recuperación de información vital desde discos dañados, USB o tarjetas de memoria.",
        "precio": 60.00,
        "duracion": "Variable",
        "imagen": "servicio-1.jpg",
    },
]

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
    return render_template("servicios.html", active="servicios", servicios=SERVICIOS)

@app.route("/servicios/nuevo", methods=['GET', 'POST'])
def nuevo_servicio():
    form = ProductoForm()
    if form.validate_on_submit():
        nuevo_item = {
            "nombre": form.nombre.data,
            "descripcion": form.descripcion.data,
            "precio": form.precio.data,
            "duracion": form.duracion.data,
            "imagen": form.imagen.data
        }
        SERVICIOS.append(nuevo_item)
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