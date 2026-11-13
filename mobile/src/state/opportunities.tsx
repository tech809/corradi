/**
 * Estado compartido de la app: la lista de proyectos abiertos, lo visto, lo guardado y los avisos.
 *
 * - La lista se descarga entera (/api/map), se ordena por alta (`created`) y se guarda en un
 *   fichero (solo si ha cambiado) junto con su ETag. Al arrancar se pinta la caché y se pide la
 *   versión fresca con `If-None-Match`: un 304 deja la caché como está.
 * - Nada se escribe en el almacenamiento antes de terminar de leerlo (hidratación): las acciones
 *   de guardar y las recargas esperan a la lectura, y lo marcado antes (vistos, "volver a enseñar
 *   como nuevo") se une a lo leído y se escribe una sola vez.
 * - `seen` (vistos) y `saved` (guardados) viven en AsyncStorage. Las escrituras de vistos se
 *   agrupan (500 ms) y se podan a los ids que siguen en la lista.
 * - Las fichas completas de los guardados (`savedRecords`) se guardan en fichero para poder
 *   enseñar Guardados sin conexión, y se actualizan con cada descarga.
 * - Guardar programa el aviso de plazo (reminders.ts); quitar de guardados lo cancela.
 *
 * El estado se reparte en TRES contextos para no repintar de más:
 * - datos (`useOpportunityData`): lista, carga, error, `refresh`, `getById`;
 * - vistos (`useSeenState`): nuevos, primera visita, marcar como visto;
 * - guardados (`useSavedState`): guardados, fichas guardadas, avisos.
 * Así abrir una ficha (markSeen) no repinta Explorar ni el mapa. `useOpportunities()` sigue
 * devolviendo la unión de los tres (compatibilidad), pero se repinta con cualquier cambio.
 * La lógica pura (primera carga, unir/podar vistos, plan del aviso) está en ./logic.ts.
 */
import { createContext, type Context, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AppState } from 'react-native';

import { HttpError, fetchOpenOpportunitiesIfChanged, fetchOpportunity } from '@/lib/api';
import { isClosed } from '@/lib/format';
import { usePushPrefs } from '@/lib/push';
import {
  cancelReminder,
  getReminderIds,
  scheduleReminder,
  subscribeReminders,
  syncReminders,
  toggleReminder,
  type ToggleReminderResult,
} from '@/lib/reminders';
import { readFileJson, readJson, removeKey, writeFileJson, writeJson } from '@/lib/storage';
import type { Opportunity } from '@/lib/types';

import {
  FIRST_RUN_FALLBACK_NEW,
  FIRST_RUN_NEW_DAYS,
  firstVisitExpired,
  hydrateSeen,
  pruneSeen,
  savedToRecheck,
  seenAfterFirstRun,
  unseenItems,
} from './logic';

/** Datos con más de esto se consideran viejos (recarga al volver; `checking` al refrescar). */
const STALE_MS = 10 * 60 * 1000;
/** Agrupa las escrituras de "vistos". */
const SEEN_WRITE_DELAY_MS = 500;
/** Guardados que se vuelven a pedir como mucho en cada descarga (los que dejaron la lista). */
const RECHECK_LIMIT = 10;

export type SaveReminderOutcome = 'set' | 'already' | 'denied' | 'unavailable' | 'none' | 'cancelled';
export interface ToggleSavedResult {
  saved: boolean;
  reminder: SaveReminderOutcome;
}
/** Resultado del control de aviso de la ficha (`useReminder().toggle()`). */
export type ToggleResult = ToggleReminderResult;

/** Lista y estado de la descarga. */
export interface OpportunityDataState {
  /** Abiertas, de más reciente a más antigua (por `created`). */
  items: Opportunity[];
  /** Primera carga sin caché. */
  loading: boolean;
  refreshing: boolean;
  /** Hay una recarga en curso y los datos tienen más de 10 min (o no hay datos). */
  checking: boolean;
  error: string | null;
  lastUpdated: number | null;
  refresh: () => Promise<void>;
  getById: (identifier: string) => Opportunity | undefined;
}

