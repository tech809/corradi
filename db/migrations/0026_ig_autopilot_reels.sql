-- Reels por oportunidad (kind='reel_project') y piezas sueltas (kind='pinned_intro'):
-- puede haber varias el mismo día, así que la unicidad (kind, slot_date) pasa a ser
-- solo para los huecos del calendario.
ALTER TABLE ig_autopilot DROP CONSTRAINT IF EXISTS ig_autopilot_kind_slot_date_key;
CREATE UNIQUE INDEX IF NOT EXISTS ig_autopilot_slot_uniq ON ig_autopilot (kind, slot_date)
    WHERE kind NOT IN ('reel_project', 'pinned_intro');
