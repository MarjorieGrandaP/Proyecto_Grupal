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
