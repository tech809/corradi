-- CORRADI-BOT · notificaciones push de la app móvil (Expo, iOS + Android)
--
-- La app no tiene cuentas: todo lo guarda en el móvil. Lo ÚNICO que vive en el servidor es
-- el token push anónimo de Expo y las preferencias del resumen diario. Se borra al
-- desactivar las notificaciones (POST /api/push/unregister) o cuando Expo responde que el
-- token ya no es válido (DeviceNotRegistered), ver app/scheduler/push_digest.py.

CREATE TABLE IF NOT EXISTS push_devices (
    token         TEXT PRIMARY KEY,
    platform      TEXT NOT NULL CHECK (platform IN ('ios', 'android')),
    -- Tipos de proyecto suscritos (YOUTH_EXCHANGE, TRAINING_COURSE, VOLUNTEERING). Vacío = todos.
    types         TEXT[] NOT NULL DEFAULT '{}',
    daily_digest  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Una fila por ejecución del resumen diario: `sent_at` marca el corte, y la siguiente
-- ejecución solo avisa de lo creado después ("nuevo desde el último resumen").
CREATE TABLE IF NOT EXISTS push_digest_runs (
    id             BIGSERIAL PRIMARY KEY,
    sent_at        TIMESTAMPTZ NOT NULL,
    project_count  INT NOT NULL DEFAULT 0,
    device_count   INT NOT NULL DEFAULT 0
);
