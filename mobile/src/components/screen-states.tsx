/**
 * Estados de pantalla compartidos.
 *
 * - <EmptyState title text action={{ label, onPress }} />  marca Corradi + titular + texto.
 *   `children` sigue funcionando para acciones a medida. `icon` se ignora (antes era un icono).
 * - <OfflineBanner onRetry />  aviso "sin conexión" (se anuncia una vez al aparecer; sin región viva
 *   para no leerlo dos veces).
 * - <CardSkeletons count label />  tarjetas fantasma con pulso (sin pulso si se reduce movimiento).
 *   Es UN elemento "progressbar" con `label` ("Cargando proyectos" por defecto): no pongas al lado
 *   otro texto de carga con región viva (se leería dos veces).
 */
import { Image } from 'expo-image';
import { useEffect, type ReactNode, type Ref } from 'react';
import { Pressable, StyleSheet, View, type HostInstance } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';

import { CardBorder, Colors, MIN_TOUCH, Radius, Shadows, Sizes, Spacing } from '@/constants/theme';
import { announce, useReduceMotion } from '@/lib/a11y';

import { Button, type ButtonProps } from './button';
import { Icon, type IconName } from './icon';
import { AppText } from './text';

const MARK_CLAY = require('@/assets/brand/corradi-mark-clay.png');

export interface EmptyStateProps {
  title: string;
  text?: string | null;
  /** Acción principal opcional (un Button). */
  action?: Pick<ButtonProps, 'label' | 'onPress' | 'icon' | 'loading' | 'variant' | 'accessibilityHint'>;
  /** @deprecated Ya no se pinta: la cabecera es la marca Corradi. */
  icon?: IconName;
  /** Acciones a medida (se apilan debajo). */
  children?: ReactNode;
  /** Ref al titular, para mover el foco del lector. */
  titleRef?: Ref<HostInstance>;
}

export function EmptyState({ title, text, action, children, titleRef }: EmptyStateProps) {
  return (
    <View style={styles.empty}>
      <Image source={MARK_CLAY} style={styles.mark} contentFit="contain" accessible={false} accessibilityElementsHidden importantForAccessibility="no" />
      <AppText ref={titleRef} variant="title3" align="center" accessibilityRole="header">
        {title}
      </AppText>
      {text ? (
        <AppText variant="body" color={Colors.muted} align="center" style={styles.text}>
          {text}
        </AppText>
      ) : null}
      {action || children ? (
        <View style={styles.actions}>
          {action ? <Button {...action} /> : null}
          {children}
        </View>
      ) : null}
    </View>
  );
}

export interface OfflineBannerProps {
  onRetry: () => void;
  message?: string;
}

/** Aviso de que se enseñan datos guardados porque no hay conexión. Todo el aviso es el botón. */
export function OfflineBanner({ onRetry, message = 'Sin conexión: te enseñamos lo último que guardamos.' }: OfflineBannerProps) {
  useEffect(() => {
    // Al aparecer (y solo si cambia el texto).
    announce(message);
  }, [message]);

  return (
    <Pressable
      onPress={onRetry}
      accessibilityRole="button"
      accessibilityLabel={`${message} Reintentar.`}
      accessibilityHint="Vuelve a cargar los proyectos"
      style={({ pressed }) => [styles.banner, pressed && styles.bannerPressed]}>
      <Icon name="offline" size={18} color={Colors.ink2} />
      <AppText variant="meta" color={Colors.ink2} style={styles.bannerText}>
        {message}
      </AppText>
      <AppText variant="label" color={Colors.ink}>
        Reintentar
      </AppText>
    </Pressable>
  );
}

/** Tarjetas fantasma mientras llega la primera carga (misma forma que OpportunityCard). */
export function CardSkeletons({
  count = 3,
  compact = false,
  label = 'Cargando proyectos',
}: {
  count?: number;
  compact?: boolean;
  /** Lo que lee el lector de pantalla. */
  label?: string;
}) {
  const reduceMotion = useReduceMotion();
  const opacity = useSharedValue(1);

  useEffect(() => {
    if (reduceMotion) {
      cancelAnimation(opacity);
      opacity.set(1);
      return;
    }
    opacity.set(withRepeat(withTiming(0.5, { duration: 900 }), -1, true));
    return () => cancelAnimation(opacity);
  }, [reduceMotion, opacity]);

  const pulse = useAnimatedStyle(() => ({ opacity: opacity.get() }));

  return (
    <View
      style={styles.skeletons}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityState={{ busy: true }}>
      {Array.from({ length: count }, (_, i) =>
        compact ? (
          <Animated.View key={i} style={[styles.skeleton, styles.skeletonCompact, pulse]}>
            <View style={[styles.bar, styles.thumb]} />
            <View style={styles.compactLines}>
              <View style={[styles.bar, { width: '85%', height: 16 }]} />
              <View style={[styles.bar, { width: '55%', height: 12 }]} />
            </View>
          </Animated.View>
        ) : (
          <Animated.View key={i} style={[styles.skeleton, pulse]}>
            <View style={styles.coverBar} />
            <View style={styles.body}>
              <View style={[styles.bar, { width: '92%', height: 20 }]} />
              <View style={[styles.bar, { width: '64%', height: 20 }]} />
              <View style={[styles.bar, { width: '70%', height: 13, marginTop: 4 }]} />
              <View style={[styles.bar, { width: '40%', height: 13 }]} />
            </View>
          </Animated.View>
        ),
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { alignItems: 'center', paddingHorizontal: Spacing.lg, paddingVertical: Spacing.xl, gap: Spacing.sm },
  mark: { width: 56, height: 56, marginBottom: Spacing.sm },
  text: { maxWidth: 300 },
  actions: { marginTop: Spacing.md, gap: Spacing.sm, alignItems: 'center', alignSelf: 'stretch' },
  banner: {
    minHeight: MIN_TOUCH,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.sage,
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.ms,
    paddingVertical: Spacing.sm,
  },
  bannerPressed: { opacity: 0.8 },
  bannerText: { flex: 1 },
  skeletons: { gap: Spacing.ms },
  skeleton: { backgroundColor: Colors.surface, borderRadius: Radius.card, overflow: 'hidden', ...CardBorder, ...Shadows.card },
  skeletonCompact: { flexDirection: 'row', alignItems: 'center', padding: Spacing.ms, gap: Spacing.ms },
  coverBar: { height: Sizes.cardCover, backgroundColor: Colors.paper2 },
  body: { padding: Spacing.md, gap: Spacing.sm },
  bar: { backgroundColor: Colors.paper2, borderRadius: Radius.xs },
  thumb: { width: Sizes.thumb, height: Sizes.thumb, borderRadius: Radius.sm },
  compactLines: { flex: 1, gap: Spacing.sm },
});
