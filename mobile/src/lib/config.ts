/** Dominio público de Corradi. Todo lo que lee la app sale de aquí. */
export const API_BASE = 'https://mapa.proactivefuture.eu';

export const WEB_URLS = {
  home: `${API_BASE}/`,
  guia: `${API_BASE}/guia`,
  quienesSomos: `${API_BASE}/quienes-somos`,
  privacidad: `${API_BASE}/privacidad-app`,
  proyecto: (identifier: string) => `${API_BASE}/proyecto/${identifier}`,
  storyImage: (identifier: string) => `${API_BASE}/share/${identifier}/story.png`,
} as const;
