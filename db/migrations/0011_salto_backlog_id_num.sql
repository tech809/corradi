-- `salto_backlog` ahora también recibe el sobrante del escaneo diario (tope de
-- publicaciones directas por pasada, ver `scrape_salto.py` 2026-07-28), no solo el
-- backlog inicial vetado a mano. Ese sobrante SÍ tiene un id_num de `salto_ids` — al
-- publicarse por `publish_salto_backlog.py` hay que poder marcar ese id_num como
-- "published" (si no, se queda en "queued" para siempre y parecería sin resolver).
-- NULL para las filas del backlog inicial (no vinieron del escaneo por id_num).
ALTER TABLE salto_backlog ADD COLUMN IF NOT EXISTS id_num INTEGER;
