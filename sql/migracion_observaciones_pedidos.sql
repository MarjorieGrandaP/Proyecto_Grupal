-- Notas independientes: no alteran ni reemplazan transiciones anteriores.
CREATE TABLE IF NOT EXISTS observaciones_pedidos (
    id_observacion BIGSERIAL PRIMARY KEY,
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
    texto TEXT NOT NULL CHECK (length(btrim(texto)) BETWEEN 1 AND 2000),
    id_usuario_actor INTEGER REFERENCES usuarios(id_usuario),
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_observaciones_pedido ON observaciones_pedidos(id_pedido, fecha_hora, id_observacion);
