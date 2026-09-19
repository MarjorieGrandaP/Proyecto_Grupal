import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env si existe
load_dotenv()

# Parámetros de configuración de la base de datos PostgreSQL
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'pcfix_db')
DB_USER = os.getenv('DB_USER', 'postgres')
# La contraseña se obtiene exclusivamente desde .env.
# No se incluye ninguna contraseña real dentro del código.
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not DB_PASSWORD:
    raise RuntimeError(
        "No se encontró DB_PASSWORD. "
        "Configúrala en el archivo .env."
    )


def obtener_conexion():
    """
    Establece y retorna una conexión a la base de datos PostgreSQL.
    Retorna la conexión con cursor RealDictCursor para acceder a las columnas por nombre.
    """
    try:
        conexion = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conexion
    except psycopg2.Error as err:
        print(f"[ERROR CONEXION] Error al conectar con PostgreSQL: {err}")
        raise err


def inicializar_base_datos():
    """
    Crea la base de datos pcfix_db si no existe y ejecuta el esquema sql/esquema.sql
    para crear las tablas y sembrar datos iniciales.
    """
    # 1. Conectar al mantenimiento predeterminado de postgres para crear la base de datos si no existe
    try:
        conn_init = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database='postgres',
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn_init.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor_init = conn_init.cursor()
        
        cursor_init.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if not cursor_init.fetchone():
            cursor_init.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"[BD] Base de datos '{DB_NAME}' creada con éxito.")
            
        cursor_init.close()
        conn_init.close()
    except Exception as e:
        print(f"[AVISO INICIALIZACION] Verificación de base de datos 'postgres': {e}")

    # 2. Ejecutar esquema.sql sobre la base de datos de la aplicación
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        
        ruta_esquema = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sql', 'esquema.sql')
        if os.path.exists(ruta_esquema):
            with open(ruta_esquema, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            cursor.execute(sql_script)
            conn.commit()
            print("[BD] Esquema de base de datos cargado correctamente desde sql/esquema.sql.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR INICIALIZACION] Al cargar esquema.sql en '{DB_NAME}': {e}")
