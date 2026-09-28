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
