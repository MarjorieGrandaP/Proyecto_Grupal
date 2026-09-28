-- Biblioteca multimedia persistente, compatible con imágenes estáticas.
CREATE TABLE IF NOT EXISTS imagenes_servicio (
    id_imagen SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    mime_type VARCHAR(50) NOT NULL,
    contenido BYTEA NOT NULL,
    tamano_bytes INTEGER,
    hash_sha256 VARCHAR(64),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activa BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE UNIQUE INDEX IF NOT EXISTS imagenes_servicio_hash_unique ON imagenes_servicio(hash_sha256);
ALTER TABLE servicios ADD COLUMN IF NOT EXISTS id_imagen INTEGER;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='servicios_imagen_fk' AND conrelid='servicios'::regclass) THEN
        ALTER TABLE servicios ADD CONSTRAINT servicios_imagen_fk
        FOREIGN KEY (id_imagen) REFERENCES imagenes_servicio(id_imagen) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS servicios_imagen_idx ON servicios(id_imagen);
