import { File, Paths } from 'expo-file-system';
import { Platform, Share } from 'react-native';

import { WEB_URLS } from './config';
import { cleanTitle, placeLabel } from './format';
import type { Opportunity } from './types';

type ShareTarget = Pick<Opportunity, 'identifier' | 'title' | 'location' | 'country_code'>;

/**
 * Lo máximo que dejamos la descarga en marcha. Si pasa de SHARE_WAIT_MS se comparte texto +
 * enlace, pero la descarga sigue y el siguiente toque en Compartir ya la aprovecha.
 */
const DOWNLOAD_TIMEOUT_MS = 15_000;
/** Lo máximo que esperamos a la imagen al pulsar Compartir; después, texto + enlace. */
const SHARE_WAIT_MS = 6_000;

/** "{título} — {lugar}. Míralo en Corradi: {url}" */
export function shareMessage(o: ShareTarget, withUrl = true): string {
  const place = placeLabel(o);
  const head = `${cleanTitle(o.title)}${place ? ` — ${place}` : ''}.`;
  return withUrl ? `${head} Míralo en Corradi: ${WEB_URLS.proyecto(o.identifier)}` : `${head} Míralo en Corradi:`;
}

/**
 * Descargas en curso o hechas, por proyecto (solo dura lo que dura la app abierta). La imagen
 * (~1 MB, varios segundos de render en el servidor) se pide solo al pulsar Compartir, nunca al
 * abrir la ficha.
 */
const stories = new Map<string, Promise<File | null>>();

/** Descarga la imagen-story del proyecto a la caché. null si no se puede. */
async function downloadStory(identifier: string): Promise<File | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DOWNLOAD_TIMEOUT_MS);
  try {
    const dest = new File(Paths.cache, `corradi-${identifier.replace(/[^\w-]/g, '')}.jpg`);
    const file = await File.downloadFileAsync(WEB_URLS.storyImage(identifier), dest, {
      idempotent: true,
      signal: controller.signal,
    });
    return file.exists ? file : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function storyFor(identifier: string): Promise<File | null> {
  let p = stories.get(identifier);
  if (!p) {
    p = downloadStory(identifier);
    stories.set(identifier, p);
    // Si falla, se olvida para poder reintentar la próxima vez.
    void p.then((f) => {
      if (!f) stories.delete(identifier);
    });
  }
  return p;
}

function withTimeout<T>(p: Promise<T>, ms: number, fallback: T): Promise<T> {
  return new Promise((resolve) => {
    const id = setTimeout(() => resolve(fallback), ms);
    p.then(
      (v) => {
        clearTimeout(id);
        resolve(v);
      },
      () => {
        clearTimeout(id);
        resolve(fallback);
      },
    );
  });
}

/**
 * Un toque → hoja de compartir del sistema.
 * - iOS: la imagen-story se empieza a descargar aquí (el botón enseña un spinner mientras) y va
 *   con el texto y el enlace en la misma hoja. Si tarda más de 6 s, texto + enlace.
 * - Android: el Share de RN solo admite texto y expo-sharing solo un archivo (sin texto);
 *   se prioriza el texto con enlace, que en WhatsApp/Telegram ya trae vista previa con foto.
 * Si algo falla, se cae a texto + enlace.
 */
export async function shareOpportunity(o: ShareTarget): Promise<void> {
  const message = shareMessage(o);
  const url = WEB_URLS.proyecto(o.identifier);
  const title = cleanTitle(o.title);

  if (Platform.OS === 'ios') {
    const story = await withTimeout(storyFor(o.identifier), SHARE_WAIT_MS, null);
    if (story) {
      try {
        await Share.share({ message, url: story.uri });
        return;
      } catch {
        // sigue al plan B
      }
    }
  }

  try {
    await Share.share(
      Platform.OS === 'ios' ? { message: shareMessage(o, false), url } : { message, title },
      { dialogTitle: 'Compartir proyecto', subject: title },
    );
  } catch {
    // El usuario puede cerrar la hoja o el sistema no tener ninguna app: nada que hacer.
  }
}