/** Vistos / nuevos. */
export interface SeenState {
  /** Las que aún no se han visto (todas las de la lista, sin filtrar por intereses). */
  newItems: Opportunity[];
  /** Ids vistos (incluye los que ya no están en la lista). */
  seenIds: ReadonlySet<string>;
  /**
   * Primera visita: true hasta "Ya los he visto" o hasta la primera descarga hecha al menos 24 h
   * después de la primera carga.
   */
  isFirstVisit: boolean;
  /** Marca todo como visto y devuelve una función que lo deshace. */
  markAllSeen: () => () => void;
  markSeen: (identifier: string) => void;
  /** Vuelve a mostrar estos ids como nuevos (al abrir desde el aviso diario). */
  showAsNew: (ids: string[]) => void;
}

/** Guardados y avisos de plazo. */
export interface SavedState {
  savedIds: Set<string>;
  /** Ficha completa de cada guardado (persistida; se refresca si está en la última lista). */
  savedRecords: Record<string, Opportunity>;
  /** Proyectos con aviso de plazo pendiente (null mientras se lee). */
  reminderIds: ReadonlySet<string> | null;
  /**
   * Guarda o quita. Guardar programa el aviso de plazo (pidiendo permiso una sola vez);
   * quitar lo cancela. `record` es opcional: si no, se busca en la lista o se descarga.
   */
  toggleSaved: (identifier: string, record?: Opportunity) => Promise<ToggleSavedResult>;
  /**
   * Fija el estado (sin alternar): `setSaved(id, true, record)` guarda si no lo estaba;
   * `setSaved(id, false)` lo quita si lo estaba. Si ya está así, no hace nada
   * (`reminder: 'none'`). Úsalo para "Deshacer".
   */
  setSaved: (identifier: string, saved: boolean, record?: Opportunity) => Promise<ToggleSavedResult>;
  /** Uso interno de `useReminder`. */
  toggleReminderFor: (identifier: string) => Promise<ToggleResult>;
}

/** Todo junto (compatibilidad). Prefiere los hooks estrechos. */
export type OpportunitiesState = OpportunityDataState & SeenState & SavedState;

const DataCtx = createContext<OpportunityDataState | null>(null);
const SeenCtx = createContext<SeenState | null>(null);
const SavedCtx = createContext<SavedState | null>(null);

interface CachedList {
  at: number;
  sig: string;
  items: Opportunity[];
  /** ETag de /api/map para pedir la siguiente con If-None-Match (versiones antiguas: sin él). */
  etag?: string | null;
}

/** Promesa que se resuelve desde fuera (fin de la hidratación). */
function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve: () => void = () => {};
  const promise = new Promise<void>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function byCreatedDesc(a: Opportunity, b: Opportunity): number {
  return (b.created ?? '').localeCompare(a.created ?? '');
}

