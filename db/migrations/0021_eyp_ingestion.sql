-- Trazabilidad de oportunidades importadas del Portal Europeo de la Juventud (EYP).
-- `publication_scope = web` separa el catálogo web del flujo editorial multicanal.
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS source_external_id TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS source_checked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS application_deadline_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS publication_scope TEXT NOT NULL DEFAULT 'all';

ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_publication_scope_check;
ALTER TABLE projects ADD CONSTRAINT projects_publication_scope_check
    CHECK (publication_scope IN ('all', 'web'));

CREATE UNIQUE INDEX IF NOT EXISTS projects_source_external_id_unique
    ON projects (source, source_external_id)
    WHERE source IS NOT NULL AND source_external_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS projects_source_checked_at_idx
    ON projects (source, source_checked_at);
