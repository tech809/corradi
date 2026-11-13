import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { FlatList, Platform, RefreshControl, StyleSheet, View, type HostInstance } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/button';
import { OpportunityCard } from '@/components/opportunity-card';
import { CardSkeletons, EmptyState, OfflineBanner } from '@/components/screen-states';
import { TabHeader } from '@/components/tab-header';
import { AppText } from '@/components/text';
import { showToast } from '@/components/toast';
import { Colors, Motion, Spacing } from '@/constants/theme';
import { focusOn, useReduceMotion } from '@/lib/a11y';
import { plural } from '@/lib/format';
import { tapSuccess } from '@/lib/haptics';
import {
  UNAVAILABLE_MESSAGE,
  enableDigest,
  getPermissionState,
  pushSupported,
  usePushPrefs,
  type PermissionState,
  type PushResult,
} from '@/lib/push';
import type { Opportunity } from '@/lib/types';
import { orderFirst } from '@/state/logic';
import { useInterestingNewItems, useOpportunityData, useSeenState } from '@/state/opportunities';

/** Tarjetas que entran con animación al cargar (el resto aparece sin más). */
const ANIMATED_ITEMS = 6;
/** A partir de cuántas tarjetas se repite "Ya los he visto" al final de la lista. */
const FOOTER_BUTTON_MIN = 4;

/** Respuesta a "Activar aviso diario" (mismos textos que Ajustes). */
const ENABLE_MESSAGE: Record<PushResult, string> = {
  enabled: 'Aviso diario activado. Te contaremos cuándo llegan proyectos nuevos.',
  pending: 'Guardado: activaremos los avisos en cuanto haya conexión.',
  denied: 'Sin permiso de notificaciones no podemos avisarte.',
  unavailable: UNAVAILABLE_MESSAGE,
  disabled: 'No hemos podido activar el aviso. Inténtalo desde Ajustes.',
};

