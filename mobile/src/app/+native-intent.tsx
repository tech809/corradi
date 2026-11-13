/**
 * Reescribe enlaces del sistema antes de que Expo Router los resuelva (SDK 58: `redirectSystemPath`).
 *
 * - Enlaces cortos de la web: https://mapa.proactivefuture.eu/2026-0040 → /proyecto/CORRADI-2026-0040.
 *   (Android: intentFilter con pathPattern en app.config.ts; iOS: el AASA del servidor los incluye.)
 * - Todo lo demás pasa tal cual. Nunca lanza: un error aquí cerraría la app.
 */

/** "/2026-0040": año y número del proyecto. */
const SHORT_LINK = /^\/(\d{4}-\d{4})$/;
/** Esquema y host de una URL completa ("https://mapa.proactivefuture.eu", "corradi://"). */
const ORIGIN = /^[a-z][a-z0-9+.-]*:\/\/[^/?#]*/i;

export function redirectSystemPath({ path }: { path: string; initial: boolean }): string {
  try {
    const pathname = path.replace(ORIGIN, '').split(/[?#]/)[0] ?? '';
    const match = SHORT_LINK.exec(pathname.replace(/\/+$/, '') || '/');
    if (match) return `/proyecto/CORRADI-${match[1]}`;
    return path;
  } catch {
    return path;
  }
}
