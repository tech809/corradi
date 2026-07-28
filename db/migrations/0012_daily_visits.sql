-- CORRADI-BOT · visitas por día (para el gráfico de línea de /estadisticas)
--
-- El contador `counters.visits` (0004_counters.sql) es acumulativo puro, sin fecha: sirve
-- para el pie de página del mapa pero no para dibujar una serie temporal. Esta tabla guarda
-- el desglose diario desde el día en que se despliega esta migración -- no hay forma de
-- reconstruir el histórico anterior, así que el gráfico empieza a tener datos reales a
-- partir de aquí (se documenta también en la propia UI).

CREATE TABLE IF NOT EXISTS daily_visits (
    day   DATE PRIMARY KEY,
    count INT NOT NULL DEFAULT 0
);
