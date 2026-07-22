-- CORRADI-BOT · contadores para la web (visitas + proyectos publicados histórico)

CREATE TABLE IF NOT EXISTS counters (
    key   TEXT PRIMARY KEY,
    value BIGINT NOT NULL DEFAULT 0
);

-- Visitas arranca en 0.
INSERT INTO counters (key, value) VALUES ('visits', 0) ON CONFLICT DO NOTHING;

-- 'published' es un contador histórico monótono (sobrevive a que una oportunidad expire
-- o se borre). Se siembra con las que ya están publicadas ahora mismo y a partir de ahí
-- lo incrementa el propio pipeline al publicar cada nueva.
INSERT INTO counters (key, value)
SELECT 'published', count(*) FROM projects WHERE published_telegram = TRUE
ON CONFLICT DO NOTHING;
