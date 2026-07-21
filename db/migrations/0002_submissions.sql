-- CORRADI-BOT · tracking de envíos (anti-abuso) + enlace directo al post del canal

ALTER TABLE projects ADD COLUMN IF NOT EXISTS submitted_by_id BIGINT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS telegram_message_id BIGINT;

-- Registra TODO intento de envío (oportunidad creada, duplicada, no-oportunidad, error,
-- límite diario superado...). Es la base del límite de 3/día y del auto-bloqueo por spam.
CREATE TABLE IF NOT EXISTS submissions (
    id               BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    status           TEXT NOT NULL,   -- created | duplicate | duplicate_similar | not_opportunity | rate_limited | error
    project_id       UUID REFERENCES projects(id),
    created          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_submissions_user_created ON submissions(telegram_user_id, created);