export default function NuevosScreen() {
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const titleRef = useRef<HostInstance>(null);
  const { items, loading, refreshing, checking, error, refresh } = useOpportunityData();
  const { markAllSeen, showAsNew, isFirstVisit } = useSeenState();
  const liveNew = useInterestingNewItems();
  const params = useLocalSearchParams<{ ids?: string | string[] }>();

  const liveIds = useMemo(() => new Set(liveNew.map((o) => o.identifier)), [liveNew]);
  const liveIdsRef = useRef(liveIds);
  useEffect(() => {
    liveIdsRef.current = liveIds;
  }, [liveIds]);

  // Foto de los nuevos al entrar en la pestaña: lo que se abre y se ve sigue en la lista
  // (atenuado y con "Visto") hasta que se cambia de pestaña.
  const [snapshot, setSnapshot] = useState<ReadonlySet<string>>(() => new Set());
  const returningFromDetailRef = useRef(false);

  // Ids del último aviso diario con el que se abrió la pestaña: van primero y se cuentan aparte.
  const [announced, setAnnounced] = useState<ReadonlySet<string>>(() => new Set());
  const announcedIdsRef = useRef<ReadonlySet<string>>(announced);
  useEffect(() => {
    announcedIdsRef.current = announced;
  }, [announced]);

  useFocusEffect(
    useCallback(() => {
      if (returningFromDetailRef.current) {
        returningFromDetailRef.current = false;
      } else {
        setSnapshot(new Set([...liveIdsRef.current, ...announcedIdsRef.current]));
      }
      return () => {
        // Al dejar la pestaña (no para abrir una ficha) se olvida el aviso.
        if (!returningFromDetailRef.current) setAnnounced(new Set());
      };
    }, []),
  );

  // Abierta desde el aviso diario: `ids` = proyectos de ese aviso. Se enseñan como nuevos una vez.
  const idsParam = Array.isArray(params.ids) ? params.ids.join(',') : (params.ids ?? '');
  const pushIds = useMemo(
    () =>
      idsParam
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [idsParam],
  );
  // Ajuste durante el render (patrón recomendado por React): los ids del aviso entran en la foto.
  const [handledIdsParam, setHandledIdsParam] = useState('');
  if (idsParam !== handledIdsParam) {
    setHandledIdsParam(idsParam);
    if (pushIds.length) {
      setSnapshot((prev) => new Set([...prev, ...pushIds]));
      setAnnounced(new Set(pushIds));
    }
  }
  useEffect(() => {
    if (!pushIds.length) return;
    showAsNew(pushIds);
    router.setParams({ ids: undefined });
  }, [pushIds, showAsNew]);

  // Los del aviso, primero (en el orden de la lista); después el resto de nuevos.
  const display = useMemo(
    () =>
      orderFirst(
        items.filter((o) => snapshot.has(o.identifier) || liveIds.has(o.identifier)),
        announced,
      ),
    [items, snapshot, liveIds, announced],
  );
  const count = liveNew.length;
  const announcedCount = useMemo(() => display.filter((o) => announced.has(o.identifier)).length, [display, announced]);
  const othersUnseen = useMemo(() => liveNew.filter((o) => !announced.has(o.identifier)).length, [liveNew, announced]);
  const firstLoad = loading && items.length === 0;

  const onOpen = useCallback((id: string) => {
    returningFromDetailRef.current = true;
    setSnapshot((prev) => (prev.has(id) ? prev : new Set([...prev, id])));
    router.push({ pathname: '/proyecto/[id]', params: { id } });
  }, []);

  const onMarkAll = useCallback(() => {
    const prevSnapshot = snapshot;
    const prevAnnounced = announced;
    const undo = markAllSeen();
    setSnapshot(new Set());
    setAnnounced(new Set());
    tapSuccess();
    // La toast ya lo anuncia (una sola vez).
    showToast('Marcados como vistos', {
      icon: 'check',
      actionLabel: 'Deshacer',
      onAction: () => {
        undo();
        setSnapshot(prevSnapshot);
        setAnnounced(prevAnnounced);
      },
    });
    focusOn(titleRef);
  }, [snapshot, announced, markAllSeen]);

  const renderItem = useCallback(
    ({ item, index }: { item: Opportunity; index: number }) => (
      <EnterItem index={index} animate={!reduceMotion}>
        <OpportunityCard opportunity={item} onOpen={onOpen} seen={!liveIds.has(item.identifier)} />
      </EnterItem>
    ),
    [onOpen, liveIds, reduceMotion],
  );

  const markAllButton =
    count > 0 ? (
      <Button
        label="Ya los he visto"
        icon="check"
        variant="secondary"
        onPress={onMarkAll}
        accessibilityHint="Marca todos los proyectos nuevos como vistos"
      />
    ) : null;

  // "Nuevo" = aún no abierto (no "llegado desde tu última visita").
  let subtitle: string | null = null;
  if (announcedCount > 0) {
    // Abierta desde el aviso diario: "5 del aviso de hoy · 3 más sin ver".
    subtitle = [`${announcedCount} del aviso de hoy`, othersUnseen > 0 ? `${othersUnseen} más sin ver` : null]
      .filter(Boolean)
      .join(' · ');
  } else if (count > 0) {
    // Primera visita: lo de los últimos días o, si no había nada, los más recientes.
    subtitle = isFirstVisit ? 'Lo último que ha llegado' : `${plural(count, 'proyecto', 'proyectos')} que aún no has visto`;
  }

  // Aviso diario: activo si está en las preferencias y hay permiso del sistema.
  const prefs = usePushPrefs();
  const [permission, setPermission] = useState<PermissionState | null>(null);
  useFocusEffect(
    useCallback(() => {
      let alive = true;
      void getPermissionState().then((p) => alive && setPermission(p));
      return () => {
        alive = false;
      };
    }, []),
  );
  const digestKnown = prefs != null && permission != null;
  // Sin push en este binario (Expo Go, web) no se promete ningún aviso.
  const digestOn = !!prefs?.digest && permission === 'granted' && pushSupported();
  const [enabling, setEnabling] = useState(false);
  const enablingRef = useRef(false);
  const onEnableDigest = useCallback(async () => {
    if (enablingRef.current) return; // doble toque
    enablingRef.current = true;
    setEnabling(true);
    try {
      const result = await enableDigest();
      showToast(ENABLE_MESSAGE[result], { icon: result === 'enabled' ? 'check' : 'info' });
      setPermission(await getPermissionState());
    } catch {
      showToast(ENABLE_MESSAGE.disabled, { icon: 'info' });
    } finally {
      enablingRef.current = false;
      setEnabling(false);
    }
  }, []);

  const header = (
    <View style={styles.header}>
      <TabHeader ref={titleRef} eyebrow="Erasmus+ en claro" title="Nuevos" subtitle={subtitle} />
      {error && items.length > 0 ? <OfflineBanner onRetry={refresh} /> : null}
      {display.length > 0 ? markAllButton : null}
    </View>
  );

  let empty: ReactElement;
  if (checking || firstLoad) {
    empty = (
      <View style={styles.checking}>
        {/* Solo visual: el lector ya oye "Buscando novedades" en las tarjetas fantasma. */}
        <AppText variant="meta" color={Colors.muted} accessibilityElementsHidden importantForAccessibility="no">
          Buscando novedades…
        </AppText>
        <CardSkeletons label="Buscando novedades" />
      </View>
    );
  } else if (error && items.length === 0) {
    empty = (
      <EmptyState
        title="Sin conexión"
        text="No hemos podido cargar los proyectos. Revisa tu conexión y vuelve a intentarlo."
        action={{ label: 'Reintentar', onPress: refresh, loading: refreshing }}
      />
    );
  } else {
    empty = (
      <EmptyState
        title="¡Todo visto!"
        text={
          !digestKnown
            ? null
            : digestOn
              ? 'Te avisaremos cuando lleguen proyectos nuevos.'
              : 'Activa el aviso diario y te contamos cuándo llegan proyectos nuevos.'
        }>
        {digestKnown && !digestOn ? (
          <Button label="Activar aviso diario" icon="bell" loading={enabling} onPress={() => void onEnableDigest()} />
        ) : null}
        {items.length > 0 ? (
          <AppText variant="meta" color={Colors.muted} align="center">
            Ahora mismo hay {plural(items.length, 'proyecto abierto', 'proyectos abiertos')}.
          </AppText>
        ) : null}
        <Button
          label="Explorar todos"
          icon="explore"
          variant={digestKnown && !digestOn ? 'secondary' : 'primary'}
          onPress={() => router.navigate('/explorar')}
        />
      </EmptyState>
    );
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]}>
      <FlatList
        data={display}
        keyExtractor={keyOf}
        renderItem={renderItem}
        ListHeaderComponent={header}
        ListEmptyComponent={empty}
        ListFooterComponent={
          display.length > FOOTER_BUTTON_MIN && markAllButton ? <View style={styles.footer}>{markAllButton}</View> : undefined
        }
        ItemSeparatorComponent={Separator}
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
        refreshControl={
          <RefreshControl
            refreshing={refreshing && !firstLoad}
            onRefresh={refresh}
            tintColor={Colors.clay}
            colors={[Colors.clay]}
            progressBackgroundColor={Colors.surface}
          />
        }
        initialNumToRender={6}
        maxToRenderPerBatch={6}
        windowSize={7}
        removeClippedSubviews={Platform.OS === 'android'}
      />
    </View>
  );
}

function keyOf(o: Opportunity): string {
  return o.identifier;
}

/** Entrada suave (FadeInDown) solo para las primeras tarjetas, y nunca con "reducir movimiento". */
function EnterItem({ index, animate, children }: { index: number; animate: boolean; children: ReactNode }) {
  if (!animate || index >= ANIMATED_ITEMS) return <View>{children}</View>;
  return (
    <Animated.View entering={FadeInDown.duration(Motion.enter.duration).delay(index * Motion.enter.stagger)}>
      {children}
    </Animated.View>
  );
}

function Separator() {
  return <View style={styles.separator} />;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: Colors.paper },
  content: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xl, flexGrow: 1 },
  header: { gap: Spacing.md, paddingBottom: Spacing.md },
  footer: { paddingTop: Spacing.lg },
  checking: { gap: Spacing.ms },
  separator: { height: Spacing.md },
});
