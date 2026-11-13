-- CORRADI-BOT · recibos de las notificaciones push de la app móvil (Expo)
--
-- Al enviar, Expo devuelve un «ticket» por mensaje; el resultado real (sobre todo
-- DeviceNotRegistered: app desinstalada o permisos quitados) llega después en el «recibo»,
-- que se consulta con getReceipts ~15 min más tarde y Expo solo guarda 24 h. Aquí se
-- apunta cada ticket aceptado con su token, para que app/scheduler/push_digest.py
-- (`--receipts-only`) consulte los recibos y dé de baja los tokens muertos. Las filas se
-- borran al procesarse, y cualquiera con más de 48 h se purga.

CREATE TABLE IF NOT EXISTS push_tickets (
    ticket_id   TEXT PRIMARY KEY,
    token       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS push_tickets_created_at_idx ON push_tickets (created_at);
