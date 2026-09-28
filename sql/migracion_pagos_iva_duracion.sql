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
-- Las facturas anteriores mantienen total y tarifa NULL: IVA histórico no desglosado.
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
