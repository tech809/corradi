-- Interacciones anónimas por oportunidad y día para el Top 3 semanal.
-- No guarda IP, usuario, sesión ni ningún identificador del visitante.
CREATE TABLE IF NOT EXISTS project_interactions (
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    day DATE NOT NULL DEFAULT current_date,
    kind TEXT NOT NULL CHECK (kind IN ('view', 'info', 'form', 'infopack')),
    count INTEGER NOT NULL DEFAULT 0 CHECK (count >= 0),
    PRIMARY KEY (project_id, day, kind)
);

CREATE INDEX IF NOT EXISTS idx_project_interactions_day
    ON project_interactions(day DESC);
