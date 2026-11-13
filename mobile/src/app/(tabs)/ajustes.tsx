import * as Application from 'expo-application';
import { useFocusEffect } from 'expo-router';
import * as StoreReview from 'expo-store-review';
import * as WebBrowser from 'expo-web-browser';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { AppState, Linking, Platform, Pressable, ScrollView, Share, StyleSheet, Switch, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/button';
import { TypeDot } from '@/components/chip';
import { Icon, type IconName } from '@/components/icon';
import { TabHeader } from '@/components/tab-header';
import { AppText } from '@/components/text';
import { showToast } from '@/components/toast';
import { Colors, Radius, Spacing, typeColor } from '@/constants/theme';
import { WEB_URLS } from '@/lib/config';
import { typeExplainer, typeLabel } from '@/lib/format';
import { tapSelection } from '@/lib/haptics';
import {
  ALL_TYPES,
  UNAVAILABLE_MESSAGE,
  disableDigest,
  enableDigest,
  getPermissionState,
  pushSupported,
  setDigestTypes,
  usePushPrefs,
  type PermissionState,
  type PushResult,
} from '@/lib/push';
import type { OpportunityType } from '@/lib/types';

const ROW_MIN_HEIGHT = 52;
const TILE = 28;

const TOGGLE_MESSAGE: Partial<Record<PushResult, string>> = {
  pending: 'Guardado: activaremos los avisos en cuanto haya conexión.',
  denied: 'Sin permiso de notificaciones no podemos avisarte.',
  unavailable: UNAVAILABLE_MESSAGE,
};

export default function AjustesScreen() {
  const insets = useSafeAreaInsets();
  const prefs = usePushPrefs();
  const supported = pushSupported();
  const [permission, setPermission] = useState<PermissionState>('undetermined');
  const [busy, setBusy] = useState(false);
  const [canReview, setCanReview] = useState(false);

  const refreshPermission = useCallback(() => {
    void getPermissionState().then(setPermission);
  }, []);

  // Al entrar en la pestaña y al volver de los ajustes del sistema.
  useFocusEffect(refreshPermission);
  useEffect(() => {
    const sub = AppState.addEventListener('change', (s) => s === 'active' && refreshPermission());
    return () => sub.remove();
  }, [refreshPermission]);

  useEffect(() => {
    void StoreReview.hasAction()
      .then((ok) => setCanReview(ok || !!StoreReview.storeUrl()))
      .catch(() => setCanReview(false));
  }, []);

  const blocked = !supported || permission === 'denied';
  const digestOn = !!prefs?.digest && supported && permission === 'granted';

  const status = !supported
    ? UNAVAILABLE_MESSAGE
    : permission === 'denied'
      ? 'Las notificaciones de Corradi están desactivadas en el sistema.'
      : digestOn
        ? 'Activado: un aviso hacia las 19:30, solo si hay novedades de lo que te interesa.'
        : 'Desactivado.';
  const switchDisabled = !prefs || busy || blocked;

  // Guardia contra el doble toque: `busy` tarda un render en desactivar el interruptor.
  const toggling = useRef(false);
  const toggleDigest = async (value: boolean) => {
    if (toggling.current) return;
    toggling.current = true;
    setBusy(true);
    try {
      const result = value ? await enableDigest() : await disableDigest();
      const msg = TOGGLE_MESSAGE[result];
      if (msg) showToast(msg, { icon: 'info' });
    } finally {
      refreshPermission();
      setBusy(false);
      toggling.current = false;
    }
  };

  const toggleType = (t: OpportunityType) => {
    if (!prefs) return;
    const has = prefs.types.includes(t);
    if (has && prefs.types.length === 1) {
      showToast('Deja al menos un tipo marcado', { icon: 'info' });
      return;
    }
    tapSelection();
    const next = has ? prefs.types.filter((x) => x !== t) : ALL_TYPES.filter((x) => x === t || prefs.types.includes(x));
    void setDigestTypes(next);
  };

  const openWeb = (url: string) =>
    WebBrowser.openBrowserAsync(url, { toolbarColor: Colors.paper, controlsColor: Colors.clay }).catch(() =>
      Linking.openURL(url),
    );

  const review = async () => {
    try {
      if (await StoreReview.hasAction()) await StoreReview.requestReview();
      else {
        const url = StoreReview.storeUrl();
        if (url) await Linking.openURL(url);
      }
    } catch {
      // sin tienda disponible: no hacer nada
    }
  };

  const share = () =>
    Share.share({
      message: `Corradi: intercambios, cursos y voluntariado Erasmus+ para jóvenes que viven en España. ${WEB_URLS.home}`,
    }).catch(() => {});

  const version = Application.nativeApplicationVersion;
  const build = Application.nativeBuildVersion;

  return (
    <ScrollView
      style={styles.root}
      // iOS ya añade el margen superior seguro (contentInsetAdjustmentBehavior); Android no.
      contentInsetAdjustmentBehavior="automatic"
      contentContainerStyle={[styles.content, Platform.OS === 'android' && { paddingTop: insets.top }]}>
      <TabHeader title="Ajustes" />

      <Section title="Avisos" subtitle="Al guardar un proyecto te avisamos 3 días antes de que cierre.">
        {/* Toda la fila es un único elemento accesible (rol switch); el Switch es solo visual. */}
        <Pressable
          onPress={() => void toggleDigest(!digestOn)}
          disabled={switchDisabled}
          accessible
          accessibilityRole="switch"
          accessibilityLabel="Resumen diario de proyectos nuevos"
          accessibilityState={{ checked: digestOn, disabled: switchDisabled, busy }}
          accessibilityHint={
            !supported
              ? UNAVAILABLE_MESSAGE
              : permission === 'denied'
                ? 'Desactivado en los ajustes del sistema. Usa el botón Abrir ajustes del sistema.'
                : undefined
          }
          style={({ pressed }) => [styles.row, pressed && !switchDisabled && styles.rowPressed]}>
          <Tile icon="bell" bg={Colors.clay} />
          <AppText variant="bodyLg" style={[styles.rowText, styles.rowTitle]}>
            Resumen diario de proyectos nuevos
          </AppText>
          <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            <Switch
              value={digestOn}
              onValueChange={(v) => void toggleDigest(v)}
              disabled={switchDisabled}
              trackColor={{ true: Colors.clay, false: Colors.controlBorder }}
              thumbColor={Colors.white}
              ios_backgroundColor={Colors.controlBorder}
            />
          </View>
        </Pressable>
        <View style={[styles.status, permission === 'denied' && supported && styles.statusWarn]}>
          <AppText variant="meta" color={Colors.ink2} accessibilityLiveRegion="polite">
            {status}
          </AppText>
          {supported && permission === 'denied' ? (
            <Button
              label="Abrir ajustes del sistema"
              variant="secondary"
              onPress={() => void Linking.openSettings()}
              style={styles.statusButton}
            />
          ) : null}
        </View>
      </Section>

      <Section title="Me interesa" subtitle="Lo que marques filtra la pestaña Nuevos y el resumen diario.">
        {ALL_TYPES.map((t, i) => {
          const checked = !!prefs?.types.includes(t);
          return (
            <Pressable
              key={t}
              onPress={() => toggleType(t)}
              disabled={!prefs}
              accessibilityRole="checkbox"
              accessibilityLabel={typeLabel(t)}
              accessibilityHint={typeExplainer(t) ?? undefined}
              accessibilityState={{ checked, disabled: !prefs }}
              style={({ pressed }) => [styles.row, i > 0 && styles.rowDivider, pressed && styles.rowPressed]}>
              <View style={[styles.tile, { backgroundColor: typeColor(t).chipBg }]}>
                <TypeDot type={t} size={20} />
              </View>
              <View style={styles.rowText}>
                <AppText variant="bodyLg" style={styles.rowTitle}>
                  {typeLabel(t)}
                </AppText>
                <AppText variant="meta" color={Colors.muted}>
                  {typeExplainer(t)}
                </AppText>
              </View>
              <View style={[styles.checkbox, checked && styles.checkboxOn]}>
                {checked ? <Icon name="check" size={16} color={Colors.white} /> : null}
              </View>
            </Pressable>
          );
        })}
      </Section>

      <Section title="Corradi">
        <LinkRow icon="doc" label="Guía para tu primer proyecto" onPress={() => openWeb(WEB_URLS.guia)} />
        <LinkRow icon="people" label="Quiénes somos" onPress={() => openWeb(WEB_URLS.quienesSomos)} divider />
        <LinkRow icon="info" label="Privacidad" onPress={() => openWeb(WEB_URLS.privacidad)} divider />
      </Section>

      <Section>
        {canReview ? <LinkRow icon="checkCircle" label="Valorar Corradi" onPress={review} internal /> : null}
        <LinkRow icon="share" label="Compartir la app" onPress={share} internal divider={canReview} />
      </Section>

      <View style={styles.footer}>
        <AppText variant="caption" color={Colors.muted} align="center">
          Corradi {version ?? ''}
          {build ? ` (${build})` : ''}
        </AppText>
        <AppText variant="caption" color={Colors.muted} align="center">
          Un proyecto de Proactive Future · cofinanciado por Erasmus+
        </AppText>
      </View>
    </ScrollView>
  );
}

function Section({ title, subtitle, children }: { title?: string; subtitle?: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      {title ? (
        <AppText variant="eyebrow" color={Colors.muted} accessibilityRole="header" style={styles.sectionTitle}>
          {title}
        </AppText>
      ) : null}
      {subtitle ? (
        <AppText variant="meta" color={Colors.muted} style={styles.sectionSub}>
          {subtitle}
        </AppText>
      ) : null}
      <View style={styles.group}>{children}</View>
    </View>
  );
}

function Tile({ icon, bg }: { icon: IconName; bg: string }) {
  return (
    <View style={[styles.tile, { backgroundColor: bg }]}>
      <Icon name={icon} size={16} color={Colors.white} />
    </View>
  );
}

function LinkRow({
  icon,
  label,
  onPress,
  internal,
  divider,
}: {
  icon: IconName;
  label: string;
  onPress: () => void;
  /** true = acción dentro de la app (no abre el navegador). */
  internal?: boolean;
  divider?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={internal ? 'button' : 'link'}
      accessibilityLabel={label}
      accessibilityHint={internal ? undefined : 'Se abre en el navegador'}
      style={({ pressed }) => [styles.row, divider && styles.rowDivider, pressed && styles.rowPressed]}>
      <Tile icon={icon} bg={internal ? Colors.clay : Colors.ink2} />
      <AppText variant="bodyLg" style={[styles.rowText, styles.rowTitle]}>
        {label}
      </AppText>
      <Icon name={internal ? 'chevronRight' : 'external'} size={16} color={Colors.muted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.paper },
  content: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xxl },
  section: { marginTop: Spacing.lg },
  sectionTitle: { marginBottom: Spacing.sm, marginLeft: Spacing.xs },
  sectionSub: { marginTop: -Spacing.xs, marginBottom: Spacing.sm, marginLeft: Spacing.xs },
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
    minHeight: ROW_MIN_HEIGHT,
  },
  rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: Colors.rule },
  rowPressed: { backgroundColor: Colors.paper2 },
  rowText: { flex: 1, gap: 2 },
  rowTitle: { lineHeight: 22 },
  tile: { width: TILE, height: TILE, borderRadius: Radius.xs, alignItems: 'center', justifyContent: 'center' },
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
  status: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.ms,
    gap: Spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.rule,
  },
  statusWarn: { backgroundColor: Colors.paper2 },
  statusButton: { alignSelf: 'flex-start' },
  footer: { marginTop: Spacing.xl, alignItems: 'center', gap: Spacing.xs },
});
