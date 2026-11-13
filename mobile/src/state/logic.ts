/**
 * Lógica pura del estado (sin React, sin almacenamiento, sin APIs nativas), para poder probarla
 * aparte. La usa src/state/opportunities.tsx (y reminders.ts para el plan del aviso).
 *
 * REGLA: este fichero (y lo que importa: lib/format.ts → lib/types.ts) no puede importar nada de
 * React Native, Expo ni React. Lo comprueba y prueba `node scripts/check-logic.mjs` (Node ≥22.18,
 * que quita los tipos de TypeScript sin instalar nada).
 */
import { parseDay } from '@/lib/format';
import type { Opportunity } from '@/lib/types';

const DAY_MS = 86_400_000;

/** En la primera apertura solo cuenta como "nuevo" lo dado de alta en estos días. */
export const FIRST_RUN_NEW_DAYS = 2;
/** Si en la primera apertura no hay nada de esos días, se enseñan como nuevos los N más recientes. */
export const FIRST_RUN_FALLBACK_NEW = 10;
/** La "primera visita" (texto de bienvenida en Nuevos) dura al menos esto desde la primera carga. */
export const FIRST_VISIT_MS = DAY_MS;

/** Instante (ms) antes del cual lo dado de alta cuenta como visto en la primera carga. */
export function firstRunCutoff(now: number, days: number = FIRST_RUN_NEW_DAYS): number {
  return now - days * DAY_MS;
}

/**
 * Primera carga: se da por visto lo anterior al corte (o sin fecha de alta). Devuelve un conjunto
 * nuevo con `seen` + esos ids; `seen` no se modifica.
 *
 * `fallbackNew` (por defecto 0 = sin respaldo): si así no queda NADA nuevo, se dejan sin ver los
 * `fallbackNew` más recientes por `created` (los que no estaban ya en `seen`), para que la
 * primera apertura nunca enseñe "¡Todo visto!".
 *
 * Casos (now = 2026-11-13T12:00Z, days = 2):
 * - a creado el 12-nov, b el 1-nov, c sin fecha → visto {b, c}; nuevo a.
 * - todos de octubre, fallbackNew = 2 → nuevos los 2 más recientes; el resto, visto.
 * - todos de octubre, fallbackNew = 0 → todo visto (comportamiento antiguo).
 * - `seen` de entrada se conserva siempre (no se "desve" nada que ya estuviera visto).
 */
export function seenAfterFirstRun(
  items: readonly Pick<Opportunity, 'identifier' | 'created'>[],
  seen: ReadonlySet<string>,
  now: number,
  days: number = FIRST_RUN_NEW_DAYS,
  fallbackNew = 0,
): Set<string> {
  const cutoff = firstRunCutoff(now, days);
  const next = new Set(seen);
  for (const o of items) {
    const created = o.created ? Date.parse(o.created) : NaN;
    if (!Number.isFinite(created) || created < cutoff) next.add(o.identifier);
  }
  if (fallbackNew > 0 && items.every((o) => next.has(o.identifier))) {
    const recent = items
      .filter((o) => !seen.has(o.identifier))
      .slice()
      .sort((a, b) => (b.created ?? '').localeCompare(a.created ?? ''))
      .slice(0, fallbackNew);
    for (const o of recent) next.delete(o.identifier);
  }
  return next;
}

/**
 * Vistos leídos del almacenamiento + lo marcado mientras se leía, menos lo que se pidió volver a
 * enseñar como nuevo antes de terminar de leer (`pendingUnsee`, p. ej. al abrir desde el aviso).
 * Casos: stored {a,b}, current {c}, pending {b} → {a, c}.
 */
export function hydrateSeen(
  stored: Iterable<string>,
  current: ReadonlySet<string>,
  pendingUnsee: ReadonlySet<string>,
): Set<string> {
  const merged = mergeSeen(stored, current);
  pendingUnsee.forEach((id) => merged.delete(id));
  return merged;
}

/**
 * Pone primero los de `first` (en el orden de `items`) y después el resto, sin repetir.
 * Casos: items [a,b,c,d], first {c,a} → [a,c,b,d]; first vacío → items tal cual.
 */
export function orderFirst<T extends Pick<Opportunity, 'identifier'>>(items: readonly T[], first: ReadonlySet<string>): T[] {
  if (first.size === 0) return [...items];
  const head: T[] = [];
  const tail: T[] = [];
  for (const o of items) (first.has(o.identifier) ? head : tail).push(o);
  return [...head, ...tail];
}

