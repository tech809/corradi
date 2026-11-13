import * as Notifications from 'expo-notifications';
import { AndroidImportance, IosAuthorizationStatus } from 'expo-notifications';
import { Platform } from 'react-native';

import { planReminder, type ReminderPlan } from '@/state/logic';

import { isClosed } from './format';
import { readJson, writeJson } from './storage';
import type { Opportunity } from './types';

/**
 * "Avísame antes de que cierre": notificación LOCAL a las 10:00 (hora del móvil)
 * 3 días antes del plazo; si ya es tarde para eso, 1 día antes o la misma mañana.
 *
 * Se guarda identifier → { notificationId, deadline } en storage 'reminders' (las versiones
 * antiguas guardaban solo el id de la notificación: se migran al leer). `syncReminders(items)`
 * se llama tras cada descarga correcta para cancelar avisos de proyectos que ya no están
 * abiertos y reprogramar los que han cambiado de plazo.
 *
 * Cualquier cambio avisa a los suscriptores (`subscribeReminders`), así el estado de la app
 * (tarjetas con campana, ficha) se entera aunque el cambio venga de otra pantalla.
 */

export const REMINDER_CHANNEL_ID = 'reminders';

type ReminderTarget = Pick<Opportunity, 'identifier' | 'title' | 'application_deadline' | 'deadline_estimated' | 'status'>;

interface StoredReminder {
  notificationId: string;
  /** Plazo con el que se programó (para reprogramar si cambia). null = desconocido (migrado). */
  deadline: string | null;
}

type ReminderMap = Record<string, StoredReminder>;

export type { ReminderPlan };

/** Cuándo saltaría el aviso, o por qué no se puede poner (lógica pura en src/state/logic.ts). */
export function reminderPlan(o: ReminderTarget, now: Date = new Date()): ReminderPlan {
  if (Platform.OS === 'web') return { ok: false, reason: 'Los avisos solo funcionan en la app del móvil.' };
  return planReminder(o, now);
}

// ---------- Almacenamiento ----------

// Las operaciones se encadenan para que dos cambios seguidos no se pisen el mapa.
let queue: Promise<unknown> = Promise.resolve();
function serial<T>(fn: () => Promise<T>): Promise<T> {
  const run = queue.then(fn, fn);
  queue = run.catch(() => {});
  return run;
}

async function readMap(): Promise<ReminderMap> {
  const raw = await readJson<Record<string, unknown>>('reminders', {});
  const map: ReminderMap = {};
  for (const [id, v] of Object.entries(raw ?? {})) {
    if (typeof v === 'string') map[id] = { notificationId: v, deadline: null }; // formato antiguo
    else if (v && typeof v === 'object' && typeof (v as StoredReminder).notificationId === 'string') {
      map[id] = { notificationId: (v as StoredReminder).notificationId, deadline: (v as StoredReminder).deadline ?? null };
    }
  }
  return map;
}

const listeners = new Set<(ids: Set<string>) => void>();

async function writeMap(map: ReminderMap): Promise<void> {
  await writeJson('reminders', map);
  const ids = new Set(Object.keys(map));
  listeners.forEach((l) => l(ids));
}