/** Firma barata de la lista (djb2 sobre id + actualizado + plazo + estado) para no reescribir igual. */
function listSignature(items: readonly Opportunity[]): string {
  let h = 5381;
  for (const o of items) {
    const s = `${o.identifier}|${o.updated ?? ''}|${o.application_deadline ?? ''}|${o.status ?? ''};`;
    for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return `${items.length}:${(h >>> 0).toString(36)}`;
}

function sameRecord(a: Opportunity | undefined, b: Opportunity): boolean {
  return !!a && a.updated === b.updated && a.application_deadline === b.application_deadline && a.status === b.status;
}

export function OpportunitiesProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [seen, setSeen] = useState<Set<string>>(() => new Set());
  const [savedIds, setSavedIds] = useState<Set<string>>(() => new Set());
  const [savedRecords, setSavedRecords] = useState<Record<string, Opportunity>>({});
  const [reminderIds, setReminderIds] = useState<ReadonlySet<string> | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [isFirstVisit, setIsFirstVisit] = useState(false);

  // Fuente de verdad síncrona (los estados de arriba son su reflejo para pintar).
  const itemsRef = useRef<Opportunity[]>([]);
  const seenRef = useRef<Set<string>>(new Set());
  const savedRef = useRef<Set<string>>(new Set());
  const recordsRef = useRef<Record<string, Opportunity>>({});
  const lastUpdatedRef = useRef<number | null>(null);
  const sigRef = useRef<string | null>(null);
  const firstRunAtRef = useRef<number | null>(null);
  const firstVisitRef = useRef(false);
  const hydratedRef = useRef(false);
  const [hydration] = useState(deferred);
  const etagRef = useRef<string | null>(null);
  /** Ids que se pidió enseñar como nuevos antes de leer los vistos (se aplican tras leerlos). */
  const pendingUnseeRef = useRef<Set<string>>(new Set());
  /** Guardados ya vueltos a pedir en esta sesión (no se repiten). */
  const recheckedRef = useRef<Set<string>>(new Set());
  const savedDirtyRef = useRef(false);
  const recordsDirtyRef = useRef(false);
  const seenDirtyRef = useRef(false);
  const seenTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflightRef = useRef<Promise<void> | null>(null);

  // ---------- Vistos ----------

  const flushSeen = useCallback(() => {
    if (seenTimerRef.current) {
      clearTimeout(seenTimerRef.current);
      seenTimerRef.current = null;
    }
    if (!seenDirtyRef.current || !hydratedRef.current) return;
    seenDirtyRef.current = false;
    void writeJson('seen', pruneSeen(seenRef.current, itemsRef.current));
  }, []);

  const commitSeen = useCallback(
    (next: Set<string>) => {
      seenRef.current = next;
      setSeen(next);
      seenDirtyRef.current = true;
      if (seenTimerRef.current) clearTimeout(seenTimerRef.current);
      seenTimerRef.current = setTimeout(flushSeen, SEEN_WRITE_DELAY_MS);
    },
    [flushSeen],
  );

  const endFirstVisit = useCallback(() => {
    if (!firstVisitRef.current) return;
    firstVisitRef.current = false;
    setIsFirstVisit(false);
    void writeJson('firstVisitDone', true);
  }, []);

  // ---------- Guardados ----------

  // Antes de leer el almacenamiento no se escribe nada (se pisaría lo guardado): se marca y se
  // escribe una vez al terminar de leer.
  const commitSaved = useCallback((next: Set<string>) => {
    savedRef.current = next;
    setSavedIds(next);
    if (hydratedRef.current) void writeJson('saved', [...next]);
    else savedDirtyRef.current = true;
  }, []);

  const commitRecords = useCallback((next: Record<string, Opportunity>) => {
    recordsRef.current = next;
    setSavedRecords(next);
    if (hydratedRef.current) void writeFileJson('savedRecords', next);
    else recordsDirtyRef.current = true;
  }, []);

  /**
   * Actualiza las fichas guardadas con la lista fresca. Los guardados que ya no están en la lista
   * y cuya ficha aún dice "abierto" (o no tienen ficha) se vuelven a pedir (como mucho 10 por
   * descarga, una vez por sesión): así Guardados sabe que cerraron. Si el servidor ya no lo
   * tiene (404), la ficha guardada se marca cerrada.
   */
  const refreshSavedRecords = useCallback(
    async (fresh: readonly Opportunity[]) => {
      const index = new Map(fresh.map((o) => [o.identifier, o]));
      let next = recordsRef.current;
      for (const id of savedRef.current) {
        const o = index.get(id);
        if (o && !sameRecord(next[id], o)) next = { ...next, [id]: o };
      }
      if (next !== recordsRef.current) commitRecords(next);

      const toCheck = savedToRecheck(
        savedRef.current,
        new Set(index.keys()),
        recordsRef.current,
        isClosed,
        recheckedRef.current,
        RECHECK_LIMIT,
      );
      for (const id of toCheck) {
        try {
          const o = await fetchOpportunity(id);
          recheckedRef.current.add(id);
          if (savedRef.current.has(id)) commitRecords({ ...recordsRef.current, [id]: o });
        } catch (e) {
          if (e instanceof HttpError && e.status === 404) {
            recheckedRef.current.add(id);
            const prev = recordsRef.current[id];
            if (savedRef.current.has(id) && prev) commitRecords({ ...recordsRef.current, [id]: { ...prev, status: 'closed' } });
            continue;
          }
          break; // Sin red: ya se intentará en la próxima carga.
        }
      }
    },
    [commitRecords],
  );

  const findRecord = useCallback(async (id: string, record?: Opportunity): Promise<Opportunity | null> => {
    if (record) return record;
    const fromList = itemsRef.current.find((o) => o.identifier === id);
    if (fromList) return fromList;
    if (recordsRef.current[id]) return recordsRef.current[id];
    try {
      return await fetchOpportunity(id);
    } catch {
      return null;
    }
  }, []);

  // ---------- Descarga ----------

  const refresh = useCallback((): Promise<void> => {
    if (inflightRef.current) return inflightRef.current;
    const run = (async () => {
      // Antes, terminar de leer la caché y los vistos (si no, la primera carga los pisaría).
      await hydration.promise;
      const last = lastUpdatedRef.current;
      setChecking(last == null || Date.now() - last > STALE_MS);
      setRefreshing(true);
      try {
        // Con lista en caché se pide condicional: un 304 deja la caché como está.
        const res = await fetchOpenOpportunitiesIfChanged(itemsRef.current.length ? etagRef.current : null);
        const now = Date.now();
        let fresh: Opportunity[];
        if (res.status === 'unchanged') {
          fresh = itemsRef.current;
        } else {
          fresh = [...res.items].sort(byCreatedDesc);
          const sig = listSignature(fresh);
          const listChanged = sig !== sigRef.current;
          const etagChanged = res.etag !== etagRef.current;
          etagRef.current = res.etag;
          if (listChanged) {
            sigRef.current = sig;
            itemsRef.current = fresh;
            setItems(fresh);
          }
          // El fichero guarda la lista y su ETag: se reescribe si cambia cualquiera de los dos.
          if (listChanged || etagChanged) {
            void writeFileJson('list', { at: now, sig, items: fresh, etag: res.etag } satisfies CachedList);
          }
        }
        void writeJson('cacheAt', now);
        lastUpdatedRef.current = now;
        setLastUpdated(now);
        setError(null);

        if (firstRunAtRef.current == null) {
          // Primera vez: no enseñar 200 "nuevos". Se da por visto lo anterior a los últimos días.
          // Si no hay nada de esos días, los 10 más recientes cuentan como nuevos.
          commitSeen(seenAfterFirstRun(fresh, seenRef.current, now, FIRST_RUN_NEW_DAYS, FIRST_RUN_FALLBACK_NEW));
          firstRunAtRef.current = now;
          void writeJson('firstRunAt', now);
        } else if (firstVisitRef.current && firstVisitExpired(firstRunAtRef.current, now)) {
          // La bienvenida ("lo que ha llegado en los últimos días") se acaba al día siguiente.
          endFirstVisit();
        }

        void syncReminders(fresh);
        void refreshSavedRecords(fresh);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Error de conexión');
      } finally {
        setRefreshing(false);
        setChecking(false);
        setLoading(false);
        inflightRef.current = null;
      }
    })();
    inflightRef.current = run;
    return run;
  }, [hydration, commitSeen, refreshSavedRecords, endFirstVisit]);

  // ---------- Arranque ----------

  useEffect(() => {
    let alive = true;
    (async () => {
      const [seenList, savedList, firstRunAt, oldFirstRunDone, firstVisitDone, cacheAt, records, fileList] = await Promise.all([
        readJson<string[]>('seen', []),
        readJson<string[]>('saved', []),
        readJson<number | null>('firstRunAt', null),
        readJson<boolean>('firstRunDone', false),
        readJson<boolean>('firstVisitDone', false),
        readJson<number | null>('cacheAt', null),
        readFileJson<Record<string, Opportunity>>('savedRecords', {}),
        readFileJson<CachedList | null>('list', null),
      ]);
      if (!alive) return;

      // Lista: fichero; si no hay, se migra la caché antigua de AsyncStorage (una vez) y se borra.
      let cached = fileList?.items?.length ? fileList : null;
      if (!cached) {
        const old = await readJson<{ at: number; items: Opportunity[] } | null>('cache', null);
        if (old?.items?.length) {
          const sorted = [...old.items].sort(byCreatedDesc);
          cached = { at: old.at, sig: listSignature(sorted), items: sorted };
          void writeFileJson('list', cached);
        }
        void removeKey('cache');
      }

      // Primera carga: se migra la marca antigua (quien ya usaba la app no es "primera visita").
      let runAt = firstRunAt;
      let visitDone = firstVisitDone;
      if (runAt == null && oldFirstRunDone) {
        runAt = Date.now();
        visitDone = true;
        void writeJson('firstRunAt', runAt);
        void writeJson('firstVisitDone', true);
        void removeKey('firstRunDone');
      }
      firstRunAtRef.current = runAt;
      firstVisitRef.current = !visitDone;
      setIsFirstVisit(!visitDone);

      // Vistos: se SUMAN a lo que ya se haya marcado mientras se leía (nunca se pisa) y se quitan
      // los que se pidió volver a enseñar como nuevos mientras tanto (aviso diario).
      const hadPending = pendingUnseeRef.current.size > 0;
      if (seenList.length || hadPending) {
        const merged = hydrateSeen(seenList, seenRef.current, pendingUnseeRef.current);
        seenRef.current = merged;
        setSeen(merged);
        if (hadPending) seenDirtyRef.current = true;
      }
      pendingUnseeRef.current = new Set();

      // Guardados: lo leído primero y lo guardado durante la lectura detrás.
      if (savedList.length) {
        const merged = new Set(savedList);
        savedRef.current.forEach((id) => merged.add(id));
        savedRef.current = merged;
        setSavedIds(merged);
      }
      const mergedRecords = { ...records, ...recordsRef.current };
      recordsRef.current = mergedRecords;
      setSavedRecords(mergedRecords);

      if (cached && itemsRef.current.length === 0) {
        itemsRef.current = cached.items;
        sigRef.current = cached.sig;
        etagRef.current = cached.etag ?? null;
        setItems(cached.items);
        setLoading(false);
      }
      const at = Math.max(cached?.at ?? 0, cacheAt ?? 0) || null;
      lastUpdatedRef.current = at;
      setLastUpdated(at);

      hydratedRef.current = true;
      // Lo cambiado durante la lectura se escribe ahora, una vez, ya unido a lo leído.
      if (savedDirtyRef.current) {
        savedDirtyRef.current = false;
        void writeJson('saved', [...savedRef.current]);
      }
      if (recordsDirtyRef.current) {
        recordsDirtyRef.current = false;
        void writeFileJson('savedRecords', recordsRef.current);
      }
      flushSeen(); // por si se marcó algo antes de terminar de leer
      hydration.resolve();
      void refresh();
    })();
    return () => {
      alive = false;
    };
  }, [hydration, flushSeen, refresh]);

  // Avisos: lectura inicial (limpia los que ya saltaron) y cambios desde cualquier pantalla.
  useEffect(() => {
    let alive = true;
    const unsubscribe = subscribeReminders((ids) => setReminderIds(ids));
    getReminderIds()
      .then((ids) => alive && setReminderIds(ids))
      .catch(() => alive && setReminderIds(new Set()));
    return () => {
      alive = false;
      unsubscribe();
    };
  }, []);

  // Al volver a la app (p. ej. desde una notificación), refresca si hace falta; al salir, guarda.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        const last = lastUpdatedRef.current;
        if (hydratedRef.current && (!last || Date.now() - last > STALE_MS)) void refresh();
      } else {
        flushSeen();
      }
    });
    return () => {
      sub.remove();
      flushSeen();
    };
  }, [refresh, flushSeen]);

  // ---------- Acciones ----------

  const markAllSeen = useCallback((): (() => void) => {
    const prev = seenRef.current;
    const added = itemsRef.current.map((o) => o.identifier).filter((id) => !prev.has(id));
    if (added.length) {
      const next = new Set(prev);
      added.forEach((id) => next.add(id));
      commitSeen(next);
    }
    endFirstVisit();
    return () => {
      if (!added.length) return;
      const next = new Set(seenRef.current);
      added.forEach((id) => next.delete(id));
      commitSeen(next);
    };
  }, [commitSeen, endFirstVisit]);

  const markSeen = useCallback(
    (identifier: string) => {
      pendingUnseeRef.current.delete(identifier);
      if (seenRef.current.has(identifier)) return;
      const next = new Set(seenRef.current);
      next.add(identifier);
      commitSeen(next);
    },
    [commitSeen],
  );

  const showAsNew = useCallback(
    (ids: string[]) => {
      // Antes de leer los vistos: se recuerdan y se quitan de lo leído al terminar.
      if (!hydratedRef.current) ids.forEach((id) => pendingUnseeRef.current.add(id));
      const present = ids.filter((id) => seenRef.current.has(id));
      if (!present.length) return;
      const next = new Set(seenRef.current);
      present.forEach((id) => next.delete(id));
      commitSeen(next);
    },
    [commitSeen],
  );

  const setSaved = useCallback(
    async (identifier: string, saved: boolean, record?: Opportunity): Promise<ToggleSavedResult> => {
      // Nunca antes de leer los guardados (se decidiría con la lista vacía).
      await hydration.promise;
      if (!saved) {
        if (!savedRef.current.has(identifier)) return { saved: false, reminder: 'none' };
        const next = new Set(savedRef.current);
        next.delete(identifier);
        commitSaved(next);
        if (recordsRef.current[identifier]) {
          const { [identifier]: _removed, ...rest } = recordsRef.current;
          commitRecords(rest);
        }
        const had = await cancelReminder(identifier).catch(() => false);
        return { saved: false, reminder: had ? 'cancelled' : 'none' };
      }

      if (savedRef.current.has(identifier)) return { saved: true, reminder: 'none' };
      const next = new Set(savedRef.current);
      next.add(identifier);
      commitSaved(next);

      const rec = await findRecord(identifier, record);
      if (!rec) return { saved: true, reminder: 'unavailable' };
      if (savedRef.current.has(identifier)) commitRecords({ ...recordsRef.current, [identifier]: rec });

      // El permiso de notificaciones se pide como mucho una vez al guardar; después, el aviso
      // solo se programa si ya hay permiso (la ficha deja pedirlo a mano).
      const asked = await readJson<boolean>('reminderPermAsked', false);
      if (!asked) void writeJson('reminderPermAsked', true);
      const r = await scheduleReminder(rec, { askPermission: !asked });
      // Si se quitó de guardados mientras se programaba, se deshace el aviso.
      if (!savedRef.current.has(identifier)) {
        if (r.status === 'set') await cancelReminder(identifier).catch(() => false);
        return { saved: false, reminder: 'none' };
      }
      switch (r.status) {
        case 'set':
          return { saved: true, reminder: 'set' };
        case 'already':
          return { saved: true, reminder: 'already' };
        case 'denied':
          return { saved: true, reminder: 'denied' };
        default:
          return { saved: true, reminder: 'unavailable' };
      }
    },
    [hydration, commitSaved, commitRecords, findRecord],
  );

  const toggleSaved = useCallback(
    async (identifier: string, record?: Opportunity): Promise<ToggleSavedResult> => {
      await hydration.promise;
      return setSaved(identifier, !savedRef.current.has(identifier), record);
    },
    [hydration, setSaved],
  );

  const toggleReminderFor = useCallback(
    async (identifier: string): Promise<ToggleResult> => {
      const rec = await findRecord(identifier);
      if (!rec) return { status: 'unavailable', reason: 'No hemos podido cargar el proyecto. Inténtalo de nuevo.' };
      return toggleReminder(rec);
    },
    [findRecord],
  );

  const data = useMemo<OpportunityDataState>(() => {
    const index = new Map(items.map((o) => [o.identifier, o]));
    return {
      items,
      loading,
      refreshing,
      checking,
      error,
      lastUpdated,
      refresh,
      getById: (id) => index.get(id),
    };
  }, [items, loading, refreshing, checking, error, lastUpdated, refresh]);

  const seenState = useMemo<SeenState>(
    () => ({
      newItems: unseenItems(items, seen),
      seenIds: seen,
      isFirstVisit,
      markAllSeen,
      markSeen,
      showAsNew,
    }),
    [items, seen, isFirstVisit, markAllSeen, markSeen, showAsNew],
  );

  const savedState = useMemo<SavedState>(
    () => ({ savedIds, savedRecords, reminderIds, toggleSaved, setSaved, toggleReminderFor }),
    [savedIds, savedRecords, reminderIds, toggleSaved, setSaved, toggleReminderFor],
  );

  return (
    <DataCtx.Provider value={data}>
      <SeenCtx.Provider value={seenState}>
        <SavedCtx.Provider value={savedState}>{children}</SavedCtx.Provider>
      </SeenCtx.Provider>
    </DataCtx.Provider>
  );
}

