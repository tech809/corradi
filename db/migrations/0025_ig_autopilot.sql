-- Piloto automático de Instagram (app/ig_auto, app/scheduler/ig_autopilot.py).
-- Una fila por publicación planificada: qué tipo, cuándo, con qué variantes de experimento,
-- su resultado y sus métricas. (kind, slot_date) único: el plan de un día es idempotente.
CREATE TABLE IF NOT EXISTS ig_autopilot (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT NOT NULL,           -- carousel_opp | reel_opp | guide | lastcall | reel_lastcall
    slot_date     DATE NOT NULL,
    planned_at    TIMESTAMPTZ NOT NULL,
    project_id    UUID REFERENCES projects(id) ON DELETE SET NULL,
    ref           TEXT,                    -- clave de guía u otra referencia
    variant       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status        TEXT NOT NULL DEFAULT 'planned',  -- planned | published | skipped | failed
    attempts      INT NOT NULL DEFAULT 0,
    media_id      TEXT,
    permalink     TEXT,
    published_at  TIMESTAMPTZ,
    error         TEXT,
    metrics       JSONB,
    metrics_at    TIMESTAMPTZ,
    score         DOUBLE PRECISION,
    created       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kind, slot_date)
);
CREATE INDEX IF NOT EXISTS ig_autopilot_due_idx ON ig_autopilot (status, planned_at);

-- Seguidores por día, para medir el crecimiento.
CREATE TABLE IF NOT EXISTS ig_account_daily (
    day        DATE PRIMARY KEY,
    followers  INT NOT NULL,
    media      INT
);
