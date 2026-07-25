-- Registro de fichas de SALTO-YOUTH ya notificadas (app/scheduler/scrape_salto.py), para
-- no volver a avisar de la misma cada día. NO guarda las oportunidades en sí (esas solo
-- entran en "projects" si el coordinador reenvía el texto al bot y decide publicarlas).
CREATE TABLE IF NOT EXISTS salto_seen (
    url        TEXT PRIMARY KEY,
    found_at   TIMESTAMPTZ DEFAULT now()
);
