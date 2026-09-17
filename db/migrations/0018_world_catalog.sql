-- Edición internacional de Corradi. Tablas deliberadamente separadas: ningún job o
-- endpoint de la edición española consulta estas filas por accidente.
CREATE TABLE IF NOT EXISTS world_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier TEXT UNIQUE NOT NULL,
    source_id INTEGER UNIQUE,
    source_url TEXT UNIQUE,
    hash TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT,
    topic TEXT,
    organiser_name TEXT,
    summary TEXT,
    raw_message TEXT NOT NULL,
    country_code TEXT,
    location TEXT,
    latitude NUMERIC(10, 8),
    longitude NUMERIC(11, 8),
    start_date DATE,
    end_date DATE,
    application_deadline DATE,
    deadline_estimated BOOLEAN NOT NULL DEFAULT FALSE,
    infopack_url TEXT,
    application_url TEXT,
    max_participants INTEGER,
    participant_min_age INTEGER,
    participant_max_age INTEGER,
    cost NUMERIC(10, 2),
    contact_information TEXT,
    detailed_description TEXT,
    programme_details TEXT,
    learning_outcomes TEXT,
    participant_profile TEXT,
    accommodation_details TEXT,
    covered_costs TEXT,
    travel_details TEXT,
    eligibility_countries TEXT,
    eligibility_country_codes TEXT[] NOT NULL DEFAULT '{}',
    eligibility_scope TEXT NOT NULL DEFAULT 'unknown'
        CHECK (eligibility_scope IN ('explicit', 'all_programme', 'neighbouring', 'unknown')),
    image_url TEXT,
    image_credit TEXT,
    image_source_url TEXT,
    image_origin TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'expired')),
    source TEXT NOT NULL DEFAULT 'salto',
    submitted_by_id BIGINT,
    telegram_message_id BIGINT,
    created TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_world_projects_open_deadline
    ON world_projects (application_deadline) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_world_projects_country ON world_projects (country_code);
CREATE INDEX IF NOT EXISTS idx_world_projects_eligibility
    ON world_projects USING GIN (eligibility_country_codes);

CREATE TABLE IF NOT EXISTS world_salto_ids (
    id_num INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    identifier TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_world_salto_retry
    ON world_salto_ids (id_num) WHERE status IN ('draft', 'error');

CREATE TABLE IF NOT EXISTS world_salto_scan_cursor (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_checked_id INTEGER NOT NULL
);
