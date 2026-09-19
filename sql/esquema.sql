-- =========================================================
-- ESQUEMA RELACIONAL: PC-FIX
-- Avance 13/16: Base de datos relacional PostgreSQL
-- =========================================================

-- 1. Tabla Proveedores
CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor SERIAL PRIMARY KEY,
    empresa VARCHAR(100) NOT NULL,
    contacto VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    categoria VARCHAR(100) NOT NULL
);

-- 2. Tabla Servicios (Productos / Servicios Técnicos)
CREATE TABLE IF NOT EXISTS servicios (
    id_servicio SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT NOT NULL,
    precio NUMERIC(10, 2) NOT NULL,
    duracion VARCHAR(50) NOT NULL,
    imagen VARCHAR(100) NOT NULL,
    id_proveedor INT REFERENCES proveedores(id_proveedor) ON DELETE SET NULL
);

-- 3. Tabla Clientes
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    cedula VARCHAR(20),
    telefono VARCHAR(20) NOT NULL,
    correo VARCHAR(100),
    equipo VARCHAR(100) NOT NULL,
    estado VARCHAR(50) NOT NULL DEFAULT 'Pendiente'
);

-- 4. Tabla Facturas
CREATE TABLE IF NOT EXISTS facturas (
    id_factura SERIAL PRIMARY KEY,
    numero VARCHAR(50) NOT NULL UNIQUE,
    id_cliente INT REFERENCES clientes(id_cliente) ON DELETE CASCADE,
    id_servicio INT REFERENCES servicios(id_servicio) ON DELETE SET NULL,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    total NUMERIC(10, 2) NOT NULL,
    estado VARCHAR(50) NOT NULL DEFAULT 'Pendiente'
);

-- 5. Tabla Usuarios: identificador único; nombre de usuario obligatorio; UNIQUE para impedir usuarios duplicados; espacio suficiente para almacenar la contraseña hasheada, no en texto plano.
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario SERIAL PRIMARY KEY,
    usuario VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    correo VARCHAR(120),
    rol VARCHAR(10) NOT NULL DEFAULT 'cliente',
    CONSTRAINT usuarios_rol_check CHECK (rol IN ('admin', 'cliente')),
    CONSTRAINT usuarios_correo_unique UNIQUE (correo)
);

-- Migración segura: los usuarios antiguos pueden conservar correo NULL.
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS correo VARCHAR(120);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'usuarios_correo_unique'
          AND conrelid = 'usuarios'::regclass
    ) THEN
        ALTER TABLE usuarios
        ADD CONSTRAINT usuarios_correo_unique UNIQUE (correo);
    END IF;
END $$;

-- Normalizar correos históricos antes de aplicar unicidad sin distinguir mayúsculas.
-- Si existían duplicados por diferencias de formato, se conserva el primero y
-- los demás quedan NULL para no eliminar usuarios ni inventar correos.
WITH correos_repetidos AS (
    SELECT id_usuario,
           ROW_NUMBER() OVER (
               PARTITION BY LOWER(BTRIM(correo))
               ORDER BY id_usuario
           ) AS posicion
    FROM usuarios
    WHERE correo IS NOT NULL
)
UPDATE usuarios u
SET correo = NULL
FROM correos_repetidos r
WHERE u.id_usuario = r.id_usuario
  AND r.posicion > 1;

UPDATE usuarios
SET correo = LOWER(BTRIM(correo))
WHERE correo IS NOT NULL;

-- PostgreSQL impide duplicados que difieran solo por mayúsculas/minúsculas.
CREATE UNIQUE INDEX IF NOT EXISTS usuarios_correo_lower_unique
    ON usuarios (LOWER(correo))
    WHERE correo IS NOT NULL;

-- Migración segura para instalaciones que ya tenían creada la tabla usuarios.
-- Los usuarios existentes se conservan y reciben el rol cliente por defecto.
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS rol VARCHAR(10);

UPDATE usuarios
SET rol = 'cliente'
WHERE rol IS NULL OR rol NOT IN ('admin', 'cliente');

ALTER TABLE usuarios
ALTER COLUMN rol SET DEFAULT 'cliente',
ALTER COLUMN rol SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'usuarios_rol_check'
          AND conrelid = 'usuarios'::regclass
    ) THEN
        ALTER TABLE usuarios
        ADD CONSTRAINT usuarios_rol_check CHECK (rol IN ('admin', 'cliente'));
    END IF;
