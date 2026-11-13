import AsyncStorage from '@react-native-async-storage/async-storage';
import { File, Paths } from 'expo-file-system';

/**
 * Todo lo que la app recuerda vive en el propio móvil: no hay cuentas.
 *
 * - Claves pequeñas (listas de ids, preferencias, marcas de tiempo): AsyncStorage, con prefijo
 *   y versión para poder migrar sin chocar.
 * - Datos grandes (la lista de proyectos, las fichas guardadas): ficheros JSON en el directorio
 *   de documentos (expo-file-system, API `File`/`Paths` de SDK 58). Se escriben de forma atómica
 *   (fichero temporal + mover) para no dejar un JSON a medias si la app se cierra.
 */
const KEYS = {
  seen: 'corradi:v1:seen', // string[] de identifiers ya vistos
  saved: 'corradi:v1:saved', // string[] de identifiers guardados (orden de guardado)
  cache: 'corradi:v1:cache', // OBSOLETA: { at, items } (se migra a fichero y se borra)
  cacheAt: 'corradi:v1:cacheAt', // number: última descarga correcta de la lista
  firstRunDone: 'corradi:v1:firstRunDone', // OBSOLETA: se migra a firstRunAt
  firstRunAt: 'corradi:v1:firstRunAt', // number: primera carga correcta
  firstVisitDone: 'corradi:v1:firstVisitDone', // true tras el primer "Ya los he visto"
  reminders: 'corradi:v1:reminders', // Record<identifier, { notificationId, deadline }>
  reminderPermAsked: 'corradi:v1:reminderPermAsked', // true tras pedir permiso al guardar
  prefs: 'corradi:v1:prefs', // NotificationPrefs
  openCount: 'corradi:v1:openCount', // número de aperturas (para pedir valoración)
  reviewAsked: 'corradi:v1:reviewAsked',
} as const;

export type StorageKey = keyof typeof KEYS;

export async function readJson<T>(key: StorageKey, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(KEYS[key]);
    return raw == null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export async function writeJson(key: StorageKey, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(KEYS[key], JSON.stringify(value));
  } catch {
    // Sin almacenamiento la app sigue funcionando; solo olvida el estado.
  }
}

export async function removeKey(key: StorageKey): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEYS[key]);
  } catch {
    // Nada que hacer.
  }
}

// ---------- Ficheros JSON ----------

/** Ficheros de datos grandes (en el directorio de documentos de la app). */
export type DataFile = 'list' | 'savedRecords';

const FILE_NAMES: Record<DataFile, string> = {
  list: 'corradi-list-v1.json', // { at, sig, items: Opportunity[] }
  savedRecords: 'corradi-saved-v1.json', // Record<identifier, Opportunity>
};

function dataFile(name: DataFile, suffix = ''): File | null {
  try {
    return new File(Paths.document, FILE_NAMES[name] + suffix);
  } catch {
    return null; // Web u otro entorno sin sistema de ficheros.
  }
}

export async function readFileJson<T>(name: DataFile, fallback: T): Promise<T> {
  try {
    const file = dataFile(name);
    if (!file || !file.exists) return fallback;
    return JSON.parse(await file.text()) as T;
  } catch {
    return fallback;
  }
}

// Una escritura a la vez por fichero (comparten el temporal).
const writeQueues: Partial<Record<DataFile, Promise<void>>> = {};

/** Escribe el JSON en un temporal y lo mueve encima del bueno (escritura atómica). */
export function writeFileJson(name: DataFile, value: unknown): Promise<void> {
  const json = JSON.stringify(value);
  const run = (writeQueues[name] ?? Promise.resolve()).then(async () => {
    try {
      const target = dataFile(name);
      const tmp = dataFile(name, '.tmp');
      if (!target || !tmp) return;
      tmp.create({ overwrite: true });
      await tmp.write(json);
      await tmp.move(target, { overwrite: true });
    } catch {
      // Sin disco la app sigue funcionando; solo no habrá caché.
    }
  });
  writeQueues[name] = run;
  return run;
}
