/**
 * Ayudas de accesibilidad compartidas (VoiceOver / TalkBack).
 *
 * - `announce(msg)`: lee un mensaje sin mover el foco (confirmaciones, resultados de filtros…).
 * - `useReduceMotion()`: true si el sistema pide reducir movimiento. Toda animación decorativa
 *   (escalas al pulsar, entradas, pulsos de carga, transiciones de imagen) debe saltarse entonces.
 * - `useScreenReader()`: true con VoiceOver/TalkBack activo.
 * - `focusOn(ref)`: mueve el foco del lector a un elemento (p. ej. el título tras navegar).
 */
import { useEffect, useState, type RefObject } from 'react';
import { AccessibilityInfo, Platform, type HostInstance } from 'react-native';

/** Lee `message` con el lector de pantalla (iOS lo encola para no cortar otra lectura). */
export function announce(message: string): void {
  const msg = message.trim();
  if (!msg) return;
  try {
    if (Platform.OS === 'ios') {
      AccessibilityInfo.announceForAccessibilityWithOptions(msg, { queue: true });
    } else {
      AccessibilityInfo.announceForAccessibility(msg);
    }
  } catch {
    // Sin lector o API no disponible: nada que hacer.
  }
}

/** ¿El sistema pide reducir movimiento? Se actualiza en vivo. */
export function useReduceMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((v) => alive && setReduce(v))
      .catch(() => {});
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', (v: boolean) => setReduce(v));
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);
  return reduce;
}

/** ¿Hay un lector de pantalla activo? Se actualiza en vivo. */
export function useScreenReader(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isScreenReaderEnabled()
      .then((v) => alive && setOn(v))
      .catch(() => {});
    const sub = AccessibilityInfo.addEventListener('screenReaderChanged', (v: boolean) => setOn(v));
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);
  return on;
}

/**
 * Mueve el foco del lector de pantalla al elemento de `ref` tras `delayMs` (deja que la
 * pantalla se monte/anime antes). Usa `sendAccessibilityEvent(…, 'focus')`, el sustituto
 * oficial de `setAccessibilityFocus(findNodeHandle(…))` (deprecado en RN 0.88).
 * Devuelve una función para cancelar.
 */
export function focusOn(ref: RefObject<HostInstance | null>, delayMs = 350): () => void {
  const id = setTimeout(() => {
    const node = ref.current;
    if (!node) return;
    try {
      AccessibilityInfo.sendAccessibilityEvent(node, 'focus');
    } catch {
      // El nodo ya no existe: ignorar.
    }
  }, delayMs);
  return () => clearTimeout(id);
}
