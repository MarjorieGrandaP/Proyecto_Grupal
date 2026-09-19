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
- Selección dinámica de imágenes para los servicios disponibles en `static/img`.
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