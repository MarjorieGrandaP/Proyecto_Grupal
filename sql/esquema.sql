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
