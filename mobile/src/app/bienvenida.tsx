import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  BackHandler,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
  type HostInstance,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/button';
import { TypeDot } from '@/components/chip';
import { Icon } from '@/components/icon';
import { AppText } from '@/components/text';
import { showToast } from '@/components/toast';
import { Colors, Motion, Radius, Spacing } from '@/constants/theme';
import { focusOn, useReduceMotion } from '@/lib/a11y';
import { typeLabel } from '@/lib/format';
import { tapSelection, tapSuccess } from '@/lib/haptics';
import {
  ALL_TYPES,
  UNAVAILABLE_MESSAGE,
  disableDigest,
  enableDigest,
  markWelcomeDone,
  setDigestTypes,
  type PushResult,
} from '@/lib/push';
import type { OpportunityType } from '@/lib/types';

/** Foto 4:3 (1200×900, ver README › Recursos gráficos): se muestra entera, sin recortes. */
const PHOTO = require('@/assets/images/welcome.jpg');
const PHOTO_ASPECT = 4 / 3;
const MARK = require('@/assets/brand/corradi-mark-clay.png');

/**
 * Qué es cada tipo, en una línea bajo su casilla. Resumen de TYPE_EXPLAINERS (src/lib/types.ts):
 * si cambia allí, cambia aquí.
 */
const TYPE_SHORT_EXPLAINERS: Record<OpportunityType, string> = {
  YOUTH_EXCHANGE: 'De 5 a 21 días con jóvenes de otros países',
  TRAINING_COURSE: 'Para quien trabaja con jóvenes (monitores, educadores)',
  VOLUNTEERING: 'De 2 semanas a 12 meses en otro país, con gastos cubiertos',
};

/** Velo arriba de la foto (inkDeep al 45 % → 0) para que la barra de estado blanca se lea. */
const TOP_SCRIM_GRADIENT = 'linear-gradient(to bottom, rgba(27,40,30,0.45), rgba(27,40,30,0))';
/** Fundido de la foto a papel (paper transparente → paper). */
const PAPER_FADE_GRADIENT = `linear-gradient(to bottom, rgba(247,240,226,0) 0%, ${Colors.paper} 100%)`;

/** Mensaje tras elegir, según lo que haya pasado de verdad. */
const RESULT_MESSAGE: Record<PushResult, string> = {
  enabled: 'Listo: te avisamos cuando haya proyectos nuevos.',
  pending: 'Listo: activaremos los avisos en cuanto haya conexión.',
  denied: 'Sin permiso de notificaciones no podemos avisarte. Puedes activarlo en Ajustes.',
  unavailable: UNAVAILABLE_MESSAGE,
  disabled: 'Sin avisos. Puedes activarlos cuando quieras en Ajustes.',
};

/**
 * Primera apertura: qué es Corradi, qué tipos de proyecto le interesan y si quiere el resumen
 * diario. Solo se ve una vez. Va a pantalla completa (fullScreenModal en _layout) y no se puede
 * cerrar sin elegir: en Android el botón "atrás" cuenta como "Ahora no". Los tipos marcados se
 * guardan con cualquiera de las dos respuestas (filtran también la pestaña Nuevos).
 */
