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

-- Eliminación lógica: conserva datos, claves foráneas y estados al reejecutar.
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;

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
        estado IN ('Solicitado', 'Pendiente de anticipo', 'En revisión', 'En reparación', 'Listo', 'Entregado', 'Cancelado')
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
            estado IN ('Solicitado', 'Pendiente de anticipo', 'En revisión', 'En reparación', 'Listo', 'Entregado', 'Cancelado')
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
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE LOWER(BTRIM(nombre)) = LOWER(BTRIM('Mantenimiento Preventivo')));

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Mantenimiento Correctivo', 'Diagnóstico preciso, reparación a nivel de placa y reemplazo de hardware dañado.', 40.00, '2 horas', 'servicio-2.jpg', 1
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE LOWER(BTRIM(nombre)) = LOWER(BTRIM('Mantenimiento Correctivo')));

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Optimización y Limpieza', 'Aceleramos el rendimiento de tu sistema operativo y eliminamos virus o malware.', 20.00, '45 minutos', 'servicio-3.jpg', 3
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE LOWER(BTRIM(nombre)) = LOWER(BTRIM('Optimización y Limpieza')));

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Instalación de Software', 'Instalación desde cero y actualización de sistemas operativos y programas esenciales.', 15.00, '30 minutos', 'servicio-4.jpg', 3
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE LOWER(BTRIM(nombre)) = LOWER(BTRIM('Instalación de Software')));

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Formateo e Instalación de Windows', 'Formateo seguro del disco, instalación de Windows y configuración de controladores.', 30.00, '1.5 horas', 'servicio-4.jpg', 3
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE LOWER(BTRIM(nombre)) = LOWER(BTRIM('Formateo e Instalación de Windows')));

INSERT INTO servicios (nombre, descripcion, precio, duracion, imagen, id_proveedor)
SELECT 'Recuperación de Datos', 'Recuperación de información vital desde discos dañados, USB o tarjetas de memoria.', 60.00, 'Variable', 'servicio-1.jpg', 2
WHERE NOT EXISTS (SELECT 1 FROM servicios WHERE LOWER(BTRIM(nombre)) = LOWER(BTRIM('Recuperación de Datos')));

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


-- Copia histórica del servicio: conserva valores existentes y permite reejecución.
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS servicio_nombre VARCHAR(100);

UPDATE facturas f
SET servicio_nombre = s.nombre
FROM servicios s
WHERE f.id_servicio = s.id_servicio
  AND f.servicio_nombre IS NULL;

-- Migración de historial, archivado y nombres únicos (también disponible por separado).
-- Reparación conservadora: nunca sobrescribe un snapshot existente.
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS servicio_nombre VARCHAR(100);
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS archivado BOOLEAN NOT NULL DEFAULT FALSE;

-- 1. Relación directa todavía existente.
UPDATE facturas f SET servicio_nombre = s.nombre
FROM servicios s
WHERE f.id_servicio = s.id_servicio
  AND NULLIF(BTRIM(f.servicio_nombre), '') IS NULL;

-- 2. Relación conservada en el pedido.
UPDATE facturas f SET servicio_nombre = s.nombre
FROM pedidos p JOIN servicios s ON s.id_servicio = p.id_servicio
WHERE f.id_pedido = p.id_pedido
  AND NULLIF(BTRIM(f.servicio_nombre), '') IS NULL;

