/**
 * Qué pasa con las notificaciones:
 * - En primer plano se muestran (banner + lista + sonido).
 * - Al tocarlas: resumen diario ({screen:'nuevos', ids:[...]}) → pestaña Nuevos con `ids`
 *   (separados por comas) para enseñar justo esos; recordatorio de plazo ({screen:'proyecto', id})
 *   → ficha del proyecto. Incluye el arranque en frío (la app estaba cerrada).
 * - Cada toque se atiende una sola vez (por `request.identifier`): el arranque en frío y el
 *   listener pueden entregar la misma respuesta.
 * - Al arrancar, y cada vez que la app vuelve a primer plano (como mucho cada 15 s),
 *   sincroniza el registro push: así un permiso retirado o devuelto en los ajustes del sistema
 *   se refleja en el servidor sin esperar a un arranque en frío. Escucha si el sistema cambia el
 *   token y, la primera vez, abre la bienvenida (/bienvenida).
 */
import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import { useEffect } from 'react';
import { AppState } from 'react-native';

import { ensureChannels, getPrefs, onDeviceToken, pushSupported, syncPushOnStart } from './push';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

type RouteData = { screen?: unknown; id?: unknown; ids?: unknown };

/** Identificadores ya atendidos en esta sesión (el módulo vive lo que vive el proceso). */
const handled = new Set<string>();

function idsParam(ids: unknown): string | null {
  if (!Array.isArray(ids)) return null;
  const clean = ids.filter((x): x is string => typeof x === 'string' && x.length > 0 && !x.includes(','));
  return clean.length ? clean.join(',') : null;
}

function openFromData(data: RouteData | undefined): void {
  if (!data) return;
  if (data.screen === 'nuevos') {
    const ids = idsParam(data.ids);
    router.navigate(ids ? { pathname: '/', params: { ids } } : '/');
  } else if (data.screen === 'proyecto' && typeof data.id === 'string' && data.id) {
    router.navigate({ pathname: '/proyecto/[id]', params: { id: data.id } });
  }
}

/** Devuelve true si la respuesta abrió una pantalla (o ya se había atendido). */
function handleResponse(response: Notifications.NotificationResponse): boolean {
  if (response.actionIdentifier !== Notifications.DEFAULT_ACTION_IDENTIFIER) return false;
  const key = response.notification.request.identifier;
  if (handled.has(key)) return true;
  handled.add(key);
  try {
    openFromData(response.notification.request.content.data as RouteData);
  } finally {
    // Que no se vuelva a abrir la misma pantalla en el próximo montaje.
    try {
      Notifications.clearLastNotificationResponse();
    } catch {
      // API no disponible (web): ignorar.
    }
  }
  return true;
}

export function useNotificationRouting(): void {
  useEffect(() => {
    // Arranque en frío: la app se abrió tocando una notificación.
    const last = Notifications.getLastNotificationResponse();
    const openedFromNotification = last ? handleResponse(last) : false;

    let cancelled = false;
    void getPrefs().then((p) => {
      if (!cancelled && !p.welcomeDone && !openedFromNotification) router.push('/bienvenida');
    });

    const responses = Notifications.addNotificationResponseReceivedListener(handleResponse);
    // Solo con push disponible: en Expo Go para Android este listener lanza un error.
    const tokens = pushSupported() ? Notifications.addPushTokenListener((token) => void onDeviceToken(token)) : null;

    void ensureChannels();
    void syncPushOnStart();
    const appState = AppState.addEventListener('change', (state) => {
      if (state === 'active') void syncPushOnStart({ throttle: true });
    });

    return () => {
      cancelled = true;
      responses.remove();
      tokens?.remove();
      appState.remove();
    };
  }, []);
}