export default function BienvenidaScreen() {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const reduceMotion = useReduceMotion();
  const titleRef = useRef<HostInstance>(null);
  // Guardia contra el doble toque: el estado tarda un render en desactivar los botones.
  const choosing = useRef(false);
  const [busy, setBusy] = useState<'activate' | 'skip' | null>(null);
  const [types, setTypes] = useState<OpportunityType[]>([...ALL_TYPES]);
  // Barra de estado clara sobre la foto; oscura cuando la foto ya ha salido por arriba.
  const [pastPhoto, setPastPhoto] = useState(false);
  const photoHeight = Math.round(width / PHOTO_ASPECT);

  useEffect(() => focusOn(titleRef, 500), []);

  const choose = useCallback(
    async (activate: boolean) => {
      if (choosing.current) return;
      choosing.current = true;
      setBusy(activate ? 'activate' : 'skip');
      let result: PushResult = 'disabled';
      try {
        if (activate) {
          result = await enableDigest({ types });
        } else {
          result = await disableDigest();
          await setDigestTypes(types);
        }
      } catch {
        // push.ts no lanza errores; por si acaso, la bienvenida se cierra igual
      } finally {
        await markWelcomeDone();
        setBusy(null);
        if (router.canGoBack()) router.back();
        else router.replace('/');
        const ok = result === 'enabled' || result === 'pending';
        if (ok) tapSuccess();
        // Se cierra la bienvenida a la vez: el resultado tiene que verse en la pantalla de destino.
        showToast(RESULT_MESSAGE[result], { icon: ok ? 'bellFill' : 'info', persistAcrossNavigation: true });
      }
    },
    [types],
  );

  // Android: "atrás" = "Ahora no" (nunca se cierra sin dejar la bienvenida resuelta).
  useFocusEffect(
    useCallback(() => {
      const sub = BackHandler.addEventListener('hardwareBackPress', () => {
        void choose(false);
        return true;
      });
      return () => sub.remove();
    }, [choose]),
  );

  const toggleType = (t: OpportunityType) => {
    const has = types.includes(t);
    if (has && types.length === 1) {
      // showToast ya lo anuncia.
      showToast('Deja al menos un tipo marcado', { icon: 'info' });
      return;
    }
    tapSelection();
    setTypes(has ? types.filter((x) => x !== t) : ALL_TYPES.filter((x) => x === t || types.includes(x)));
  };

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const past = e.nativeEvent.contentOffset.y > photoHeight - insets.top - 24;
    if (past !== pastPhoto) setPastPhoto(past);
  };

  const enter = (i: number) =>
    reduceMotion ? undefined : FadeInDown.delay(120 + i * Motion.enter.stagger * 2).duration(Motion.enter.duration * 1.5);

  return (
    <View style={styles.root}>
      <StatusBar style={pastPhoto ? 'dark' : 'light'} />
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        contentInsetAdjustmentBehavior="never"
        showsVerticalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={32}>
        {/* La foto va DENTRO del scroll: el texto nunca pasa por encima de ella. */}
        <View style={[styles.photoWrap, { height: photoHeight }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Image source={PHOTO} style={StyleSheet.absoluteFill} contentFit="cover" accessible={false} />
          <View style={[styles.topScrim, { height: insets.top + 56 }]} />
          <View style={styles.fade} />
        </View>

        <View style={styles.content}>
          <Animated.View entering={enter(0)}>
            <Image source={MARK} style={styles.mark} contentFit="contain" accessible={false} />
          </Animated.View>
          <Animated.View entering={enter(1)} style={styles.texts}>
            <AppText variant="eyebrow" color={Colors.clayText}>
              Erasmus+ en claro
            </AppText>
            <AppText ref={titleRef} variant="title1" accessibilityRole="header" maxFontSizeMultiplier={1.4}>
              Proyectos por Europa, casi siempre con alojamiento y comida pagados
            </AppText>
          </Animated.View>
          <Animated.View entering={enter(2)}>
            <AppText variant="bodyLg" color={Colors.ink2}>
              Intercambios, cursos y voluntariado con Erasmus+ para quien vive en España. Te avisamos una vez al día si hay
              novedades.
            </AppText>
          </Animated.View>

          <Animated.View entering={enter(3)} style={styles.interests}>
            <AppText variant="label" accessibilityRole="header">
              ¿Qué te interesa?
            </AppText>
            <View style={styles.group}>
              {ALL_TYPES.map((t, i) => {
                const checked = types.includes(t);
                return (
                  <Pressable
                    key={t}
                    onPress={() => toggleType(t)}
                    disabled={busy !== null}
                    accessibilityRole="checkbox"
                    accessibilityLabel={`${typeLabel(t)}. ${TYPE_SHORT_EXPLAINERS[t]}`}
                    accessibilityState={{ checked, disabled: busy !== null }}
                    style={({ pressed }) => [styles.row, i > 0 && styles.rowDivider, pressed && styles.rowPressed]}>
                    <TypeDot type={t} size={20} />
                    <View style={styles.rowText}>
                      <AppText variant="body">{typeLabel(t)}</AppText>
                      <AppText variant="meta" color={Colors.muted}>
                        {TYPE_SHORT_EXPLAINERS[t]}
                      </AppText>
                    </View>
                    <View style={[styles.checkbox, checked && styles.checkboxOn]}>
                      {checked ? <Icon name="check" size={16} color={Colors.white} /> : null}
                    </View>
                  </Pressable>
                );
              })}
            </View>
          </Animated.View>
        </View>
      </ScrollView>

      <View style={[styles.actions, { paddingBottom: insets.bottom + Spacing.md }]}>
        <Button
          label="Activar avisos"
          icon="bell"
          onPress={() => choose(true)}
          loading={busy === 'activate'}
          disabled={busy === 'skip'}
          accessibilityHint="Te pediremos permiso para enviarte notificaciones"
        />
        <Button label="Ahora no" variant="secondary" onPress={() => choose(false)} loading={busy === 'skip'} disabled={busy === 'activate'} />
        <AppText variant="caption" color={Colors.muted} align="center">
          Puedes cambiarlo cuando quieras en Ajustes.
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.paper },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: Spacing.lg },
  photoWrap: { backgroundColor: Colors.paper2, overflow: 'hidden' },
  // Velo arriba para que la barra de estado (texto blanco) se lea sobre cualquier foto.
  topScrim: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundImage: TOP_SCRIM_GRADIENT,
  },
  // Fundido a papel en el borde inferior de la foto (gradiente nativo de RN, sin dependencias).
  fade: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: '30%',
    backgroundImage: PAPER_FADE_GRADIENT,
  },
  content: { paddingHorizontal: Spacing.lg, gap: Spacing.md },
  mark: { width: 44, height: 44 },
  texts: { gap: Spacing.sm },
  interests: { gap: Spacing.sm, marginTop: Spacing.xs },
  group: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.rule,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.ms,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.ms,
    minHeight: 52,
  },
  rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: Colors.rule },
  rowPressed: { backgroundColor: Colors.paper2 },
  rowText: { flex: 1, gap: Spacing.xxs },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: Radius.xs,
    borderWidth: 1.5,
    borderColor: Colors.controlBorder,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surface,
  },
  checkboxOn: { backgroundColor: Colors.clay, borderColor: Colors.clay },
  actions: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.ms,
    gap: Spacing.sm,
    backgroundColor: Colors.paper,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.rule,
  },
});
