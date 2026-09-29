-- Eliminación permanente para operaciones futuras, conservando el historial.
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS eliminado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS eliminado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS servicio_descripcion TEXT;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS servicio_precio NUMERIC(10,2);

-- Completar únicamente campos ausentes con la información aún disponible.
-- El importe se recupera de la factura, nunca del precio actual del catálogo.
UPDATE facturas f SET servicio_descripcion = s.descripcion
FROM servicios s WHERE s.id_servicio = f.id_servicio AND f.servicio_descripcion IS NULL;
UPDATE facturas SET servicio_precio = COALESCE(subtotal, total)
WHERE servicio_precio IS NULL;

CREATE OR REPLACE FUNCTION snapshot_servicio_factura() RETURNS trigger AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM servicios WHERE id_servicio = NEW.id_servicio) THEN
    SELECT COALESCE(NEW.servicio_nombre, s.nombre),
           COALESCE(NEW.servicio_descripcion, s.descripcion)
    INTO NEW.servicio_nombre, NEW.servicio_descripcion
    FROM servicios s WHERE s.id_servicio = NEW.id_servicio;
    END IF;
    NEW.servicio_precio := COALESCE(NEW.servicio_precio, NEW.subtotal, NEW.total);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS snapshot_servicio_factura ON facturas;
CREATE TRIGGER snapshot_servicio_factura BEFORE INSERT ON facturas
FOR EACH ROW EXECUTE FUNCTION snapshot_servicio_factura();

-- Reemplazar reglas destructivas existentes aunque tengan nombres personalizados.
DO $$
DECLARE fk RECORD;
BEGIN
    FOR fk IN SELECT conrelid::regclass AS tabla, conname,
                     pg_get_constraintdef(oid) AS definicion
              FROM pg_constraint
              WHERE contype = 'f' AND confdeltype IN ('c', 'n')
                AND connamespace = current_schema()::regnamespace
                AND (conrelid IN ('facturas'::regclass, 'pedidos'::regclass)
                     OR confrelid IN ('pedidos'::regclass, 'facturas'::regclass))
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', fk.tabla, fk.conname);
        EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', fk.tabla, fk.conname,
            replace(replace(fk.definicion, 'ON DELETE CASCADE', 'ON DELETE RESTRICT'),
                    'ON DELETE SET NULL', 'ON DELETE RESTRICT'));
    END LOOP;
END $$;