-- 3. Auditoría: aceptar solo un id de servicio y un nombre inequívocos.
-- Si hubo varios ids/nombres históricos, no adivinar cuál fue facturado.
WITH referencias_brutas AS (
    SELECT f.id_factura, j.datos->>'id_servicio' AS servicio_id,
           CASE WHEN a.tabla = 'facturas' THEN 1 ELSE 2 END AS prioridad
    FROM facturas f
    JOIN auditoria a ON
        (a.tabla = 'facturas' AND a.id_registro = f.id_factura::text)
        OR (a.tabla = 'pedidos' AND a.id_registro = f.id_pedido::text)
    CROSS JOIN LATERAL (VALUES (a.datos_anteriores), (a.datos_nuevos)) AS j(datos)
    WHERE NULLIF(BTRIM(f.servicio_nombre), '') IS NULL
      AND NULLIF(j.datos->>'id_servicio', '') IS NOT NULL
), referencias AS (
    -- La relación registrada en la propia factura prevalece sobre cambios del pedido.
    SELECT r.id_factura, r.servicio_id FROM referencias_brutas r
    WHERE r.prioridad = (
        SELECT MIN(r2.prioridad) FROM referencias_brutas r2
        WHERE r2.id_factura = r.id_factura
    )
), ids_unicos AS (
    SELECT id_factura, MIN(servicio_id) AS servicio_id
    FROM referencias GROUP BY id_factura
    HAVING COUNT(DISTINCT servicio_id) = 1
), nombres AS (
    SELECT i.id_factura, j.datos->>'nombre' AS nombre
    FROM ids_unicos i
    JOIN auditoria a ON a.tabla = 'servicios' AND a.id_registro = i.servicio_id
    CROSS JOIN LATERAL (VALUES (a.datos_anteriores), (a.datos_nuevos)) AS j(datos)
    WHERE NULLIF(BTRIM(j.datos->>'nombre'), '') IS NOT NULL
), recuperables AS (
    SELECT id_factura, MIN(nombre) AS nombre
    FROM nombres GROUP BY id_factura
    HAVING COUNT(DISTINCT nombre) = 1
)
UPDATE facturas f SET servicio_nombre = r.nombre
FROM recuperables r
WHERE f.id_factura = r.id_factura
  AND NULLIF(BTRIM(f.servicio_nombre), '') IS NULL;

-- No eliminar ni fusionar duplicados preexistentes durante una migración.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM servicios GROUP BY LOWER(BTRIM(nombre)) HAVING COUNT(*) > 1
    ) THEN
        CREATE UNIQUE INDEX IF NOT EXISTS servicios_nombre_normalizado_unique
            ON servicios (LOWER(BTRIM(nombre)));
    ELSE
        RAISE NOTICE 'Existen servicios duplicados; revisar antes de crear el índice único.';
    END IF;
END $$;

