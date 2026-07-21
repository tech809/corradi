-- CORRADI-BOT · acceso abierto: sustituye la lista blanca por una lista de bloqueados.
-- Cualquiera puede escribir al bot por defecto; solo se bloquea explícitamente
-- (a mano por un admin, o automáticamente tras 2 mensajes seguidos que no son oportunidad).

CREATE TABLE IF NOT EXISTS blocked_users (
    telegram_user_id BIGINT PRIMARY KEY,
    reason           TEXT,          -- 'spam_auto' | 'manual' | ...
    blocked_by       BIGINT,        -- NULL si fue automático
    blocked_at       TIMESTAMPTZ DEFAULT now()
);
