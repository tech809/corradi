/**
 * Confirmaciones breves ("Guardado", "Recordatorio puesto") en una píldora abajo.
 *
 *   const toast = useToast();
 *   toast.show('Guardado en tu lista', { actionLabel: 'Deshacer', onAction: () => unsave(id) });
 *
 * <ToastHost /> ya está montado en src/app/_layout.tsx (no lo montes otra vez).
 * - Duración: 3 s (o `duration`). Con una acción ("Deshacer"), al menos 8 s; en Android, lo que
 *   pida el ajuste de accesibilidad "Tiempo para actuar" (`getRecommendedTimeoutMillis`).
 *   Con acción y un lector de pantalla activo NO se oculta sola: sigue hasta la siguiente toast,
 *   hasta cambiar de pantalla o 30 s.
 * - El mensaje se anuncia UNA vez con `announce()` (sin región viva, que lo leería dos veces).
 *   Quien llama a showToast no debe anunciar lo mismo.
 * - Solo hay una a la vez: una nueva sustituye a la anterior.
 * - Al cambiar de pantalla se quita, salvo que el cambio llegue en los 300 ms siguientes a
 *   mostrarla (la toast que acompaña a una navegación la sobrevive) o que se pida
 *   `persistAcrossNavigation: true` (entonces solo se va por tiempo o con otra toast).
 * - Posición: la calcula el host según la ruta (está en el layout raíz, fuera de las pestañas):
 *   dentro del grupo (tabs), encima de la barra de pestañas (iOS 49 pt + borde seguro + 8;
 *   Android 80 + borde seguro + 8: alturas de la barra nativa SIN comprobar en dispositivo);
 *   fuera (ficha, bienvenida), borde seguro + 8. `offset` = distancia fija sobre el borde
 *   inferior seguro, si una pantalla necesita otra (p. ej. encima de una barra propia).
 */
import { usePathname, useSegments } from 'expo-router';
import { useEffect, useRef, useSyncExternalStore } from 'react';
import { AccessibilityInfo, Platform, Pressable, StyleSheet, View } from 'react-native';
import Animated, { FadeInDown, FadeOutDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, Fonts, MIN_TOUCH, Motion, Radius, Shadows, Spacing } from '@/constants/theme';
import { announce, useScreenReader } from '@/lib/a11y';

import { Icon, type IconName } from './icon';
import { AppText } from './text';

export interface ToastOptions {
  actionLabel?: string;
  onAction?: () => void;
  /** Milisegundos. Por defecto 3000 (con acción, mínimo 8000). */
  duration?: number;
  icon?: IconName;
  /** Distancia fija sobre el borde inferior seguro. Por defecto la decide el host según la ruta. */
  offset?: number;
  /** No se quita al cambiar de pantalla (solo por tiempo o con otra toast). */
  persistAcrossNavigation?: boolean;
}

interface ToastState extends ToastOptions {
  id: number;
  message: string;
  /** Date.now() al mostrarla. */
  at: number;
}

// Almacén mínimo a nivel de módulo: se puede llamar a showToast desde cualquier sitio.
let current: ToastState | null = null;
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function showToast(message: string, options: ToastOptions = {}): void {
  current = { ...options, message, id: ++seq, at: Date.now() };
  emit();
}

export function hideToast(): void {
  if (!current) return;
  current = null;
  emit();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};
const getSnapshot = () => current;

const API = { show: showToast, hide: hideToast } as const;

const DEFAULT_MS = 3000;
/** Toasts con acción: tiempo mínimo para leer y pulsar "Deshacer". */
const ACTION_MIN_MS = 8000;
/** Con lector de pantalla y acción, tope de tiempo en pantalla. */
const SCREEN_READER_ACTION_MAX_MS = 30_000;
/** Un cambio de ruta tan pronto tras mostrarla es la navegación que la acompaña: no la quita. */
const NAVIGATION_GRACE_MS = 300;
/** Margen visual sobre lo que haya debajo. */
const GAP = Spacing.sm;
/**
 * Alto de la barra de pestañas nativa (sin el borde seguro). iOS: UITabBar, 49 pt. Android:
 * barra de navegación Material 3, 80 dp. Leídos de la documentación de cada plataforma; SIN
 * comprobar en dispositivo con NativeTabs de SDK 58.
 */
