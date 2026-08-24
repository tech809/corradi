-- Ficha editorial extensa: se muestra solo al abrir una oportunidad. Los campos se
-- extraen del anuncio y, cuando es legible, del infopack oficial.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS detailed_description TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS programme_details TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS learning_outcomes TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS participant_profile TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS accommodation_details TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS covered_costs TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS travel_details TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS eligibility_countries TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS infopack_enriched BOOLEAN NOT NULL DEFAULT FALSE;
