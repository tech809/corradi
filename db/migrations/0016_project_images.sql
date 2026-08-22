-- Imagen editorial con procedencia visible. Nunca se guarda una foto sin conservar su
-- fuente/crédito: puede venir de una organización o del proveedor de stock configurado.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS image_credit TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS image_source_url TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS image_origin TEXT;
