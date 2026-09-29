-- Ejecutar después de migracion_eliminacion_logica.sql.
-- El bloque es atómico incluso si el cliente utiliza autocommit:
-- si existen duplicados no eliminados, falla sin retirar el índice anterior.
-- No modifica servicios ni documentos históricos.
DO $$
BEGIN
    DROP INDEX IF EXISTS servicios_nombre_normalizado_unique;
    CREATE UNIQUE INDEX IF NOT EXISTS servicios_nombre_normalizado_unique
        ON servicios (LOWER(BTRIM(nombre)))
        WHERE eliminado = FALSE;
END $$;