END $$;

-- 7. Pedidos de clientes.
CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL,
    id_servicio INTEGER,
    equipo VARCHAR(100) NOT NULL,
    descripcion TEXT NOT NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'Solicitado',
    solicita_factura BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_solicitud TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pedidos_estado_check CHECK (
        estado IN ('Solicitado', 'En revisión', 'En reparación', 'Listo', 'Entregado', 'Cancelado')
    ),
    CONSTRAINT pedidos_usuario_fk
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON DELETE CASCADE,
    CONSTRAINT pedidos_servicio_fk
        FOREIGN KEY (id_servicio)
        REFERENCES servicios(id_servicio)
        ON DELETE SET NULL
);

-- Migración segura para instalaciones que ya tengan pedidos parcialmente creados.
ALTER TABLE pedidos
ADD COLUMN IF NOT EXISTS id_usuario INTEGER,
ADD COLUMN IF NOT EXISTS id_servicio INTEGER,
ADD COLUMN IF NOT EXISTS equipo VARCHAR(100),
ADD COLUMN IF NOT EXISTS descripcion TEXT,
ADD COLUMN IF NOT EXISTS estado VARCHAR(30) DEFAULT 'Solicitado',
ADD COLUMN IF NOT EXISTS solicita_factura BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'pedidos_estado_check'
          AND conrelid = 'pedidos'::regclass
    ) THEN
        ALTER TABLE pedidos ADD CONSTRAINT pedidos_estado_check CHECK (
            estado IN ('Solicitado', 'En revisión', 'En reparación', 'Listo', 'Entregado', 'Cancelado')
        );
    END IF;
END $$;

-- Facturas nuevas pueden vincularse a usuarios y pedidos; las antiguas siguen siendo válidas.
ALTER TABLE facturas
ADD COLUMN IF NOT EXISTS id_usuario INTEGER,
ADD COLUMN IF NOT EXISTS id_pedido INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'facturas_usuario_fk'
          AND conrelid = 'facturas'::regclass
    ) THEN
        ALTER TABLE facturas ADD CONSTRAINT facturas_usuario_fk
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'facturas_pedido_fk'
          AND conrelid = 'facturas'::regclass
    ) THEN
        ALTER TABLE facturas ADD CONSTRAINT facturas_pedido_fk
            FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE SET NULL;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS facturas_pedido_unique
    ON facturas (id_pedido)
    WHERE id_pedido IS NOT NULL;

-- 6. Perfil 1:1 de cada usuario. Los datos personales pueden quedar vacíos
-- para usuarios antiguos hasta que completen su perfil.
CREATE TABLE IF NOT EXISTS perfiles_usuario (
    id_perfil SERIAL PRIMARY KEY,
    id_usuario INTEGER UNIQUE NOT NULL,
    nombres VARCHAR(100),
    apellidos VARCHAR(100),
    telefono VARCHAR(30),
    imagen VARCHAR(255),
    CONSTRAINT perfiles_usuario_usuario_fk
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON DELETE CASCADE
);

-- Crear perfiles vacíos sin inventar datos para usuarios ya existentes.
INSERT INTO perfiles_usuario (id_usuario)
SELECT u.id_usuario
FROM usuarios u
WHERE NOT EXISTS (
    SELECT 1
    FROM perfiles_usuario p
    WHERE p.id_usuario = u.id_usuario
);

-- 8. Auditoría de cambios de datos.
CREATE TABLE IF NOT EXISTS auditoria (
    id_auditoria SERIAL PRIMARY KEY,
    tabla VARCHAR(50) NOT NULL,
    operacion VARCHAR(10) NOT NULL,
    id_registro VARCHAR(100),
    datos_anteriores JSONB,
    datos_nuevos JSONB,
    usuario_bd VARCHAR(100),
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT auditoria_operacion_check CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE'))
);

CREATE OR REPLACE FUNCTION registrar_auditoria()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    datos_anteriores_json JSONB;
    datos_nuevos_json JSONB;
    registro_id VARCHAR(100);
