-- CORRADI-BOT · esquema inicial (PostgreSQL 16 + pgvector)
-- Se ejecuta automáticamente en la primera inicialización del contenedor de Postgres.
-- Modelo de datos heredado y ampliado del PoC 'erasmusbot'.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier          TEXT UNIQUE,                 -- legible: CORRADI-2026-0001
    hash                TEXT UNIQUE NOT NULL,        -- dedup exacto: md5(title+country+start_date)

    title               TEXT NOT NULL,
    type                TEXT,                        -- YOUTH_EXCHANGE | TRAINING_COURSE | VOLUNTEERING | WORKSHOP
    topic               TEXT,
    summary             TEXT,
    raw_message         TEXT NOT NULL,

    country_code        TEXT,                        -- ISO 3166-1 alpha-2
    location            TEXT,
    latitude            NUMERIC(10, 8),
    longitude           NUMERIC(11, 8),

    start_date          DATE,
    end_date            DATE,
    application_deadline DATE,
    deadline_estimated  BOOLEAN DEFAULT FALSE,       -- TRUE si la deadline es el fallback (+N días)

    infopack_url        TEXT,
    application_url      TEXT,
    max_participants    INTEGER,
    participant_min_age INTEGER,
    participant_max_age INTEGER,
    cost                NUMERIC(10, 2),
    contact_information TEXT,

    status              TEXT DEFAULT 'open',         -- open | closed | expired
    source              TEXT,                        -- kosmos | gestor | ...
    submitted_by        TEXT,

    embedding           vector(768),                 -- dedup semántico (Gemini, 768 dims)
    published_telegram  BOOLEAN DEFAULT FALSE,
    handed_off_whatsapp BOOLEAN DEFAULT FALSE,

    created             TIMESTAMPTZ DEFAULT now(),
    updated             TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_status    ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_deadline  ON projects(application_deadline);
CREATE INDEX IF NOT EXISTS idx_projects_type      ON projects(type);
CREATE INDEX IF NOT EXISTS idx_projects_country   ON projects(country_code);
-- índice vectorial coseno (HNSW) para deduplicación / futuro RAG
CREATE INDEX IF NOT EXISTS idx_projects_embedding ON projects USING hnsw (embedding vector_cosine_ops);
