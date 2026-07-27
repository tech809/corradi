-- CORRADI-BOT · cola de publicación en Instagram (feed + story), una fila por oportunidad.
-- No es un JSON en git (como el prototipo de tur-app): en Postgres se puede consultar,
-- reintentar y auditar sin depender de que el propio proceso de publicación reescriba un
-- fichero versionado.

CREATE TABLE IF NOT EXISTS instagram_posts (
    id             BIGSERIAL PRIMARY KEY,
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE UNIQUE,
    status         TEXT NOT NULL DEFAULT 'pending',   -- pending | published | failed
    attempts       INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT,
    media_id       TEXT,       -- id del post de feed en la Graph API
    story_media_id TEXT,
    created        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_instagram_posts_status ON instagram_posts(status);
