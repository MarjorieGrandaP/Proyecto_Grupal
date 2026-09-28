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
