-- Amplía el embudo anónimo de producto. Solo se guardan recuentos por proyecto y día.
ALTER TABLE project_interactions DROP CONSTRAINT IF EXISTS project_interactions_kind_check;
ALTER TABLE project_interactions ADD CONSTRAINT project_interactions_kind_check
    CHECK (kind IN (
        'view', 'info', 'form', 'infopack', 'save', 'compare',
        'calendar', 'application', 'assistant'
    ));