BEGIN
    IF TG_OP = 'UPDATE' AND to_jsonb(OLD) = to_jsonb(NEW) THEN
        RETURN NEW;
    END IF;

    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        datos_anteriores_json := to_jsonb(OLD);
    END IF;

    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        datos_nuevos_json := to_jsonb(NEW);
    END IF;

    -- Nunca conservar contraseñas, aunque estén almacenadas como hash.
    IF TG_TABLE_NAME = 'usuarios' THEN
        datos_anteriores_json := datos_anteriores_json - 'password';
        datos_nuevos_json := datos_nuevos_json - 'password';
    END IF;

    registro_id := CASE TG_TABLE_NAME
        WHEN 'usuarios' THEN COALESCE(datos_nuevos_json->>'id_usuario', datos_anteriores_json->>'id_usuario')
        WHEN 'perfiles_usuario' THEN COALESCE(datos_nuevos_json->>'id_perfil', datos_anteriores_json->>'id_perfil')
        WHEN 'servicios' THEN COALESCE(datos_nuevos_json->>'id_servicio', datos_anteriores_json->>'id_servicio')
        WHEN 'pedidos' THEN COALESCE(datos_nuevos_json->>'id_pedido', datos_anteriores_json->>'id_pedido')
        WHEN 'facturas' THEN COALESCE(datos_nuevos_json->>'id_factura', datos_anteriores_json->>'id_factura')
        WHEN 'clientes' THEN COALESCE(datos_nuevos_json->>'id_cliente', datos_anteriores_json->>'id_cliente')
        WHEN 'proveedores' THEN COALESCE(datos_nuevos_json->>'id_proveedor', datos_anteriores_json->>'id_proveedor')
        ELSE NULL
    END;

    INSERT INTO auditoria (
        tabla, operacion, id_registro, datos_anteriores,
        datos_nuevos, usuario_bd, fecha_hora
    )
    VALUES (
        TG_TABLE_NAME, TG_OP, registro_id, datos_anteriores_json,
        datos_nuevos_json, CURRENT_USER, CURRENT_TIMESTAMP
    );

    RETURN NULL;
END;
$$;

-- Triggers idempotentes: solo se reemplazan triggers, nunca datos de negocio.
DROP TRIGGER IF EXISTS auditoria_usuarios ON usuarios;
CREATE TRIGGER auditoria_usuarios
AFTER INSERT OR UPDATE OR DELETE ON usuarios
FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();

DROP TRIGGER IF EXISTS auditoria_perfiles_usuario ON perfiles_usuario;
CREATE TRIGGER auditoria_perfiles_usuario
AFTER INSERT OR UPDATE OR DELETE ON perfiles_usuario
FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();

DROP TRIGGER IF EXISTS auditoria_servicios ON servicios;
CREATE TRIGGER auditoria_servicios
AFTER INSERT OR UPDATE OR DELETE ON servicios
FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();

DROP TRIGGER IF EXISTS auditoria_pedidos ON pedidos;
CREATE TRIGGER auditoria_pedidos
AFTER INSERT OR UPDATE OR DELETE ON pedidos
FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();

DROP TRIGGER IF EXISTS auditoria_facturas ON facturas;
CREATE TRIGGER auditoria_facturas
AFTER INSERT OR UPDATE OR DELETE ON facturas
FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();

DROP TRIGGER IF EXISTS auditoria_clientes ON clientes;
CREATE TRIGGER auditoria_clientes
AFTER INSERT OR UPDATE OR DELETE ON clientes
FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();

DROP TRIGGER IF EXISTS auditoria_proveedores ON proveedores;
CREATE TRIGGER auditoria_proveedores
AFTER INSERT OR UPDATE OR DELETE ON proveedores
FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();
-- =========================================================
-- INSERCIÓN DE DATOS INICIALES (SEMILLA)
-- =========================================================

-- Inserción de Proveedores
INSERT INTO proveedores (empresa, contacto, telefono, categoria)
SELECT 'TecnoRepuestos S.A.', 'Ing. Marco Ruiz', '022456789', 'Placas y componentes'
WHERE NOT EXISTS (SELECT 1 FROM proveedores WHERE empresa = 'TecnoRepuestos S.A.');

INSERT INTO proveedores (empresa, contacto, telefono, categoria)
SELECT 'Almacenes Comercial', 'Sra. Rosa Vega', '022998877', 'Pantallas y baterías'
WHERE NOT EXISTS (SELECT 1 FROM proveedores WHERE empresa = 'Almacenes Comercial');

