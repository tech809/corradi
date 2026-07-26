-- Escaneo de IDs secuenciales de SALTO-YOUTH (app/scheduler/scrape_salto.py) — sustituye
-- al enfoque por listado paginado (que usaba `salto_seen`, ver migración 0005).

-- Resultado de cada ID probado: 'draft' (aún no público, se reintenta), 'not_relevant'
-- (filtro barato: no es Training Course o no admite España), o el status que devuelva
-- pipeline.preview()/commit() ('not_opportunity', 'expired', 'deadline_too_far',
-- 'duplicate', 'duplicate_similar', 'published', 'error').
CREATE TABLE IF NOT EXISTS salto_ids (
    id_num       INTEGER PRIMARY KEY,
    status       TEXT NOT NULL,
    identifier   TEXT,
    checked_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_salto_ids_draft ON salto_ids (id_num) WHERE status = 'draft';

-- Cursor de una sola fila: hasta qué id_num se ha probado (exista o no), para que el
-- escaneo del día siguiente continúe justo donde se quedó en vez de repetir el rango ya
-- confirmado como "todavía no existe".
CREATE TABLE IF NOT EXISTS salto_scan_cursor (
    id                SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_checked_id   INTEGER NOT NULL
);
