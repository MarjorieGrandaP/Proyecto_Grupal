-- Ejecutar después de las migraciones de pagos/IVA y eliminación lógica.
-- No se rellenan ni recalculan snapshots históricos. NULL significa no registrado.
CREATE TABLE IF NOT EXISTS configuracion_comercial (
    id_configuracion SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id_configuracion = 1),
    porcentaje_iva NUMERIC(5,2) NOT NULL CHECK (porcentaje_iva BETWEEN 0 AND 100),
    descuento_activo BOOLEAN NOT NULL DEFAULT FALSE,
    porcentaje_descuento NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (porcentaje_descuento BETWEEN 0 AND 100),
    fecha_inicio_descuento DATE,
    fecha_fin_descuento DATE,
    nombre_promocion VARCHAR(150),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_por INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    CHECK (fecha_inicio_descuento IS NULL OR fecha_fin_descuento IS NULL
           OR fecha_inicio_descuento <= fecha_fin_descuento)
);
-- La fila se crea al guardar por primera vez; hasta entonces se usa IVA_RATE.
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS porcentaje_descuento NUMERIC(5,4) CHECK (porcentaje_descuento BETWEEN 0 AND 1);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS valor_descuento NUMERIC(12,2) CHECK (valor_descuento >= 0);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS subtotal_con_descuento NUMERIC(12,2);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS nombre_promocion VARCHAR(150);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS servicio_nombre VARCHAR(100);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS servicio_descripcion TEXT;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS porcentaje_descuento NUMERIC(5,4) CHECK (porcentaje_descuento BETWEEN 0 AND 1);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS valor_descuento NUMERIC(12,2) CHECK (valor_descuento >= 0);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS subtotal_con_descuento NUMERIC(12,2);
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS nombre_promocion VARCHAR(150);

CREATE OR REPLACE FUNCTION auditar_configuracion_comercial() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO auditoria(tabla, operacion, id_registro, datos_anteriores, datos_nuevos, usuario_bd)
    VALUES ('configuracion_comercial', TG_OP, NEW.id_configuracion::text,
            CASE WHEN TG_OP = 'UPDATE' THEN to_jsonb(OLD) ELSE NULL END,
            to_jsonb(NEW), CURRENT_USER);
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS auditoria_configuracion_comercial ON configuracion_comercial;
CREATE TRIGGER auditoria_configuracion_comercial AFTER INSERT OR UPDATE ON configuracion_comercial
FOR EACH ROW EXECUTE FUNCTION auditar_configuracion_comercial();