INSERT INTO proveedores (empresa, contacto, telefono, categoria)
SELECT 'PC Parts Ecuador', 'Sr. Pablo Andrade', '0987001122', 'Memorias RAM y SSD'
WHERE NOT EXISTS (SELECT 1 FROM proveedores WHERE empresa = 'PC Parts Ecuador');

-- Inserción de Servicios con relación a Proveedores
INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Mantenimiento Preventivo', 'Limpieza interna profunda, cambio de pasta térmica de alta calidad y revisión exhaustiva de componentes.', 25.00, '1 hora', 'servicio-1.jpg', 1
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE nombre = 'Mantenimiento Preventivo');

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Mantenimiento Correctivo', 'Diagnóstico preciso, reparación a nivel de placa y reemplazo de hardware dañado.', 40.00, '2 horas', 'servicio-2.jpg', 1
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE nombre = 'Mantenimiento Correctivo');

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Optimización y Limpieza', 'Aceleramos el rendimiento de tu sistema operativo y eliminamos virus o malware.', 20.00, '45 minutos', 'servicio-3.jpg', 3
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE nombre = 'Optimización y Limpieza');

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Instalación de Software', 'Instalación desde cero y actualización de sistemas operativos y programas esenciales.', 15.00, '30 minutos', 'servicio-4.jpg', 3
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE nombre = 'Instalación de Software');

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Formateo e Instalación de Windows', 'Formateo seguro del disco, instalación de Windows y configuración de controladores.', 30.00, '1.5 horas', 'servicio-4.jpg', 3
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE nombre = 'Formateo e Instalación de Windows');

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Recuperación de Datos', 'Recuperación de información vital desde discos dañados, USB o tarjetas de memoria.', 60.00, 'Variable', 'servicio-1.jpg', 2
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE nombre = 'Recuperación de Datos');

-- Inserción de Clientes
INSERT INTO clientes (nombre, cedula, telefono, correo, equipo, estado)
SELECT 'Ana Torres', '1712345678', '0991234567', 'ana.torres@email.com', 'Laptop HP Pavilion', 'En revisión'
WHERE NOT EXISTS (SELECT 1 FROM clientes WHERE nombre = 'Ana Torres');

INSERT INTO clientes (nombre, cedula, telefono, correo, equipo, estado)
SELECT 'Luis Mendoza', '1798765432', '0987654321', 'luis.mendoza@email.com', 'PC de escritorio', 'Entregado'
WHERE NOT EXISTS (SELECT 1 FROM clientes WHERE nombre = 'Luis Mendoza');

INSERT INTO clientes (nombre, cedula, telefono, correo, equipo, estado)
SELECT 'Karen Salazar', '0911223344', '0971122334', 'karen.salazar@email.com', 'MacBook Air', 'En reparación'
WHERE NOT EXISTS (SELECT 1 FROM clientes WHERE nombre = 'Karen Salazar');

INSERT INTO clientes (nombre, cedula, telefono, correo, equipo, estado)
SELECT 'Diego Núñez', '0922334455', '0965544332', 'diego.nunez@email.com', 'Laptop Lenovo IdeaPad', 'Pendiente'
WHERE NOT EXISTS (SELECT 1 FROM clientes WHERE nombre = 'Diego Núñez');

-- Inserción de Facturas
INSERT INTO facturas (numero, id_cliente, id_servicio, fecha, total, estado)
SELECT 'FAC-001', 1, 1, '2026-08-10', 25.00, 'Pagada'
WHERE NOT EXISTS (SELECT 1 FROM facturas WHERE numero = 'FAC-001');

INSERT INTO facturas (numero, id_cliente, id_servicio, fecha, total, estado)
SELECT 'FAC-002', 2, 4, '2026-08-11', 15.00, 'Pagada'
WHERE NOT EXISTS (SELECT 1 FROM facturas WHERE numero = 'FAC-002');

INSERT INTO facturas (numero, id_cliente, id_servicio, fecha, total, estado)
SELECT 'FAC-003', 3, 2, '2026-08-14', 40.00, 'Pendiente'
WHERE NOT EXISTS (SELECT 1 FROM facturas WHERE numero = 'FAC-003');

INSERT INTO facturas (numero, id_cliente, id_servicio, fecha, total, estado)
SELECT 'FAC-004', 4, 5, '2026-08-15', 30.00, 'Pendiente'
WHERE NOT EXISTS (SELECT 1 FROM facturas WHERE numero = 'FAC-004');
