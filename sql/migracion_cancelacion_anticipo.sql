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
