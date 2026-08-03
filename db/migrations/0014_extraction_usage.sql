-- CORRADI-BOT · gasto REAL (no estimado) de la extracción de oportunidades contra Gemini,
-- acumulado por mes en curso (clave 'YYYY-MM'). Mismo patrón que chat_usage (0010), pero para
-- el otro consumidor de Gemini: cada mensaje que llega al bot Y cada ficha que escanea SALTO
-- pasan por app/llm/extractor.py, que hasta ahora no medía nada -- solo se medía el chat.
--
-- Sin `alerted`/tope de presupuesto a propósito: la extracción es el corazón del pipeline
-- (sin ella no se puede publicar nada), a diferencia del chat, que es una función extra que
-- sí tiene sentido pausar si se dispara el gasto.
CREATE TABLE IF NOT EXISTS extraction_usage (
    month     TEXT PRIMARY KEY,
    spent_usd NUMERIC(10, 6) NOT NULL DEFAULT 0,
    queries   INTEGER NOT NULL DEFAULT 0
);
