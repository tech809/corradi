/**
 * Avisos push de Corradi: un único resumen diario (≈19:30) cuando hay proyectos nuevos.
 *
 * - Las preferencias viven en el móvil (clave 'prefs'); no hay cuentas.
 * - El servidor solo guarda el token Expo, la plataforma y los tipos elegidos.
 * - Solo se llama al servidor cuando cambia algo (token, tipos o resumen sí/no): se recuerda
 *   lo último registrado en `registered`.
 * - Nada aquí lanza errores hacia la UI: sin red o sin backend se guarda lo pendiente
 *   y se reintenta al abrir la app o al volver a ella (`syncPushOnStart`).
 * - Registrar, dar de baja y sincronizar van en una fila (`serial`): nunca se pisan.
 */
import Constants, { ExecutionEnvironment } from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { AndroidImportance, IosAuthorizationStatus } from 'expo-notifications';
import { useEffect, useState } from 'react';
import { Platform } from 'react-native';

import { postJson } from './api';
import { readJson, writeJson } from './storage';
import { OPPORTUNITY_TYPES, type OpportunityType } from './types';

export const ALL_TYPES: OpportunityType[] = [...OPPORTUNITY_TYPES];

/** Canales de Android. 'digest' lo usa el servidor; 'reminders', los recordatorios locales. */
export const CHANNELS = { digest: 'digest', reminders: 'reminders' } as const;

export interface NotificationPrefs {
  digest: boolean;
  /** Tipos que interesan: filtran el resumen push y la pestaña Nuevos. Nunca vacío. */
  types: OpportunityType[];
}

/** Lo último que aceptó el servidor (para no repetir el registro si nada ha cambiado). */
interface Registration {
  token: string;
  types: OpportunityType[];
  digest: boolean;
}

/** Lo que se guarda en 'prefs': las preferencias más el estado interno de sincronización. */
interface StoredPrefs extends NotificationPrefs {
  /** true cuando ya se ha pasado por la bienvenida (con cualquiera de las dos respuestas). */
  welcomeDone?: boolean;
  /** Último token Expo conocido (para darlo de baja o detectar que ha cambiado). */
  token?: string | null;
  /** Último token nativo (APNs/FCM) visto: el listener de tokens solo actúa si cambia. */
  deviceToken?: string | null;
  /** Lo último registrado con éxito en el servidor. */
  registered?: Registration | null;
  /** Operación que falló (sin red, backend caído) y hay que repetir. */
  pending?: 'register' | 'unregister' | null;
}

export const DEFAULT_PREFS: NotificationPrefs = { digest: true, types: [...ALL_TYPES] };

/**
 * - enabled: registrado en el servidor.
 * - pending: guardado; se registrará cuando haya red / servidor.
 * - denied: el sistema no da permiso.
 * - unavailable: este binario no puede recibir push (simulador, Expo Go en Android o falta el
 *   projectId de EAS). Se devuelve ANTES de pedir permiso.
 * - disabled: el resumen está apagado.
 */
export type PushResult = 'enabled' | 'pending' | 'denied' | 'unavailable' | 'disabled';

/** Texto honesto para cuando no hay push en este binario (bienvenida y Ajustes). */
export const UNAVAILABLE_MESSAGE = 'Los avisos estarán disponibles en la versión de las tiendas.';

// ---------------------------------------------------------------------------
// Estado compartido (Ajustes, bienvenida y Nuevos se enteran de los cambios)

export type PushPrefs = NotificationPrefs & { welcomeDone: boolean };

let current: StoredPrefs | null = null;
const listeners = new Set<(p: StoredPrefs) => void>();

function normalizeTypes(types: readonly OpportunityType[] | null | undefined): OpportunityType[] {
  const valid = ALL_TYPES.filter((t) => types?.includes(t));
  return valid.length ? valid : [...ALL_TYPES];
}

