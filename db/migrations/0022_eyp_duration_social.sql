-- Duración normalizada para filtros ECS y momento real de entrada al flujo social.
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS duration_days INTEGER,
    ADD COLUMN IF NOT EXISTS duration_months NUMERIC(5, 1),
    ADD COLUMN IF NOT EXISTS social_published_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS projects_eyp_social_published_idx
    ON projects (social_published_at)
    WHERE source = 'eyp' AND social_published_at IS NOT NULL;
