-- Separar los intentos reservados de las publicaciones confirmadas.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS social_reserved_at TIMESTAMPTZ;