async function load(): Promise<StoredPrefs> {
  if (current) return current;
  const stored = await readJson<StoredPrefs | null>('prefs', null);
  current = { ...DEFAULT_PREFS, ...(stored ?? {}) };
  current.types = normalizeTypes(current.types);
  return current;
}

async function save(patch: Partial<StoredPrefs>): Promise<StoredPrefs> {
  const next = { ...(await load()), ...patch };
  current = next;
  await writeJson('prefs', next);
  listeners.forEach((l) => l(next));
  return next;
}

function publicPrefs(p: StoredPrefs): PushPrefs {
  return { digest: p.digest, types: p.types, welcomeDone: !!p.welcomeDone };
}

export async function getPrefs(): Promise<PushPrefs> {
  return publicPrefs(await load());
}

/** Preferencias actuales (null mientras se leen del almacenamiento). Forma estable: no quitar campos. */
export function usePushPrefs(): PushPrefs | null {
  const [prefs, setPrefs] = useState<PushPrefs | null>(current ? publicPrefs(current) : null);
  useEffect(() => {
    const listener = (p: StoredPrefs) => setPrefs(publicPrefs(p));
    listeners.add(listener);
    void load().then(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return prefs;
}

export async function markWelcomeDone(): Promise<void> {
  await save({ welcomeDone: true });
}

// ---------------------------------------------------------------------------
// Sistema

/** Expo Go en Android no admite push remoto desde SDK 53. */
const isExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;

function getProjectId(): string | undefined {
  const fromEas = Constants.easConfig?.projectId;
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined;
  return fromEas ?? extra?.eas?.projectId ?? undefined;
}

/** ¿Puede este binario recibir push remoto? (móvil real, projectId y no Expo Go en Android) */
export function pushSupported(): boolean {
  return Device.isDevice && !!getProjectId() && !(isExpoGo && Platform.OS === 'android');
}

let channelsReady: Promise<void> | null = null;

/** Crea los canales de Android (idempotente). En Android 13+ hace falta antes de pedir permiso. */
export function ensureChannels(): Promise<void> {
  if (Platform.OS !== 'android') return Promise.resolve();
  channelsReady ??= (async () => {
    try {
      await Notifications.setNotificationChannelAsync(CHANNELS.digest, {
        name: 'Resumen diario',
        description: 'Un aviso al día cuando hay proyectos nuevos',
        importance: AndroidImportance.DEFAULT,
      });
      await Notifications.setNotificationChannelAsync(CHANNELS.reminders, {
        name: 'Recordatorios de plazos',
        description: 'Avisos que pides antes de que cierre un proyecto.',
        importance: AndroidImportance.HIGH,
      });
    } catch {
      channelsReady = null; // se reintenta la próxima vez
    }
  })();
  return channelsReady;
}

export type PermissionState = 'granted' | 'denied' | 'undetermined';

export async function getPermissionState(): Promise<PermissionState> {
  try {
    const p = await Notifications.getPermissionsAsync();
    if (p.granted || p.ios?.status === IosAuthorizationStatus.PROVISIONAL) return 'granted';
    return p.canAskAgain ? 'undetermined' : 'denied';
  } catch {
    return 'undetermined';
  }
}

/** Pide permiso si aún se puede. Devuelve si lo hay. */
export async function requestPermission(): Promise<boolean> {
  await ensureChannels();
  try {
    const now = await Notifications.getPermissionsAsync();
    if (now.granted) return true;
    if (!now.canAskAgain) return false;
    const asked = await Notifications.requestPermissionsAsync();
    return asked.granted || asked.ios?.status === IosAuthorizationStatus.PROVISIONAL;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Servidor

function payloadTypes(types: OpportunityType[]): OpportunityType[] {
  // Lista vacía = todos (contrato del backend).
  return ALL_TYPES.every((t) => types.includes(t)) ? [] : types;
}

function sameRegistration(a: Registration | null | undefined, b: Registration): boolean {
  return !!a && a.token === b.token && a.digest === b.digest && a.types.join() === b.types.join();
}

interface Tokens {
  expo: string;
  device: string | null;
}

/**
 * Token nativo + token Expo. Si el nativo es el mismo que el guardado y el token Expo guardado es
 * el que el servidor tiene registrado (sin nada pendiente), se reutiliza: el token Expo depende
 * del nativo, así que no hace falta volver a pedirlo a los servidores de Expo en cada vuelta a
 * primer plano.
 */
async function getTokens(device: Notifications.DevicePushToken | undefined, stored: StoredPrefs): Promise<Tokens | null> {
  const projectId = getProjectId();
  if (!projectId) return null;
  try {
    // El token nativo se pide aparte para poder comparar en el listener (ver onDeviceToken).
    const devicePushToken = device ?? (await Notifications.getDevicePushTokenAsync());
    const deviceToken = typeof devicePushToken.data === 'string' ? devicePushToken.data : null;
    if (
      deviceToken &&
      deviceToken === stored.deviceToken &&
      stored.token &&
      stored.registered?.token === stored.token &&
      !stored.pending
    ) {
      return { expo: stored.token, device: deviceToken };
    }
    const { data } = await Notifications.getExpoPushTokenAsync({ projectId, devicePushToken });
    return { expo: data, device: deviceToken };
  } catch {
    return null; // sin red, o servicio de push no disponible
  }
}

// Todas las operaciones con el servidor (registrar, dar de baja, sincronizar) van en fila, una
// detrás de otra (mismo patrón que reminders.ts). Así, desactivar mientras un registro está en
// vuelo no deja el token dado de alta: la baja se ejecuta DESPUÉS y lo deshace.
let queue: Promise<unknown> = Promise.resolve();
function serial<T>(fn: () => Promise<T>): Promise<T> {
  const run = queue.then(fn, fn);
  queue = run.catch(() => {});
  return run;
}

/** Registra el token con las preferencias actuales si algo ha cambiado. No pide permisos. */
function register(device?: Notifications.DevicePushToken): Promise<PushResult> {
  return serial(() => doRegister(device));
}

/** Solo desde dentro de la fila (`serial`). */
async function doRegister(device?: Notifications.DevicePushToken, attempt = 0): Promise<PushResult> {
  // Lo que se lee es lo que hay AHORA (puede haber cambiado mientras esperaba en la fila).
  const before = await load();
  if (!before.digest) return 'disabled';
  const tokens = await getTokens(device, before);
  if (!tokens) {
    await save({ pending: 'register' });
    return 'pending';
  }
  const prefs = await load();
  if (!prefs.digest) return 'disabled';
  const wanted: Registration = { token: tokens.expo, types: [...prefs.types], digest: prefs.digest };
  if (sameRegistration(prefs.registered, wanted) && !prefs.pending) {
    if (prefs.deviceToken !== tokens.device) await save({ deviceToken: tokens.device });
    return 'enabled';
  }
  try {
    // Si el token ha rotado, el antiguo deja de valer: se da de baja (sin esperar éxito).
    if (prefs.token && prefs.token !== tokens.expo) {
      postJson('/api/push/unregister', { token: prefs.token }).catch(() => {});
    }
    await postJson('/api/push/register', {
      token: tokens.expo,
      platform: Platform.OS === 'ios' ? 'ios' : 'android',
      types: payloadTypes(wanted.types),
      daily_digest: wanted.digest,
    });
    await save({ token: tokens.expo, deviceToken: tokens.device, registered: wanted, pending: null });
  } catch {
    await save({ token: tokens.expo, deviceToken: tokens.device, pending: 'register' });
    return 'pending';
  }
  // ¿Cambiaron los tipos mientras se enviaba? Se manda lo nuevo (una vez; si no, en el próximo arranque).
  const now = await load();
  if (now.digest && now.types.join() !== wanted.types.join() && attempt === 0) return doRegister(undefined, 1);
  return now.digest ? 'enabled' : 'disabled';
}

/** Da de baja el token en el servidor (conserva `digest`: es la preferencia del usuario). */
function unregister(): Promise<void> {
  return serial(doUnregister);
}

/** Solo desde dentro de la fila (`serial`). */
async function doUnregister(): Promise<void> {
  const p = await load();
  if (!p.token) {
    await save({ pending: null, registered: null });
    return;
  }
  try {
    await postJson('/api/push/unregister', { token: p.token });
    await save({ token: null, registered: null, pending: null });
  } catch {
    await save({ pending: 'unregister' });
  }
}

/**
 * Activa el resumen diario. Si este binario no puede recibir push devuelve 'unavailable' sin
 * pedir permiso (pero recuerda la preferencia). Si no, pide permiso, obtiene el token y lo registra.
 */
export async function enableDigest(prefs?: Partial<NotificationPrefs>): Promise<PushResult> {
  const types = normalizeTypes(prefs?.types?.length ? prefs.types : (await load()).types);
  if (!pushSupported()) {
    if (__DEV__ && Device.isDevice && !getProjectId()) {
      console.warn('[push] Falta EAS_PROJECT_ID: no se puede obtener el token push.');
    }
    await save({ digest: true, types });
    return 'unavailable';
  }
  const granted = await requestPermission();
  if (!granted) {
    await save({ digest: false, types });
    return 'denied';
  }
  await save({ digest: true, types });
  return register();
}

/** Desactiva el resumen diario y da de baja el token en el servidor. */
export async function disableDigest(): Promise<PushResult> {
  await save({ digest: false });
  await unregister();
  return 'disabled';
}

/**
 * Cambia los tipos que interesan (filtran el resumen y la pestaña Nuevos) y, si el resumen está
 * activo y hay push, vuelve a registrar.
 */
export async function setDigestTypes(types: OpportunityType[]): Promise<PushResult> {
  const next = await save({ types: normalizeTypes(types) });
  if (!next.digest) return 'disabled';
  if (!pushSupported()) return 'unavailable';
  if ((await getPermissionState()) !== 'granted') return 'denied';
  return register();
}

/**
 * El sistema avisa de un token nativo (iOS lo emite en CADA petición de token, también las
 * nuestras): solo se vuelve a registrar si es distinto del último visto.
 */
export async function onDeviceToken(device: Notifications.DevicePushToken): Promise<void> {
  try {
    const p = await load();
    if (!p.digest || !p.welcomeDone || !pushSupported()) return;
    if (typeof device.data === 'string' && device.data === p.deviceToken) return;
    if ((await getPermissionState()) !== 'granted') return;
    await register(device);
  } catch {
    // nunca romper la app por los avisos
  }
}

let syncing = false;
let lastSync = 0;

/** Mínimo entre dos sincronizaciones al volver a primer plano (cada una lee el token nativo). */
const SYNC_MIN_INTERVAL_MS = 15_000;

/**
 * Al arrancar y al volver a primer plano: crea canales, repite lo pendiente y comprueba si el
 * token ha cambiado. Si el permiso del sistema se ha retirado (p. ej. en los ajustes del
 * sistema mientras la app estaba en segundo plano), da de baja el token pero conserva la
 * preferencia para restaurarla cuando vuelva el permiso. Nunca pide permisos ni lanza errores.
 * `throttle`: no repetir si ya se sincronizó hace menos de 15 s.
 */
export async function syncPushOnStart(opts: { throttle?: boolean } = {}): Promise<void> {
  if (syncing) return;
  if (opts.throttle && Date.now() - lastSync < SYNC_MIN_INTERVAL_MS) return;
  syncing = true;
  lastSync = Date.now();
  try {
    await ensureChannels();
    await serial(async () => {
      const p = await load();
      if (!p.welcomeDone || !pushSupported()) return;
      if (!p.digest) {
        if (p.token || p.pending === 'unregister') await doUnregister();
        return;
      }
      const permission = await getPermissionState();
      if (permission !== 'granted') {
        if (p.token) await doUnregister();
        return;
      }
      await doRegister();
    });
  } catch {
    // nunca romper el arranque por los avisos
  } finally {
    syncing = false;
  }
}
