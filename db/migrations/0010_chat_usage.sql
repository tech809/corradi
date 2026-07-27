-- CORRADI-BOT · gasto REAL (no estimado) del chat del mapa contra Gemini, acumulado por mes
-- en curso (clave 'YYYY-MM'). Alimentado por app/llm/chat.py a partir de `usage_metadata` de
-- cada respuesta de Gemini (docs/chatbot_mapa.md, decisión del usuario en §8.3).
--
-- `alerted` evita mandar el aviso de "presupuesto agotado" (Telegram, app/alerts.py) más de
-- una vez por mes: se marca a TRUE la primera vez que se cruza CHAT_MONTHLY_BUDGET_USD y no
-- se vuelve a avisar hasta que cambie la clave `month`.
CREATE TABLE IF NOT EXISTS chat_usage (
    month     TEXT PRIMARY KEY,
    spent_usd NUMERIC(10, 6) NOT NULL DEFAULT 0,
    queries   INTEGER NOT NULL DEFAULT 0,
    alerted   BOOLEAN NOT NULL DEFAULT FALSE
);
