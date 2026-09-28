-- Migracion puntual de facturas emitidas antes del desglose de IVA y del registro de pagos.
-- Ejecutar despues de sql/migracion_pagos_iva_duracion.sql. Repetible y no procesa facturas nuevas.
CREATE TABLE IF NOT EXISTS pcfix_migraciones (
    nombre VARCHAR(100) PRIMARY KEY,
    aplicada_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pcfix_migraciones WHERE nombre='facturas_historicas_iva_15') THEN
        RETURN;
    END IF;

    UPDATE facturas
    SET subtotal = total,
        porcentaje_iva = 0.15,
        valor_iva = ROUND(total * 0.15, 2),
        total = total + ROUND(total * 0.15, 2),
        estado = 'Pagada',
        migracion_historica_iva = TRUE
    WHERE subtotal IS NULL AND porcentaje_iva IS NULL AND valor_iva IS NULL;

    UPDATE facturas
    SET estado='Pagada', migracion_historica_iva=TRUE
    WHERE NOT migracion_historica_iva;

    UPDATE pagos p
    SET estado='Rechazado',
        motivo_rechazo='Pendiente conciliado por la migración de facturas históricas.'
    WHERE p.estado='Pendiente'
      AND EXISTS (SELECT 1 FROM facturas f WHERE f.id_pedido=p.id_pedido AND f.migracion_historica_iva);

    -- La conciliación es explícita y no contiene comprobante ficticio.
    INSERT INTO pagos (
        id_pedido, tipo_pago, monto, estado, nombre_archivo, mime_type, contenido,
        migracion_historica, fecha_subida, fecha_confirmacion
    )
    SELECT f.id_pedido, 'total', f.total, 'Confirmado', NULL, NULL, NULL,
           TRUE, f.fecha::timestamp, f.fecha::timestamp
    FROM facturas f
    WHERE f.id_pedido IS NOT NULL
      AND f.total > 0
      AND f.migracion_historica_iva
      AND NOT EXISTS (SELECT 1 FROM pagos p WHERE p.id_pedido=f.id_pedido AND p.estado='Confirmado')
    ON CONFLICT DO NOTHING;

    INSERT INTO pcfix_migraciones(nombre) VALUES ('facturas_historicas_iva_15');
END;
$$;
