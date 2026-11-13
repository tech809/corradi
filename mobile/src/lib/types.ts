/**
 * Oportunidad tal como la devuelve la API (`_serialize` / `_serialize_map` en
 * app/api/main.py). Casi todo puede venir a null: la extracción no siempre encuentra el dato.
 * Las fechas son ISO ("2026-11-13") o null.
 */
/** Los tres únicos formatos (app/domain/project_type.py). VOLUNTEERING = Cuerpo Europeo de Solidaridad. */
export type OpportunityType = 'YOUTH_EXCHANGE' | 'TRAINING_COURSE' | 'VOLUNTEERING';

/** Orden canónico para filtros, leyendas y listas de tipos. */
export const OPPORTUNITY_TYPES: readonly OpportunityType[] = ['YOUTH_EXCHANGE', 'TRAINING_COURSE', 'VOLUNTEERING'];

export const TYPE_LABELS: Record<OpportunityType, string> = {
  YOUTH_EXCHANGE: 'Intercambio juvenil',
  TRAINING_COURSE: 'Curso de formación',
  VOLUNTEERING: 'Voluntariado europeo',
};

/** Etiqueta corta para chips, filtros y leyenda del mapa. */
export const TYPE_SHORT_LABELS: Record<OpportunityType, string> = {
  YOUTH_EXCHANGE: 'Intercambio',
  TRAINING_COURSE: 'Curso',
  VOLUNTEERING: 'Voluntariado',
};

/** Qué es cada formato, en una frase para quien no conoce Erasmus+. */
export const TYPE_EXPLAINERS: Record<OpportunityType, string> = {
  YOUTH_EXCHANGE:
    'Entre 5 y 21 días con jóvenes de varios países, con talleres y actividades sobre un tema. Alojamiento y comida pagados; el viaje se reembolsa hasta un límite.',
  TRAINING_COURSE:
    'Formación de unos días para personas que trabajan o colaboran con jóvenes: monitores, educadores, voluntarios de asociaciones. Suele ser gratis, con el viaje reembolsado hasta un límite.',
  VOLUNTEERING:
    'Vives de 2 semanas a 12 meses en otro país colaborando con una organización. Te cubren viaje, alojamiento, comida, seguro y dinero de bolsillo. De 18 a 30 años.',
};

export interface Opportunity {
  identifier: string; // "CORRADI-2026-0731"
  last_minute?: boolean | null; // etiqueta "Última llamada" de la web
  approx_location?: boolean | null; // true = coordenadas solo a nivel de país
  title: string;
  type: OpportunityType | null;
  topic: string | null;
  organiser_name: string | null;
  summary: string | null;
  country_code: string | null;
  location: string | null;
  latitude: number | null;
  longitude: number | null;
  start_date: string | null;
  end_date: string | null;
  application_deadline: string | null;
  deadline_estimated: boolean | null;
  infopack_url: string | null;
  application_url: string | null;
  participant_min_age: number | null;
  participant_max_age: number | null;
  cost: number | string | null; // la API lo manda como número (0.0, 300.0)
  contact_information: string | null;
  detailed_description: string | null;
  programme_details: string | null;
  learning_outcomes: string | null;
  participant_profile: string | null;
  accommodation_details: string | null;
  covered_costs: string | null;
  travel_details: string | null;
  eligibility_countries: string | null;
  /** Códigos de país admitidos (UE: "EL" = Grecia). null o vacío = no se sabe. */
  eligibility_country_codes: string[] | null;
  image_url: string | null;
  image_credit: string | null;
  source_url: string | null;
  source_checked_at?: string | null; // última comprobación en la fuente (ISO)
  channel_url?: string | null; // mensaje original en el canal de Telegram
  duration_months: number | null;
  status: string | null;
  created: string | null; // alta en Corradi, ISO con hora: "2026-10-08T10:17:08+00:00"
  updated: string | null;
  // La API puede añadir campos; no romper por ello.
  [key: string]: unknown;
}

export interface MapResponse {
  count: number;
  located: number;
  unlocated: number;
  generated: string;
  results: Opportunity[];
}