/**
 * Guardados que ya no están en la lista de abiertos y cuya ficha guardada sigue diciendo
 * "abierto" (o no hay ficha): hay que volver a pedirlos para saber si cerraron.
 * `checked` = ya pedidos en esta sesión (no se repiten). Como mucho `limit`.
 * Casos: saved [a,b,c], lista {a}, fichas {b: abierta}, c sin ficha → [b, c];
 * con fichas {b: cerrada} → [c]; con checked {c} → [b].
 */
export function savedToRecheck(
  savedIds: Iterable<string>,
  listIds: ReadonlySet<string>,
  records: Readonly<Record<string, Pick<Opportunity, 'status' | 'application_deadline'> | undefined>>,
  isClosed: (o: Pick<Opportunity, 'status' | 'application_deadline'>) => boolean,
  checked: ReadonlySet<string> = new Set(),
  limit = 10,
): string[] {
  const out: string[] = [];
  for (const id of savedIds) {
    if (out.length >= limit) break;
    if (listIds.has(id) || checked.has(id)) continue;
    const rec = records[id];
    if (!rec || !isClosed(rec)) out.push(id);
  }
  return out;
}

/** ¿Se acaba la "primera visita" en esta descarga? (≥24 h desde la primera carga). */
export function firstVisitExpired(firstRunAt: number | null, now: number, minMs: number = FIRST_VISIT_MS): boolean {
  return firstRunAt != null && now - firstRunAt >= minMs;
}

/**
 * Une lo leído del almacenamiento con lo marcado mientras se leía (nunca se pierde nada).
 * Devuelve un conjunto nuevo. Caso: stored [a], current {b} → {a, b}.
 */
export function mergeSeen(stored: Iterable<string>, current: ReadonlySet<string>): Set<string> {
  const merged = new Set(stored);
  current.forEach((id) => merged.add(id));
  return merged;
}

/**
 * Lista de vistos a persistir: solo los ids que siguen en la lista. Si la lista está vacía (aún
 * no se sabe), se conserva todo. Casos: seen {a,z}, items [a,b] → [a]; items [] → [a, z].
 */
export function pruneSeen(seen: ReadonlySet<string>, items: readonly Pick<Opportunity, 'identifier'>[]): string[] {
  if (items.length === 0) return [...seen];
  const present = new Set(items.map((o) => o.identifier));
  return [...seen].filter((id) => present.has(id));
}

/** Nuevos = de la lista y no vistos (mismo orden que la lista). */
export function unseenItems<T extends Pick<Opportunity, 'identifier'>>(items: readonly T[], seen: ReadonlySet<string>): T[] {
  return items.filter((o) => !seen.has(o.identifier));
}

// ---------- Aviso de plazo ----------

export const REMINDER_HOUR = 10;
/** Días antes del plazo en los que se intenta avisar, por orden de preferencia. */
export const REMINDER_DAYS_BEFORE: readonly number[] = [3, 1, 0];

export type ReminderPlan = { ok: true; fireAt: Date; daysBefore: number } | { ok: false; reason: string };

/**
 * Cuándo saltaría el aviso de plazo (a las 10:00, 3 días antes; si ya es tarde, 1 día antes o la
 * misma mañana), o por qué no se puede poner. Sin comprobación de plataforma (ver reminders.ts).
 * Casos (now = 13-nov 09:00): plazo 20-nov → 17-nov 10:00 (3 días); plazo 14-nov → 13-nov 10:00
 * (1 día); plazo 13-nov → hoy 10:00 (0 días); plazo 12-nov → "El plazo ya ha pasado.";
 * status 'closed' → cerrada; sin plazo → "Aún no sabemos la fecha límite…".
 */
export function planReminder(
  o: Pick<Opportunity, 'status' | 'application_deadline'>,
  now: Date = new Date(),
): ReminderPlan {
  if (o.status && o.status !== 'open') return { ok: false, reason: 'Esta convocatoria ya está cerrada.' };
  const deadline = parseDay(o.application_deadline);
  if (!deadline) return { ok: false, reason: 'Aún no sabemos la fecha límite, así que no podemos avisarte.' };
  for (const daysBefore of REMINDER_DAYS_BEFORE) {
    const fireAt = new Date(deadline.getFullYear(), deadline.getMonth(), deadline.getDate() - daysBefore, REMINDER_HOUR, 0, 0);
    if (fireAt.getTime() > now.getTime() + 60_000) return { ok: true, fireAt, daysBefore };
  }
  const closedAlready = deadline.getTime() < new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12).getTime();
  return {
    ok: false,
    reason: closedAlready ? 'El plazo ya ha pasado.' : 'Cierra hoy: ya no da tiempo a avisarte, ¡apúntate ya!',
  };
}
