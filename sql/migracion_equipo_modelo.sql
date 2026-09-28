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
