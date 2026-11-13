-- Recuento agregado por hora desde el despliegue de esta migración.
-- No registra IP, sesión ni identificadores de visitante.
CREATE TABLE IF NOT EXISTS hourly_visits (
    hour TIMESTAMPTZ PRIMARY KEY,
    count INT NOT NULL DEFAULT 0
);