function useRequired<T>(ctx: Context<T | null>, name: string): T {
  const value = useContext(ctx);
  if (!value) throw new Error(`${name} fuera de OpportunitiesProvider`);
  return value;
}

/** Lista, carga, error, `refresh`, `getById`. No se repinta al marcar vistos o guardar. */
export function useOpportunityData(): OpportunityDataState {
  return useRequired(DataCtx, 'useOpportunityData');
}

/** Nuevos, vistos y primera visita. */
export function useSeenState(): SeenState {
  return useRequired(SeenCtx, 'useSeenState');
}

/** Guardados, fichas guardadas y avisos de plazo. */
export function useSavedState(): SavedState {
  return useRequired(SavedCtx, 'useSavedState');
}

/** Todo junto (compatibilidad): se repinta con cualquier cambio. Prefiere los hooks de arriba. */
export function useOpportunities(): OpportunitiesState {
  const data = useOpportunityData();
  const seen = useSeenState();
  const saved = useSavedState();
  return useMemo(() => ({ ...data, ...seen, ...saved }), [data, seen, saved]);
}

/**
 * Nuevos que encajan con los tipos que interesan al usuario (Ajustes → avisos). Mientras se
 * leen las preferencias (o si no hay ninguna marcada) cuentan todos. Lo usan Nuevos y el
 * número de la pestaña.
 */
export function useInterestingNewItems(): Opportunity[] {
  const { newItems } = useSeenState();
  const prefs = usePushPrefs();
  const types = prefs?.types;
  return useMemo(() => {
    if (!types || types.length === 0) return newItems;
    const wanted = new Set<string>(types);
    return newItems.filter((o) => !o.type || wanted.has(o.type));
  }, [newItems, types]);
}

/** Aviso de plazo de un proyecto para el control de la ficha. `on` es null mientras se lee. */
export function useReminder(id: string): { on: boolean | null; toggle: () => Promise<ToggleResult> } {
  const { reminderIds, toggleReminderFor } = useSavedState();
  const toggle = useCallback(() => toggleReminderFor(id), [toggleReminderFor, id]);
  return { on: reminderIds ? reminderIds.has(id) : null, toggle };
}
