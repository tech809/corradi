-- Un aviso de token inválido al día y por credencial, aunque el bot y cron fallen a la vez.
-- Solo se guarda una huella irreversible del token; nunca el secreto.
CREATE TABLE IF NOT EXISTS instagram_auth_alerts (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
    token_fingerprint TEXT NOT NULL,
    last_sent TIMESTAMPTZ NOT NULL DEFAULT now()
);
