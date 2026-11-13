/**
 * Vibraciones cortas (expo-haptics). Nunca lanzan: si el dispositivo no tiene motor háptico,
 * está en web o el sistema las tiene desactivadas, no pasa nada.
 *
 * - tapSelection: cambiar una selección (chip, pestaña de un segmentado, filtro).
 * - tapLight: pulsar un botón de icono (guardar, compartir…).
 * - tapSuccess: acción completada (guardado, recordatorio puesto).
 * - tapWarning: algo no se pudo hacer.
 */
import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';

const enabled = Platform.OS === 'ios' || Platform.OS === 'android';

function run(fn: () => Promise<void>): void {
  if (!enabled) return;
  try {
    fn().catch(() => {});
  } catch {
    // Módulo nativo no disponible: ignorar.
  }
}

export function tapSelection(): void {
  run(() => Haptics.selectionAsync());
}

export function tapLight(): void {
  run(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
}

export function tapSuccess(): void {
  run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
}

export function tapWarning(): void {
  run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning));
}