const TAB_BAR_HEIGHT = Platform.OS === 'android' ? 80 : 49;

/** Devuelve `{ show, hide }` (referencias estables). */
export function useToast() {
  return API;
}

export function ToastHost() {
  const toast = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const screenReader = useScreenReader();
  const insets = useSafeAreaInsets();
  const segments = useSegments();
  const inTabs = (segments[0] as string | undefined) === '(tabs)';
  const pathname = usePathname();
  const announcedId = useRef(0);

  // Pantalla en la que apareció cada toast: si se cambia de pantalla después, se quita.
  const shownOnRef = useRef<{ id: number; path: string } | null>(null);
  useEffect(() => {
    if (!toast) return;
    const shown = shownOnRef.current;
    if (shown?.id !== toast.id) {
      shownOnRef.current = { id: toast.id, path: pathname };
      return;
    }
    if (shown.path === pathname || toast.persistAcrossNavigation) return;
    if (Date.now() - toast.at < NAVIGATION_GRACE_MS) {
      // Navegación que acompaña a la toast: la nueva pantalla pasa a ser la suya.
      shownOnRef.current = { id: toast.id, path: pathname };
      return;
    }
    hideToast();
  }, [toast, pathname]);

  useEffect(() => {
    if (!toast) return;
    if (toast.id !== announcedId.current) {
      announcedId.current = toast.id;
      announce(toast.actionLabel ? `${toast.message}. Botón ${toast.actionLabel} disponible.` : toast.message);
    }
    const id = toast.id;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const hideIn = (ms: number) => {
      if (cancelled) return;
      timer = setTimeout(() => {
        if (current?.id === id) hideToast();
      }, ms);
    };

    if (!toast.actionLabel) {
      hideIn(toast.duration ?? DEFAULT_MS);
    } else if (screenReader) {
      hideIn(SCREEN_READER_ACTION_MAX_MS);
    } else {
      const wanted = Math.max(toast.duration ?? ACTION_MIN_MS, ACTION_MIN_MS);
      // Android: respeta el ajuste "Tiempo para actuar"; iOS devuelve el mismo valor.
      AccessibilityInfo.getRecommendedTimeoutMillis(wanted).then(
        (ms) => hideIn(Math.max(ms, wanted)),
        () => hideIn(wanted),
      );
    }
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [toast, screenReader]);

  if (!toast) return null;

  const bottom =
    toast.offset != null ? insets.bottom + toast.offset : inTabs ? TAB_BAR_HEIGHT + insets.bottom + GAP : insets.bottom + GAP;

  return (
    <View pointerEvents="box-none" style={[styles.host, { bottom }]}>
      <Animated.View
        key={toast.id}
        entering={FadeInDown.duration(Motion.pop.duration)}
        exiting={FadeOutDown.duration(Motion.pop.duration)}
        style={styles.pill}>
        {toast.icon ? <Icon name={toast.icon} size={18} color={Colors.paper} /> : null}
        <AppText variant="body" color={Colors.paper} style={styles.message}>
          {toast.message}
        </AppText>
        {toast.actionLabel ? (
          <Pressable
            onPress={() => {
              toast.onAction?.();
              hideToast();
            }}
            accessibilityRole="button"
            accessibilityLabel={toast.actionLabel}
            style={({ pressed }) => [styles.action, pressed && styles.actionPressed]}>
            <AppText variant="label" color={Colors.peach} style={styles.actionText}>
              {toast.actionLabel}
            </AppText>
          </Pressable>
        ) : null}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  host: { position: 'absolute', left: Spacing.md, right: Spacing.md, alignItems: 'center' },
  pill: {
    maxWidth: 520,
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingLeft: Spacing.ml,
    paddingRight: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: Radius.xl,
    backgroundColor: Colors.inkDeep,
    ...Shadows.md,
  },
  message: { flexShrink: 1, paddingVertical: Spacing.sm, paddingRight: Spacing.sm },
  action: {
    minHeight: MIN_TOUCH,
    minWidth: MIN_TOUCH,
    paddingHorizontal: Spacing.ms,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionPressed: { backgroundColor: Colors.overlayLight },
  actionText: { fontFamily: Fonts.sansBold },
});
