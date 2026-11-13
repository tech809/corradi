import { API_BASE } from './config';
import type { MapResponse, Opportunity } from './types';

/** Tiempo máximo de cualquier petición: con mala cobertura es mejor fallar y enseñar la caché. */
export const REQUEST_TIMEOUT_MS = 15_000;

export class TimeoutError extends Error {
  constructor(path: string) {
    super(`Tiempo de espera agotado en ${path}`);
    this.name = 'TimeoutError';
  }
}

/** fetch con límite de tiempo (AbortController). */
async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
  } catch (e) {
    if (controller.signal.aborted) throw new TimeoutError(path);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/** Respuesta HTTP no correcta. Sigue siendo un `Error` con el mismo mensaje de antes. */
export class HttpError extends Error {
  readonly status: number;
  constructor(status: number, path: string) {
    super(`HTTP ${status} en ${path}`);
    this.name = 'HttpError';
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await request(path, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new HttpError(res.status, path);
  return (await res.json()) as T;
}

function mapResults(data: MapResponse | null | undefined): Opportunity[] {
  if (!Array.isArray(data?.results)) throw new Error('Respuesta inesperada en /api/map');
  return data.results;
}

/** Todas las oportunidades abiertas (~200, ~1 MB sin comprimir; el servidor sirve gzip). */
export async function fetchOpenOpportunities(): Promise<Opportunity[]> {
  return mapResults(await getJson<MapResponse>('/api/map'));
}

export type ConditionalList =
  | { status: 'ok'; items: Opportunity[]; etag: string | null }
  /** 304: la lista no ha cambiado desde `etag`; se sigue usando la caché. */
  | { status: 'unchanged' };

/**
 * Como `fetchOpenOpportunities`, pero con `If-None-Match` si se le pasa el ETag de la última
 * lista: si el servidor contesta 304 no se descarga nada (`{ status: 'unchanged' }`).
 * Pasa `etag` solo si tienes la lista en caché (si no, un 304 te dejaría sin datos).
 * Al poner la cabecera a mano, NSURLSession (iOS) y OkHttp (Android) devuelven el 304 tal cual
 * en lugar de resolverlo con su caché (comportamiento documentado de ambos; sin comprobar aquí
 * en dispositivo).
 */
export async function fetchOpenOpportunitiesIfChanged(etag?: string | null): Promise<ConditionalList> {
  const path = '/api/map';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (etag) headers['If-None-Match'] = etag;
  const res = await request(path, { headers });
  if (res.status === 304) return { status: 'unchanged' };
  if (!res.ok) throw new HttpError(res.status, path);
  const items = mapResults((await res.json()) as MapResponse);
  return { status: 'ok', items, etag: res.headers.get('ETag') };
}

/** Ficha completa de una oportunidad (también las cerradas, para enlaces antiguos). */
export function fetchOpportunity(identifier: string): Promise<Opportunity> {
  return getJson<Opportunity>(`/opportunities/${encodeURIComponent(identifier)}`);
}

/** Petición POST JSON a la API de Corradi (la usan los avisos push). */
export async function postJson<T = unknown>(path: string, body: unknown): Promise<T> {
  const res = await request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new HttpError(res.status, path);
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}
