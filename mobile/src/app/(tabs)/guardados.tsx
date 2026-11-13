import { router } from 'expo-router';
import { useCallback, useMemo, useRef, type ReactElement, type ReactNode } from 'react';
import { FlatList, Platform, RefreshControl, StyleSheet, View, type HostInstance } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ClosedSavedRow } from '@/components/closed-saved-row';
import { OpportunityCard } from '@/components/opportunity-card';
import { CardSkeletons, EmptyState, OfflineBanner } from '@/components/screen-states';
import { TabHeader } from '@/components/tab-header';
import { showToast } from '@/components/toast';
import { Colors, Motion, Spacing } from '@/constants/theme';
import { focusOn, useReduceMotion } from '@/lib/a11y';
import { isClosed, plural } from '@/lib/format';
import type { Opportunity } from '@/lib/types';
import { useOpportunityData, useSavedState } from '@/state/opportunities';

type Row = { kind: 'open'; o: Opportunity; index: number } | { kind: 'closed'; id: string; record?: Opportunity };

const ANIMATED_ITEMS = 6;

function openProject(id: string) {
  router.push({ pathname: '/proyecto/[id]', params: { id } });
}

function keyOf(r: Row): string {
  return r.kind === 'open' ? r.o.identifier : r.id;
}

/** Plazo más cercano primero; sin plazo, al final. */
function byDeadline(a: Opportunity, b: Opportunity): number {
  return (a.application_deadline ?? '9999').localeCompare(b.application_deadline ?? '9999');
}

export default function GuardadosScreen() {
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const { items, getById, loading, refreshing, error, lastUpdated, refresh } = useOpportunityData();
  const { savedIds, savedRecords, reminderIds, setSaved } = useSavedState();
  const titleRef = useRef<HostInstance>(null);
  const listKnown = items.length > 0 || lastUpdated != null;
  const count = savedIds.size;

  // Abiertos por plazo (lo que cierra antes, arriba); los cerrados, al final (lo último guardado primero).
  const { rows, unknown } = useMemo(() => {
    const open: Opportunity[] = [];
    const closed: Row[] = [];
    let unknownCount = 0;
    for (const id of [...savedIds].reverse()) {
      const fresh = getById(id);
      const record = fresh ?? savedRecords[id];
      if (fresh && !isClosed(fresh)) open.push(fresh);
      else if (!listKnown && !record) unknownCount++; // sin lista ni ficha: aún no se sabe
      else if (!listKnown && record && !isClosed(record)) open.push(record); // sin lista: se fía de la ficha guardada
      else closed.push({ kind: 'closed', id, record });
    }
    open.sort(byDeadline);
    return {
      rows: [...open.map((o, index): Row => ({ kind: 'open', o, index })), ...closed],
      unknown: unknownCount,
    };
  }, [savedIds, savedRecords, getById, listKnown]);

  // Doble toque: mientras se quita un proyecto, otro toque en su papelera no hace nada.
  // "Deshacer" espera a que termine el quitado y lo vuelve a guardar (`setSaved(…, true)`, nunca
  // un "alternar" a ciegas). Tras quitar, el foco del lector va al título de la pantalla (la fila
  // desaparece y el foco se perdería).
  const pendingRef = useRef<Map<string, Promise<unknown>>>(new Map());

  const onRemove = useCallback(
    (id: string) => {
      if (pendingRef.current.has(id) || !savedIds.has(id)) return;
      const record = getById(id) ?? savedRecords[id];
      const removal = setSaved(id, false).finally(() => pendingRef.current.delete(id));
      pendingRef.current.set(id, removal);
      focusOn(titleRef);
      let undone = false;
      showToast('Quitado de guardados', {
        icon: 'trash',
        actionLabel: 'Deshacer',
        onAction: () => {
          if (undone) return;
          undone = true;
          void removal.catch(() => {}).then(() => setSaved(id, true, record));
        },
      });
    },
    [setSaved, getById, savedRecords, savedIds],
  );

  const renderItem = useCallback(
    ({ item }: { item: Row }) =>
      item.kind === 'open' ? (
        <EnterItem index={item.index} animate={!reduceMotion}>
          <OpportunityCard opportunity={item.o} onOpen={openProject} reminderOn={!!reminderIds?.has(item.o.identifier)} />
        </EnterItem>
      ) : (
        <ClosedSavedRow identifier={item.id} record={item.record} onOpen={openProject} onRemove={onRemove} />
      ),
    [reminderIds, onRemove, reduceMotion],
  );

  const firstLoad = loading && !listKnown;

  let empty: ReactElement;
  if (count > 0 && firstLoad) {
    empty = <CardSkeletons count={Math.min(count, 3)} />;
  } else if (count > 0 && error && !listKnown) {
    empty = (
      <EmptyState
        title="Sin conexión"
        text="Tus guardados siguen aquí: los verás en cuanto vuelva la conexión."
        action={{ label: 'Reintentar', onPress: refresh, loading: refreshing }}
      />
    );
  } else {
    empty = (
      <EmptyState
        title="Aún no has guardado nada"
        text="Guarda un proyecto y te avisaremos 3 días antes de que cierre."
        action={{ label: 'Explorar proyectos', icon: 'explore', onPress: () => router.navigate('/explorar') }}
      />
    );
  }

  // Guardados antiguos sin ficha mientras llega la lista: se esperan con tarjetas fantasma.
  const footer = unknown > 0 && rows.length > 0 && loading ? <CardSkeletons count={Math.min(unknown, 2)} /> : null;

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]}>
      <FlatList
        data={unknown > 0 && rows.length === 0 ? [] : rows}
        keyExtractor={keyOf}
        renderItem={renderItem}
        ItemSeparatorComponent={Separator}
        ListHeaderComponent={
          <View style={styles.header}>
            <TabHeader
              ref={titleRef}
              title="Guardados"
              subtitle={
                count > 0
                  ? plural(count, 'proyecto guardado', 'proyectos guardados')
                  : 'Lo que guardes se queda aquí, también sin conexión.'
              }
            />
            {error && count > 0 ? <OfflineBanner onRetry={refresh} /> : null}
          </View>
        }
        ListEmptyComponent={empty}
        ListFooterComponent={footer ? <View style={styles.footer}>{footer}</View> : undefined}
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
  footer: { paddingTop: Spacing.md },
  separator: { height: Spacing.md },
});