-- Modalidad y seguimiento persistente; migración aditiva y reejecutable.
ALTER TABLE servicios
ADD COLUMN IF NOT EXISTS requiere_entrega_equipo BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS historial_estado_pedidos (
    id_historial SERIAL PRIMARY KEY,
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    estado_anterior VARCHAR(30),
    estado_nuevo VARCHAR(30) NOT NULL,
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_usuario_actor INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS historial_estado_pedidos_pedido_fecha
ON historial_estado_pedidos (id_pedido, fecha_hora, id_historial);

CREATE OR REPLACE FUNCTION registrar_historial_estado_pedido()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    actor INTEGER;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.estado IS NOT DISTINCT FROM NEW.estado THEN
        RETURN NEW;
    END IF;
    -- Configuración local a la transacción, definida por las rutas autenticadas.
    actor := NULLIF(current_setting('pcfix.usuario_actor', TRUE), '')::INTEGER;
    INSERT INTO historial_estado_pedidos
        (id_pedido, estado_anterior, estado_nuevo, id_usuario_actor)
    VALUES (NEW.id_pedido,
            CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.estado END,
            NEW.estado, actor);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS historial_estado_pedido ON pedidos;
CREATE TRIGGER historial_estado_pedido
AFTER INSERT OR UPDATE OF estado ON pedidos
FOR EACH ROW EXECUTE FUNCTION registrar_historial_estado_pedido();

-- Pedidos previos: registrar únicamente el estado observado hoy.
-- No inventar fechas ni transiciones pasadas que esta tabla aún no registraba.
INSERT INTO historial_estado_pedidos (id_pedido, estado_nuevo)
SELECT p.id_pedido, p.estado FROM pedidos p
WHERE NOT EXISTS (
    SELECT 1 FROM historial_estado_pedidos h WHERE h.id_pedido = p.id_pedido
);

-- Ampliación de pedidos: cancelación motivada, anticipo y aceptación.
ALTER TABLE pedidos
    ADD COLUMN IF NOT EXISTS motivo_cancelacion VARCHAR(100),
    ADD COLUMN IF NOT EXISTS observacion TEXT,
    ADD COLUMN IF NOT EXISTS cancelado_por INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS fecha_cancelacion TIMESTAMP,
    ADD COLUMN IF NOT EXISTS anticipo_solicitado BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS anticipo_pagado BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS terminos_aceptados BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fecha_aceptacion_terminos TIMESTAMP;
ALTER TABLE pedidos DROP CONSTRAINT IF EXISTS pedidos_estado_check;
ALTER TABLE pedidos ADD CONSTRAINT pedidos_estado_check CHECK (
    estado IN ('Solicitado','Pendiente de anticipo','En revisión','En reparación','Listo','Entregado','Cancelado')
);
ALTER TABLE historial_estado_pedidos
    ADD COLUMN IF NOT EXISTS observacion TEXT,
    ADD COLUMN IF NOT EXISTS motivo_cancelacion VARCHAR(100);

CREATE OR REPLACE FUNCTION registrar_historial_estado_pedido()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE actor INTEGER;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.estado IS NOT DISTINCT FROM NEW.estado THEN
        RETURN NEW;
    END IF;
    actor := NULLIF(current_setting('pcfix.usuario_actor', TRUE), '')::INTEGER;
    INSERT INTO historial_estado_pedidos
        (id_pedido,estado_anterior,estado_nuevo,id_usuario_actor,observacion,motivo_cancelacion)
    VALUES (NEW.id_pedido,
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.estado END,
        NEW.estado, actor, NEW.observacion,
        CASE WHEN NEW.estado = 'Cancelado' THEN NEW.motivo_cancelacion ELSE NULL END);
    RETURN NEW;
END;
$$;

-- Corrección verificable: una factura emitida implica un pedido entregado.
-- Los triggers existentes conservan el estado anterior y esta observación.
UPDATE pedidos p
SET estado = 'Entregado', fecha_actualizacion = CURRENT_TIMESTAMP,
    observacion = 'Corrección de consistencia: pedido con factura emitida ajustado a Entregado.'
WHERE estado <> 'Entregado'
  AND EXISTS (SELECT 1 FROM facturas f WHERE f.id_pedido = p.id_pedido);

-- Equipo/modelo y copia histórica en facturas. No sobrescribir snapshots existentes.
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS equipo_nombre VARCHAR(100);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS equipo_modelo VARCHAR(100);

-- La cadena vacía conserva explícitamente que el modelo no era conocido.
-- Así una corrección posterior no lo incorpora a una factura ya emitida.
UPDATE facturas f
SET equipo_nombre = COALESCE(f.equipo_nombre, p.equipo),
    equipo_modelo = COALESCE(f.equipo_modelo, p.modelo, '')
FROM pedidos p
WHERE f.id_pedido = p.id_pedido
  AND (f.equipo_nombre IS NULL OR f.equipo_modelo IS NULL);

-- Facturas manuales antiguas: usar únicamente su cliente relacionado.
UPDATE facturas f
SET equipo_nombre = COALESCE(f.equipo_nombre, c.equipo),
    equipo_modelo = COALESCE(f.equipo_modelo, c.modelo, '')
FROM clientes c
WHERE f.id_pedido IS NULL AND f.id_cliente = c.id_cliente
  AND (f.equipo_nombre IS NULL OR f.equipo_modelo IS NULL);

-- Notas independientes: no alteran ni reemplazan transiciones anteriores.
CREATE TABLE IF NOT EXISTS observaciones_pedidos (
    id_observacion BIGSERIAL PRIMARY KEY,
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
    texto TEXT NOT NULL CHECK (length(btrim(texto)) BETWEEN 1 AND 2000),
    id_usuario_actor INTEGER REFERENCES usuarios(id_usuario),
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_observaciones_pedido ON observaciones_pedidos(id_pedido, fecha_hora, id_observacion);

-- Expediente técnico privado, visibilidad explícita y fecha real de entrega.
CREATE TABLE IF NOT EXISTS detalle_servicio (
    id_detalle SERIAL PRIMARY KEY,
    id_pedido INTEGER UNIQUE NOT NULL REFERENCES pedidos(id_pedido),
    diagnostico TEXT,
    trabajo_realizado TEXT,
    repuestos TEXT,
    recomendaciones TEXT,
    actualizado_por INTEGER REFERENCES usuarios(id_usuario),
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE observaciones_pedidos ADD COLUMN IF NOT EXISTS visible_cliente BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS fecha_entrega TIMESTAMP;

-- Solo transiciones de entrega reales; excluir estados iniciales y reparaciones de datos.
UPDATE pedidos p SET fecha_entrega = h.entrega
FROM (
    SELECT id_pedido, MIN(fecha_hora) AS entrega FROM historial_estado_pedidos
    WHERE estado_nuevo='Entregado' AND estado_anterior IS NOT NULL
      AND estado_anterior NOT IN ('Entregado','Cancelado')
      AND COALESCE(observacion,'') NOT LIKE 'Corrección de consistencia:%'
    GROUP BY id_pedido
) h WHERE p.id_pedido=h.id_pedido AND p.fecha_entrega IS NULL AND p.estado='Entregado';

CREATE OR REPLACE FUNCTION fijar_fecha_entrega_pedido()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.estado='Entregado' AND OLD.estado IS DISTINCT FROM NEW.estado
       AND NEW.fecha_entrega IS NULL
       AND COALESCE(NEW.observacion,'') NOT LIKE 'Corrección de consistencia:%' THEN
        NEW.fecha_entrega := CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS fecha_entrega_pedido ON pedidos;
CREATE TRIGGER fecha_entrega_pedido BEFORE UPDATE OF estado ON pedidos
FOR EACH ROW EXECUTE FUNCTION fijar_fecha_entrega_pedido();

CREATE OR REPLACE FUNCTION auditar_detalle_servicio()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO auditoria (tabla,operacion,id_registro,datos_anteriores,datos_nuevos,usuario_bd)
    VALUES ('detalle_servicio', TG_OP, NEW.id_detalle::text,
            CASE WHEN TG_OP='UPDATE' THEN to_jsonb(OLD) ELSE NULL END,
            to_jsonb(NEW), CURRENT_USER);
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS auditoria_detalle_servicio ON detalle_servicio;
CREATE TRIGGER auditoria_detalle_servicio AFTER INSERT OR UPDATE ON detalle_servicio
FOR EACH ROW EXECUTE FUNCTION auditar_detalle_servicio();

-- Biblioteca multimedia persistente, compatible con imágenes estáticas.
CREATE TABLE IF NOT EXISTS imagenes_servicio (
    id_imagen SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    mime_type VARCHAR(50) NOT NULL,
    contenido BYTEA NOT NULL,
    tamano_bytes INTEGER,
    hash_sha256 VARCHAR(64),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activa BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE UNIQUE INDEX IF NOT EXISTS imagenes_servicio_hash_unique ON imagenes_servicio(hash_sha256);
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS id_imagen INTEGER;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='servicios_imagen_fk' AND conrelid='servicios'::regclass) THEN
        ALTER TABLE servicios ADD CONSTRAINT servicios_imagen_fk
        FOREIGN KEY (id_imagen) REFERENCES imagenes_servicio(id_imagen) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS servicios_imagen_idx ON servicios(id_imagen);

-- Duraciones, cotización congelada y comprobantes persistentes.
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS duracion_cantidad NUMERIC(10,2);
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS duracion_unidad VARCHAR(10);
UPDATE servicios SET duracion_unidad='Variable'
WHERE duracion_unidad IS NULL AND LOWER(duracion)='variable';
UPDATE servicios SET duracion_cantidad=REPLACE(split_part(duracion,' ',1),',','.')::numeric,
    duracion_unidad=CASE WHEN LOWER(duracion) LIKE '%minuto%' THEN 'Minutos'
                        WHEN LOWER(duracion) LIKE '%hora%' THEN 'Horas'
                        WHEN LOWER(duracion) LIKE '%día%' THEN 'Días' ELSE 'Semanas' END
WHERE duracion_unidad IS NULL AND duracion ~* '^[0-9]{1,6}([.,][0-9]{1,2})? (minutos?|horas?|días?|semanas?)$';
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS pago_solicitado_por INTEGER REFERENCES usuarios(id_usuario);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS fecha_solicitud_pago TIMESTAMP;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS subtotal NUMERIC(12,2);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS porcentaje_iva NUMERIC(5,4);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS valor_iva NUMERIC(12,2);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS total NUMERIC(12,2);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS anticipo_requerido NUMERIC(12,2);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS saldo_requerido NUMERIC(12,2);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS subtotal NUMERIC(12,2);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS porcentaje_iva NUMERIC(5,4);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS valor_iva NUMERIC(12,2);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS migracion_historica_iva BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE facturas ALTER COLUMN total TYPE NUMERIC(12,2);
-- Las facturas históricas se convierten mediante sql/migracion_facturas_historicas.sql.
CREATE TABLE IF NOT EXISTS pagos (
    id_pago SERIAL PRIMARY KEY,
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
    tipo_pago VARCHAR(10) NOT NULL CHECK(tipo_pago IN ('anticipo','saldo','total')),
    monto NUMERIC(12,2) NOT NULL CHECK(monto>0),
    estado VARCHAR(12) NOT NULL DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente','Confirmado','Rechazado')),
    nombre_archivo VARCHAR(150),
    mime_type VARCHAR(50),
    contenido BYTEA,
    migracion_historica BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_confirmacion TIMESTAMP,
    id_usuario_confirma INTEGER REFERENCES usuarios(id_usuario),
    motivo_rechazo TEXT,
    CHECK(estado <> 'Rechazado' OR length(btrim(motivo_rechazo)) > 0)
);
ALTER TABLE pagos ALTER COLUMN nombre_archivo DROP NOT NULL;
ALTER TABLE pagos ALTER COLUMN mime_type DROP NOT NULL;
ALTER TABLE pagos ALTER COLUMN contenido DROP NOT NULL;
ALTER TABLE pagos ADD COLUMN IF NOT EXISTS migracion_historica BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE pagos DROP CONSTRAINT IF EXISTS pagos_tipo_pago_check;
ALTER TABLE pagos ADD CONSTRAINT pagos_tipo_pago_check CHECK(tipo_pago IN ('anticipo','saldo','total'));
CREATE UNIQUE INDEX IF NOT EXISTS pagos_unico_vigente ON pagos(id_pedido,tipo_pago)
WHERE estado IN ('Pendiente','Confirmado');
CREATE OR REPLACE FUNCTION auditar_pago() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO auditoria(tabla,operacion,id_registro,datos_anteriores,datos_nuevos,usuario_bd)
    VALUES ('pagos',TG_OP,NEW.id_pago::text,
        CASE WHEN TG_OP='UPDATE' THEN to_jsonb(OLD)-'contenido' ELSE NULL END,
        to_jsonb(NEW)-'contenido',CURRENT_USER);
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS auditoria_pago ON pagos;
CREATE TRIGGER auditoria_pago AFTER INSERT OR UPDATE ON pagos FOR EACH ROW EXECUTE FUNCTION auditar_pago();
-- Conservar el estado antiguo en historial; registrar la separación en vez de borrarlo.
UPDATE pedidos SET estado='En revisión',fecha_actualizacion=CURRENT_TIMESTAMP,
    observacion='Migración: separación del anticipo y del estado técnico.'
WHERE estado='Pendiente de anticipo';
ALTER TABLE pedidos DROP CONSTRAINT IF EXISTS pedidos_estado_check;
ALTER TABLE pedidos ADD CONSTRAINT pedidos_estado_check CHECK (
    estado IN ('Solicitado','En revisión','En reparación','Listo','Entregado','Cancelado')
);

-- Eliminación permanente para operaciones futuras, conservando el historial.
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS eliminado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS eliminado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS servicio_descripcion TEXT;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS servicio_precio NUMERIC(10,2);

-- Completar únicamente campos ausentes con la información aún disponible.
-- El importe se recupera de la factura, nunca del precio actual del catálogo.
UPDATE facturas f SET servicio_descripcion = s.descripcion
FROM servicios s WHERE s.id_servicio = f.id_servicio AND f.servicio_descripcion IS NULL;
UPDATE facturas SET servicio_precio = COALESCE(subtotal, total)
WHERE servicio_precio IS NULL;

CREATE OR REPLACE FUNCTION snapshot_servicio_factura() RETURNS trigger AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM servicios WHERE id_servicio = NEW.id_servicio) THEN
    SELECT COALESCE(NEW.servicio_nombre, s.nombre),
           COALESCE(NEW.servicio_descripcion, s.descripcion)
    INTO NEW.servicio_nombre, NEW.servicio_descripcion
    FROM servicios s WHERE s.id_servicio = NEW.id_servicio;
    END IF;
    NEW.servicio_precio := COALESCE(NEW.servicio_precio, NEW.subtotal, NEW.total);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS snapshot_servicio_factura ON facturas;
CREATE TRIGGER snapshot_servicio_factura BEFORE INSERT ON facturas
FOR EACH ROW EXECUTE FUNCTION snapshot_servicio_factura();

-- Reemplazar reglas destructivas existentes aunque tengan nombres personalizados.
DO $$
DECLARE fk RECORD;
BEGIN
    FOR fk IN SELECT conrelid::regclass AS tabla, conname,
                     pg_get_constraintdef(oid) AS definicion
              FROM pg_constraint
              WHERE contype = 'f' AND confdeltype IN ('c', 'n')
                AND connamespace = current_schema()::regnamespace
                AND (conrelid IN ('facturas'::regclass, 'pedidos'::regclass)
                     OR confrelid IN ('pedidos'::regclass, 'facturas'::regclass))
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', fk.tabla, fk.conname);
        EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', fk.tabla, fk.conname,
            replace(replace(fk.definicion, 'ON DELETE CASCADE', 'ON DELETE RESTRICT'),
                    'ON DELETE SET NULL', 'ON DELETE RESTRICT'));
    END LOOP;
END $$;
