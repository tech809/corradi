-- CORRADI-BOT · empieza a registrar quién organiza cada oportunidad (asociación/entidad).
-- Solo para ir acumulando datos: de momento NO se expone en la API pública ni en el mapa.
-- Se rellena hacia adelante; las oportunidades ya existentes se quedan sin este dato salvo
-- revisión manual.

ALTER TABLE projects ADD COLUMN IF NOT EXISTS organiser_name TEXT;
