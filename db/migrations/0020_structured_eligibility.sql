ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS eligibility_country_codes TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS eligibility_scope TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_eligibility_scope_check;
ALTER TABLE projects ADD CONSTRAINT projects_eligibility_scope_check
    CHECK (eligibility_scope IN ('explicit', 'all_programme', 'neighbouring', 'unknown'));

CREATE INDEX IF NOT EXISTS projects_eligibility_country_codes_idx
    ON projects USING GIN (eligibility_country_codes);
