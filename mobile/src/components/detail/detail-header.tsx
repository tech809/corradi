/**
 * Cabecera propia de la ficha: transparente encima de la portada, con botones de 44×44 sobre
 * un círculo tinta translúcido (volver, guardar, compartir), legible sobre cualquier foto. Al hacer scroll el fondo pasa a
 * papel y los iconos a tinta; el título pequeño aparece cuando el titular grande ya no se ve.
 * Con "reducir movimiento" no hay fundidos: cambia de golpe.
 */
import { useEffect, useRef } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';
import Animated, {
  Extrapolation,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withTiming,
  type SharedValue,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { SymbolView } from 'expo-symbols';

import { Icon, type IconName } from '@/components/icon';
import { AppText } from '@/components/text';
import { Colors, Fonts, MIN_TOUCH, Spacing } from '@/constants/theme';

/** Alto de la barra (sin la zona segura de arriba). */
export const HEADER_BAR_HEIGHT = 52;
/** Distancia de scroll en la que se funde el fondo. */
const FADE_RANGE = 48;

export interface DetailHeaderProps {
  scrollY: SharedValue<number>;
  /** Scroll a partir del cual el fondo es papel del todo (fin de la portada). */
  solidAt: SharedValue<number>;
  /** Scroll a partir del cual el titular grande ya no se ve. */
  titleAt: SharedValue<number>;
  reduceMotion: boolean;
  /** true cuando se enseña el título pequeño. */
  titleVisible: boolean;
  title: string;
  onBack: () => void;
  /** Sin `actions` solo se ve "Volver" (carga y error). */
  actions?: {
    saved: boolean;
    onSave: () => void;
    sharing: boolean;
    onShare: () => void;
  };
}

export function DetailHeader({
  scrollY,
  solidAt,
  titleAt,
  reduceMotion,
  titleVisible,
  title,
  onBack,
  actions,
}: DetailHeaderProps) {
  const insets = useSafeAreaInsets();

  // 0 = transparente sobre la portada, 1 = papel.
  const bgStyle = useAnimatedStyle(() => {
    const y = scrollY.get();
    const end = solidAt.get();
    const p = reduceMotion
      ? y >= end
        ? 1
        : 0
      : interpolate(y, [end - FADE_RANGE, end], [0, 1], Extrapolation.CLAMP);
    return { opacity: p };
  });

  const titleStyle = useAnimatedStyle(() => {
    const y = scrollY.get();
    const at = titleAt.get();
    const p = reduceMotion ? (y >= at ? 1 : 0) : interpolate(y, [at - 24, at], [0, 1], Extrapolation.CLAMP);
    return { opacity: p };
  });

  return (
    <View style={[styles.wrap, { paddingTop: insets.top }]} pointerEvents="box-none">
      <Animated.View style={[StyleSheet.absoluteFill, styles.bg, bgStyle]} pointerEvents="none" />
      <View style={styles.bar} pointerEvents="box-none">
        <HeaderButton
          icon="back"
          label="Volver"
          onPress={onBack}
          scrollY={scrollY}
          solidAt={solidAt}
          reduceMotion={reduceMotion}
        />
        <Animated.View
          style={[styles.titleWrap, titleStyle]}
          pointerEvents="none"
          accessibilityElementsHidden={!titleVisible}
          importantForAccessibility={titleVisible ? 'auto' : 'no-hide-descendants'}>
          {/* Sin rol de titular: el titular de la pantalla es el título grande (no duplicarlo). */}
          <AppText variant="label" numberOfLines={1} style={styles.title}>
            {title}
          </AppText>
        </Animated.View>
        {actions ? (
          <View style={styles.actions}>
            <HeaderButton
              icon={actions.saved ? 'bookmarkFill' : 'bookmark'}
              // Etiqueta fija; el estado lo dice `selected` ("Guardar, seleccionado").
              label="Guardar"
              hint={actions.saved ? 'Quita el proyecto de guardados y cancela el aviso' : 'Guarda el proyecto y te avisa antes de que cierre'}
              selected={actions.saved}
              onPress={actions.onSave}
              scrollY={scrollY}
              solidAt={solidAt}
              reduceMotion={reduceMotion}
              pop={actions.saved}
              // Sobre foto, siempre blanco: el marcador relleno ya dice que está guardado.
              darkColor={actions.saved ? Colors.clayText : Colors.ink}
            />
            <HeaderButton
              icon="share"
              label={actions.sharing ? 'Preparando para compartir' : 'Compartir proyecto'}
              onPress={actions.onShare}
              busy={actions.sharing}
              scrollY={scrollY}
              solidAt={solidAt}
              reduceMotion={reduceMotion}
            />
          </View>
        ) : null}
      </View>
      {/* Separador que aparece con el fondo. */}
      <Animated.View style={[styles.rule, bgStyle]} pointerEvents="none" />
    </View>
  );
}

/** El juego de iconos compartido no tiene "atrás": se usa el símbolo del sistema. */
function Glyph({ icon, color }: { icon: IconName | 'back'; color: string }) {
  if (icon === 'back') {
    return (
      <SymbolView
        name={{ ios: 'chevron.left', android: 'arrow_back' }}
        size={20}
        tintColor={color}
        accessibilityElementsHidden
        importantForAccessibility="no"
      />
    );
  }
  return <Icon name={icon} size={20} color={color} />;
}

interface HeaderButtonProps {
  icon: IconName | 'back';
  label: string;
  hint?: string;
  onPress: () => void;
  scrollY: SharedValue<number>;
  solidAt: SharedValue<number>;
  reduceMotion: boolean;
  selected?: boolean;
  busy?: boolean;
  /** Cambia de valor → pequeño "pop" del icono (p. ej. al guardar). */
  pop?: boolean;
  lightColor?: string;
  darkColor?: string;
}

function HeaderButton({
  icon,
  label,
  hint,
  onPress,
  scrollY,
  solidAt,
  reduceMotion,
  selected,
  busy,
  pop,
  lightColor = Colors.onPhoto,
  darkColor = Colors.ink,
}: HeaderButtonProps) {
  const scale = useSharedValue(1);
  const lastPop = useRef(pop);

  useEffect(() => {
    if (lastPop.current === pop) return;
    lastPop.current = pop;
    if (reduceMotion || !pop) return;
    scale.set(withSequence(withTiming(1.3, { duration: 110 }), withTiming(1, { duration: 140 })));
  }, [pop, reduceMotion, scale]);

  // Círculo oscuro y icono claro sobre la portada; sin círculo e icono tinta sobre papel.
  const lightStyle = useAnimatedStyle(() => {
    const y = scrollY.get();
    const end = solidAt.get();
    const p = reduceMotion ? (y >= end ? 1 : 0) : interpolate(y, [end - FADE_RANGE, end], [0, 1], Extrapolation.CLAMP);
    return { opacity: 1 - p };
  });
  const darkStyle = useAnimatedStyle(() => {
    const y = scrollY.get();
    const end = solidAt.get();
    const p = reduceMotion ? (y >= end ? 1 : 0) : interpolate(y, [end - FADE_RANGE, end], [0, 1], Extrapolation.CLAMP);
    return { opacity: p };
  });
  const popStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.get() }] }));

  return (
    <Pressable
      onPress={onPress}
      disabled={busy}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={hint}
      accessibilityState={{ selected: !!selected, busy: !!busy, disabled: !!busy }}
      style={({ pressed }) => [styles.btn, pressed && styles.pressed]}>
      <Animated.View style={[StyleSheet.absoluteFill, styles.circle, lightStyle]} />
      {busy ? (
        <View style={styles.center}>
          <Animated.View style={[styles.layer, lightStyle]}>
            <ActivityIndicator size="small" color={lightColor} />
          </Animated.View>
          <Animated.View style={[styles.layer, darkStyle]}>
            <ActivityIndicator size="small" color={darkColor} />
          </Animated.View>
        </View>
      ) : (
        <Animated.View style={[styles.center, popStyle]}>
          <Animated.View style={[styles.layer, lightStyle]}>
            <Glyph icon={icon} color={lightColor} />
          </Animated.View>
          <Animated.View style={[styles.layer, darkStyle]}>
            <Glyph icon={icon} color={darkColor} />
          </Animated.View>
        </Animated.View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10 },
  bg: { backgroundColor: Colors.paper },
  bar: {
    height: HEADER_BAR_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.ms,
    gap: Spacing.sm,
  },
  titleWrap: { flex: 1, justifyContent: 'center' },
  title: { fontFamily: Fonts.sansSemiBold, textAlign: 'center' },
  actions: { flexDirection: 'row', gap: Spacing.sm },
  rule: { height: StyleSheet.hairlineWidth, backgroundColor: Colors.rule },
  btn: {
    width: MIN_TOUCH,
    height: MIN_TOUCH,
    borderRadius: MIN_TOUCH / 2,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressed: { opacity: 0.7 },
  circle: { backgroundColor: Colors.photoButtonBg, borderRadius: MIN_TOUCH / 2 },
  center: { width: 24, height: 24 },
  layer: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' },
});