/** Se entera de cualquier cambio en los avisos. Devuelve la función para darse de baja. */
export function subscribeReminders(listener: (ids: Set<string>) => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

async function scheduledIds(): Promise<Set<string> | null> {
  if (Platform.OS === 'web') return new Set();
  try {
    const scheduled = await Notifications.getAllScheduledNotificationsAsync();
    return new Set(scheduled.map((n) => n.identifier));
  } catch {
    return null; // No se puede comprobar: nos fiamos de lo guardado.
  }
}

/**
 * Proyectos con aviso pendiente. Limpia los que ya saltaron (y migra el formato antiguo).
 */
export function getReminderIds(): Promise<Set<string>> {
  return serial(async () => {
    const map = await readMap();
    const pending = await scheduledIds();
    let changed = false;
    if (pending) {
      for (const [id, r] of Object.entries(map)) {
        if (!pending.has(r.notificationId)) {
          delete map[id];
          changed = true;
        }
      }
    }
    if (changed) await writeMap(map);
    return new Set(Object.keys(map));
  });
}

/** ¿Hay un aviso pendiente para este proyecto? Limpia los que ya saltaron. */
export async function isReminderSet(identifier: string): Promise<boolean> {
  return (await getReminderIds()).has(identifier);
}

// ---------- Permiso y canal ----------

async function ensureChannel(): Promise<void> {
  if (Platform.OS !== 'android') return;
  const existing = await Notifications.getNotificationChannelAsync(REMINDER_CHANNEL_ID);
  if (existing) return;
  await Notifications.setNotificationChannelAsync(REMINDER_CHANNEL_ID, {
    name: 'Recordatorios de plazos',
    description: 'Avisos que pides antes de que cierre un proyecto.',
    importance: AndroidImportance.HIGH,
  });
}

async function hasPermission(): Promise<{ granted: boolean; canAskAgain: boolean }> {
  const current = await Notifications.getPermissionsAsync();
  const granted = current.granted || current.ios?.status === IosAuthorizationStatus.PROVISIONAL;
  return { granted, canAskAgain: current.canAskAgain };
}

/**
 * Pide permiso solo si hace falta. En Android 13+ el canal debe existir antes de pedirlo.
 * Con `ask: false` solo comprueba (no saca el diálogo del sistema).
 */
async function ensurePermission(ask: boolean): Promise<boolean> {
  await ensureChannel();
  const { granted, canAskAgain } = await hasPermission();
  if (granted) return true;
  if (!ask || !canAskAgain) return false;
  const asked = await Notifications.requestPermissionsAsync({
    ios: { allowAlert: true, allowBadge: true, allowSound: true },
  });
  return asked.granted || asked.ios?.status === IosAuthorizationStatus.PROVISIONAL;
}

// ---------- Programar / cancelar ----------

function whenText(daysBefore: number): string {
  if (daysBefore === 0) return 'Cierra hoy';
  if (daysBefore === 1) return 'Cierra mañana';
  return `Cierra en ${daysBefore} días`;
}

function shorten(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

async function scheduleNotification(o: ReminderTarget, fireAt: Date, daysBefore: number): Promise<string> {
  return Notifications.scheduleNotificationAsync({
    content: {
      title: shorten(`${whenText(daysBefore)}: ${o.title}`, 110),
      body: o.deadline_estimated
        ? 'El plazo es aproximado: compruébalo en la ficha y apúntate cuanto antes.'
        : 'Toca para ver la ficha y apuntarte a tiempo.',
      data: { screen: 'proyecto', id: o.identifier },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DATE,
      date: fireAt,
      channelId: REMINDER_CHANNEL_ID,
    },
  });
}

async function cancelNotification(notificationId: string): Promise<void> {
  try {
    await Notifications.cancelScheduledNotificationAsync(notificationId);
  } catch {
    // Si ya no existía, da igual.
  }
}

export type ScheduleReminderResult =
  | { status: 'set'; fireAt: Date }
  | { status: 'already' }
  | { status: 'denied' }
  | { status: 'unavailable'; reason: string }
  | { status: 'error' };

/**
 * Pone el aviso de un proyecto si no lo tiene ya.
 * `askPermission: false` no saca el diálogo del sistema (devuelve 'denied' si no hay permiso).
 */
export function scheduleReminder(o: ReminderTarget, { askPermission = true } = {}): Promise<ScheduleReminderResult> {
  return serial(async () => {
    const map = await readMap();
    if (map[o.identifier]) return { status: 'already' } as const;
    const plan = reminderPlan(o);
    if (!plan.ok) return { status: 'unavailable', reason: plan.reason } as const;
    try {
      if (!(await ensurePermission(askPermission))) return { status: 'denied' } as const;
      const notificationId = await scheduleNotification(o, plan.fireAt, plan.daysBefore);
      map[o.identifier] = { notificationId, deadline: o.application_deadline ?? null };
      await writeMap(map);
      return { status: 'set', fireAt: plan.fireAt } as const;
    } catch {
      return { status: 'error' } as const;
    }
  });
}

/** Quita el aviso de un proyecto. true si había uno. */
export function cancelReminder(identifier: string): Promise<boolean> {
  return serial(async () => {
    const map = await readMap();
    const existing = map[identifier];
    if (!existing) return false;
    await cancelNotification(existing.notificationId);
    delete map[identifier];
    await writeMap(map);
    return true;
  });
}

export type ToggleReminderResult =
  | { status: 'set'; fireAt: Date }
  | { status: 'cancelled' }
  | { status: 'denied' }
  | { status: 'unavailable'; reason: string }
  | { status: 'error' };

/** Pone o quita el aviso de un proyecto (control de la ficha: siempre puede pedir permiso). */
export async function toggleReminder(o: ReminderTarget): Promise<ToggleReminderResult> {
  if (await cancelReminder(o.identifier)) return { status: 'cancelled' };
  const r = await scheduleReminder(o, { askPermission: true });
  // 'already' solo pasaría si otro toque lo puso entre medias: cuenta como puesto.
  if (r.status === 'already') {
    const plan = reminderPlan(o);
    return plan.ok ? { status: 'set', fireAt: plan.fireAt } : { status: 'error' };
  }
  return r;
}

/**
 * Tras cada descarga correcta de la lista de abiertos:
 * - cancela los avisos de proyectos que ya no están en la lista o están cerrados;
 * - reprograma los que han cambiado de plazo (o los cancela si ya no da tiempo);
 * - olvida los que ya saltaron.
 * No pide permisos. Con una lista vacía no hace nada (más vale un aviso de más que
 * borrarlos todos por una respuesta rara del servidor).
 */
export function syncReminders(items: readonly Opportunity[]): Promise<void> {
  if (items.length === 0 || Platform.OS === 'web') return Promise.resolve();
  return serial(async () => {
    const map = await readMap();
    const ids = Object.keys(map);
    if (ids.length === 0) return;
    const index = new Map(items.map((o) => [o.identifier, o]));
    const pending = await scheduledIds();
    let changed = false;

    for (const id of ids) {
      const r = map[id];
      const o = index.get(id);
      if (pending && !pending.has(r.notificationId)) {
        delete map[id]; // ya saltó o el sistema la borró
        changed = true;
        continue;
      }
      if (!o || isClosed(o)) {
        await cancelNotification(r.notificationId);
        delete map[id];
        changed = true;
        continue;
      }
      if ((o.application_deadline ?? null) === r.deadline) continue;
      // Ha cambiado el plazo: se reprograma (o se quita si ya no da tiempo).
      await cancelNotification(r.notificationId);
      delete map[id];
      changed = true;
      const plan = reminderPlan(o);
      if (!plan.ok) continue;
      try {
        if (!(await ensurePermission(false))) continue;
        const notificationId = await scheduleNotification(o, plan.fireAt, plan.daysBefore);
        map[id] = { notificationId, deadline: o.application_deadline ?? null };
      } catch {
        // Se queda sin aviso; la ficha deja volver a ponerlo.
      }
    }
    if (changed) await writeMap(map);
  });
}
