-- Cola temporal para publicar de forma programada el backlog inicial de oportunidades de
-- SALTO-YOUTH (2026-07-25/26, ver memoria del proyecto) — 3 veces al día durante unos
-- días. Una vez vaciada la cola, esta tabla puede borrarse (era solo para esta tanda).
CREATE TABLE IF NOT EXISTS salto_backlog (
    id                    SERIAL PRIMARY KEY,
    url                   TEXT NOT NULL,
    fields                JSONB NOT NULL,
    scheduled_at          TIMESTAMPTZ NOT NULL,
    published_identifier  TEXT,
    created_at            TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_salto_backlog_pending
    ON salto_backlog (scheduled_at) WHERE published_identifier IS NULL;
