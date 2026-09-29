# PC-Fix – Sistema web para gestión de servicios técnicos

## Descripción

PC-Fix es un sistema web desarrollado para gestionar servicios técnicos de soporte y mantenimiento de equipos informáticos. La aplicación integra una página pública informativa con módulos de gestión, formularios validados, autenticación de usuarios y persistencia de datos en PostgreSQL.

El proyecto cuenta también con una versión estática publicada en GitHub Pages:

**[https://marjoriegrandap.github.io/Proyecto_Grupal/](https://marjoriegrandap.github.io/Proyecto_Grupal/)**

> **Importante:** GitHub Pages presenta únicamente una demostración visual de la interfaz. El CRUD real, PostgreSQL, la autenticación, las sesiones y las operaciones protegidas se ejecutan en la aplicación Flask local.

## Tecnologías utilizadas

- Python
- Flask
- Flask-WTF y WTForms
- Flask-Login
- PostgreSQL
- psycopg2
- Werkzeug
- Jinja2
- Bootstrap
- HTML, CSS y JavaScript

## Funcionalidades principales

- Página pública con información de PC-Fix.
- Gestión de servicios técnicos.
- Formularios construidos con Flask-WTF.
- Validaciones en el cliente y en el servidor.
- CRUD completo de servicios conectado a PostgreSQL.
- Relación entre servicios y proveedores.
- Biblioteca multimedia visual: imágenes originales de `static/img` y nuevas imágenes persistentes en PostgreSQL (JPG, PNG, WEBP, hasta 2 MB).
- Registro de usuarios.
- Contraseñas almacenadas mediante hash, no en texto plano.
- Inicio y cierre de sesión.
- Rutas protegidas mediante Flask-Login.
- Módulos de Clientes, Proveedores y Facturación.
- Publicación de una versión estática demostrativa mediante GitHub Pages.

## Flask local y GitHub Pages

La aplicación Flask local es la versión funcional del sistema. En ella se ejecutan las validaciones, el registro e inicio de sesión, la gestión de sesiones, las rutas protegidas, el CRUD de Servicios y las consultas a PostgreSQL.

GitHub Pages no ejecuta Python, Flask ni PostgreSQL. Por ello, la publicación estática permite visualizar la interfaz y navegar por sus páginas, pero no reemplaza el entorno Flask local ni almacena datos reales.

## Estructura principal

```text
Proyecto_Grupal/
├── app.py                  # Aplicación Flask y rutas
├── models.py               # Modelo de usuario para Flask-Login
├── requirements.txt        # Dependencias del proyecto
├── .env.example            # Referencia de variables de entorno
├── conexion/               # Conexión e inicialización de PostgreSQL
├── forms/                  # Formularios Flask-WTF
├── sql/esquema.sql         # Tablas y datos iniciales
├── templates/              # Plantillas Jinja2 de Flask
├── static/                 # CSS, JavaScript e imágenes
├── secciones/              # Páginas HTML estáticas
└── index.html              # Portada estática para GitHub Pages
```

## Instalación y ejecución local

1. Clonar el repositorio:

	```bash
	git clone URL_DEL_REPOSITORIO
	cd Proyecto_Grupal
	```

2. Crear y activar un entorno virtual:

	```bash
	python -m venv .venv
	```

	En Windows:

	```powershell
	.venv\Scripts\Activate.ps1
	```

	En macOS o Linux:

	```bash
	source .venv/bin/activate
	```

3. Instalar las dependencias:

	```bash
	pip install -r requirements.txt
	```

4. Crear el archivo `.env` tomando `.env.example` como referencia. Debe incluir, como mínimo:

	```dotenv
	DB_HOST=localhost
	DB_PORT=5432
	DB_NAME=pcfix_db
	DB_USER=postgres
	DB_PASSWORD=tu_contrasena_postgresql
	SECRET_KEY=tu_clave_secreta_aqui
	```

5. Configurar PostgreSQL y asegurarse de que el servidor esté activo. La aplicación utiliza las credenciales definidas en `.env` y puede crear la base de datos `pcfix_db` si el usuario tiene permisos suficientes.

6. Ejecutar la aplicación:

	```bash
	python app.py
	```

7. Abrir en el navegador:

	[http://127.0.0.1:5000](http://127.0.0.1:5000)

### Esquema de la base de datos

El archivo `sql/esquema.sql` crea las tablas de Usuarios, Proveedores, Servicios, Clientes y Facturas, incluyendo sus relaciones, restricciones y datos iniciales. La aplicación lo carga durante la inicialización de la base de datos.

### Seguridad de la configuración

El archivo `.env` contiene credenciales de PostgreSQL y la clave secreta de Flask. **`.env` no debe subirse a GitHub** ni compartirse públicamente. Utiliza `.env.example` como plantilla sin incluir contraseñas reales.

## Integrantes

- Johao Caicedo
- Cristhian Chacha
- Marjorie Granda

## Biblioteca multimedia de servicios

En crear/editar servicio, **Seleccionar imagen** abre la biblioteca. Las imágenes
nuevas se verifican y decodifican con Pillow, se guardan en PostgreSQL y se reutilizan
por SHA-256 si el archivo es idéntico. No requieren almacenamiento persistente de
archivos en el servidor. Las imágenes originales siguen en `static/img`.
La eliminación requiere administrador y CSRF; se bloquea si cualquier servicio
(incluidos pausados y archivados) utiliza la imagen. Cambiar la imagen no borra la anterior.

La migración `sql/migracion_biblioteca_multimedia.sql` también está incorporada en
`sql/esquema.sql`. La biblioteca permite hasta 2 MB y 20 megapíxeles por imagen estática.

## Primer administrador opcional

Una instalación nueva no incluye cuentas ni contraseñas predeterminadas.
Para crear el primer administrador, define en el entorno privado las tres variables
`ADMIN_USERNAME`, `ADMIN_EMAIL` y `ADMIN_PASSWORD` documentadas en `.env.example`.
El inicio de la aplicación guarda únicamente el hash de la contraseña. Si ya existe
un administrador, no crea otro ni cambia credenciales. No convierte cuentas cliente
en administradores. Tras la creación pueden retirarse las tres variables.

## Verificación

```text
python -m unittest discover -s tests -q
python -m compileall -q app.py biblioteca.py conexion forms tests
```

Las pruebas de integración requieren una PostgreSQL local ya inicializada y cuentas
locales admin/cliente; revierten los datos de prueba. La prueba de instalación nueva
crea un esquema aislado y lo revierte, sin reemplazar las tablas existentes.
El controlador multimedia también dispone de una prueba sin dependencias Node:
`node tests/biblioteca_frontend.js` (o un entorno JavaScript compatible).

Ver `AUDITORIA_PRE_RENDER.md` para el resultado de la revisión de este bloque.


## Duraciones y pagos

Los servicios usan cantidad y unidad de duración; Variable no exige cantidad.
El precio del servicio es base sin IVA. `IVA_RATE` define la tarifa de proyecto.
Los datos de transferencia se configuran con las cuatro variables `PAYMENT_*`
indicadas en `.env.example`, sin publicar credenciales ni datos reales en Git.

El administrador inicia la revisión y fija el total con IVA desde **Gestionar → Pagos**.
El cliente puede presentar comprobante por el anticipo del 50 % o el pago total del
100 %. El administrador confirma o rechaza cada comprobante; un anticipo confirmado
habilita la reparación y el saldo restante se paga al llegar a Listo. Un pago total
confirmado no solicita un segundo pago. La factura final se emite únicamente tras el
pago completo y conserva los importes aplicados.

Las nuevas tablas y columnas están en `sql/migracion_pagos_iva_duracion.sql` y
`sql/esquema.sql`. Para una base existente, ejecutar después
`sql/migracion_facturas_historicas.sql` una sola vez: convierte cada factura emitida
usando su importe anterior como base, fija IVA al 15 %, marca la factura pagada y
registra la conciliación histórica sin archivo de comprobante. Es idempotente.
Los comprobantes nuevos quedan en PostgreSQL, se conservan tras un rechazo y no se
incluyen en la factura ni se exponen a otros clientes.
# Eliminación lógica e historial

Servicios y Clientes conservan sus filas al pulsar **Eliminar**: quedan excluidos
del uso futuro y no se pueden reactivar. **Archivar** permite restaurar; en Clientes
se reutiliza el estado inactivo. Los pedidos del portal pertenecen a `usuarios`,
una entidad independiente de los registros administrativos de `clientes`.

Para una base existente, aplicar `sql/migracion_eliminacion_logica.sql` dentro de
una transacción antes de servir la aplicación actualizada. El mismo SQL está
incluido en `sql/esquema.sql`, que se ejecuta durante la inicialización habitual.
La migración es repetible, conserva las filas y sustituye las reglas destructivas
de las relaciones históricas por `RESTRICT`.

Las facturas nuevas guardan nombre, descripción y precio al emitirse. Para las
antiguas, solo se completan snapshots ausentes: descripción disponible actualmente
y precio procedente de la propia factura. No se pueden reconstruir descripciones
anteriores que nunca se guardaron.

Pruebas específicas (incluyen migración y rollback):
`python -m unittest discover -s tests -p test_eliminacion_logica.py -v`.
