import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { FlatList, Platform, RefreshControl, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Chip } from '@/components/chip';
import { Icon } from '@/components/icon';
import { IconButton } from '@/components/icon-button';
import { OpportunityCard } from '@/components/opportunity-card';
import { CardSkeletons, EmptyState, OfflineBanner } from '@/components/screen-states';
import { SegmentedControl, type SegmentedOption } from '@/components/segmented-control';
import { TabHeader } from '@/components/tab-header';
import { AppText } from '@/components/text';
import { Colors, MIN_TOUCH, Motion, Radius, Sizes, Spacing, Typography } from '@/constants/theme';
import { announce, useReduceMotion } from '@/lib/a11y';
import { CLOSING_SOON_DAYS, closingSoon, countryName, plural, typeLabel, typeShortLabel } from '@/lib/format';
import { OPPORTUNITY_TYPES, type Opportunity, type OpportunityType } from '@/lib/types';
import { useOpportunityData } from '@/state/opportunities';

type TypeFilter = 'ALL' | OpportunityType;

function isOpportunityType(v: string | undefined): v is OpportunityType {
  return !!v && (OPPORTUNITY_TYPES as readonly string[]).includes(v);
}
type Sort = 'newest' | 'deadline';

const TYPE_FILTERS: { value: TypeFilter; label: string }[] = [
  { value: 'ALL', label: 'Todos' },
  { value: 'YOUTH_EXCHANGE', label: 'Intercambios' },
  { value: 'TRAINING_COURSE', label: 'Cursos' },
  { value: 'VOLUNTEERING', label: 'Voluntariados' },
];

const SORT_OPTIONS: readonly SegmentedOption<Sort>[] = [
  { value: 'newest', label: 'Más nuevos', accessibilityLabel: 'Más nuevos primero' },
  { value: 'deadline', label: 'Por fecha límite', accessibilityLabel: 'Por fecha límite, la más cercana primero' },
];

const ANIMATED_ITEMS = 6;
const ANNOUNCE_DELAY_MS = 600;

/** Filas de la lista: controles (fijos arriba al hacer scroll), resultados, tarjetas o un estado. */
type Row =
  | { kind: 'controls' }
  | { kind: 'results' }
  | { kind: 'card'; o: Opportunity; index: number }
  | { kind: 'state' };

const CONTROLS_ROW: Row = { kind: 'controls' };
const RESULTS_ROW: Row = { kind: 'results' };
const STATE_ROW: Row = { kind: 'state' };
/** Índice de la fila de controles entre los hijos del ScrollView (0 es la cabecera). */
const STICKY_INDICES = [1];

/** Minúsculas y sin tildes, para que "polonia" encuentre "Polonia" y "educacion" encuentre "educación". */
function normalize(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function searchText(o: Opportunity): string {
  return normalize(
    [
      o.title,
      o.summary,
      o.location,
      o.organiser_name,
      o.topic,
      countryName(o.country_code),
      o.country_code,
      o.type ? typeLabel(o.type) : null,
      o.type ? typeShortLabel(o.type) : null,
    ]
      .filter(Boolean)
      .join(' '),
  );
}

function byDeadline(a: Opportunity, b: Opportunity): number {
  // Sin plazo, al final.
  return (a.application_deadline ?? '9999').localeCompare(b.application_deadline ?? '9999');
}

function openProject(id: string) {
  router.push({ pathname: '/proyecto/[id]', params: { id } });
}

function keyOf(r: Row): string {
  return r.kind === 'card' ? r.o.identifier : r.kind;
}

export default function ExplorarScreen() {
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const { items, loading, refreshing, error, refresh } = useOpportunityData();
  const [query, setQuery] = useState('');
  const [type, setType] = useState<TypeFilter>('ALL');

  // Llegada con ?q=texto y/o ?type=TIPO (desde otra pantalla o un enlace): se siembra una vez por
  // valor nuevo (ajuste durante el render, como `focus` en mapa.tsx) y luego se limpia el parámetro.
  const params = useLocalSearchParams<{ q?: string; type?: string }>();
  const qParam = typeof params.q === 'string' && params.q.trim() ? params.q : undefined;
  const typeParam = isOpportunityType(params.type) ? params.type : undefined;
  const [handledQ, setHandledQ] = useState<string | undefined>(undefined);
  const [handledType, setHandledType] = useState<string | undefined>(undefined);
  if (qParam !== handledQ) {
    setHandledQ(qParam);
    if (qParam) setQuery(qParam);
  }
  if (typeParam !== handledType) {
    setHandledType(typeParam);
    if (typeParam) setType(typeParam);
  }
  useEffect(() => {
    if (params.q !== undefined || params.type !== undefined) router.setParams({ q: undefined, type: undefined });
  }, [params.q, params.type]);
  const [soon, setSoon] = useState(false);
  const [sort, setSort] = useState<Sort>('newest');
  const deferredQuery = useDeferredValue(query);

  // Índice de búsqueda: se calcula una vez por lista, no en cada tecla.
  const index = useMemo(() => items.map((o) => ({ o, text: searchText(o) })), [items]);

  // Búsqueda + "Cierran pronto" (sin el tipo): base de los resultados y de los números de los chips.
  const matching = useMemo(() => {
    const terms = normalize(deferredQuery).split(/\s+/).filter(Boolean);
    return index
      .filter(({ o, text }) => {
        if (soon && !closingSoon(o)) return false;
        return terms.every((t) => text.includes(t));
      })
      .map(({ o }) => o);
  }, [index, deferredQuery, soon]);

  const typeCounts = useMemo(() => {
    const counts: Record<TypeFilter, number> = { ALL: matching.length, YOUTH_EXCHANGE: 0, TRAINING_COURSE: 0, VOLUNTEERING: 0 };
    for (const o of matching) if (o.type) counts[o.type]++;
    return counts;
  }, [matching]);

  const results = useMemo(() => {
    const filtered = type === 'ALL' ? [...matching] : matching.filter((o) => o.type === type);
    return sort === 'deadline' ? filtered.sort(byDeadline) : filtered; // `items` ya viene de más nuevo a más antiguo
  }, [matching, type, sort]);

  const firstLoad = loading && items.length === 0;
  const filtersActive = query.trim() !== '' || type !== 'ALL' || soon;
  const resetFilters = useCallback(() => {
    setQuery('');
    setType('ALL');
    setSoon(false);
  }, []);

  // Número de resultados para el lector: una sola vez (sin región viva), con pausa al teclear
  // y sin leerlo al abrir la pantalla.
  const countText = results.length === 0 ? 'Ningún proyecto con estos filtros' : plural(results.length, 'proyecto', 'proyectos');
  const announcedOnceRef = useRef(false);
  useEffect(() => {
    if (firstLoad) return;
    if (!announcedOnceRef.current) {
      announcedOnceRef.current = true;
      return;
    }
    const t = setTimeout(() => announce(countText), ANNOUNCE_DELAY_MS);
    return () => clearTimeout(t);
  }, [countText, deferredQuery, type, soon, firstLoad]);

  const rows = useMemo<Row[]>(() => {
    if (firstLoad || (error && items.length === 0) || results.length === 0) return [CONTROLS_ROW, RESULTS_ROW, STATE_ROW];
    return [CONTROLS_ROW, RESULTS_ROW, ...results.map((o, i) => ({ kind: 'card' as const, o, index: i }))];
  }, [firstLoad, error, items.length, results]);

  const renderItem = useCallback(
    ({ item }: { item: Row }) => {
      switch (item.kind) {
        case 'controls':
          return (
            <View style={styles.controls}>
              <View style={styles.search}>
                <Icon name="search" size={18} color={Colors.muted} />
                <TextInput
                  value={query}
                  onChangeText={setQuery}
                  placeholder="Busca por tema, país, ciudad…"
                  placeholderTextColor={Colors.muted}
                  style={styles.input}
                  returnKeyType="search"
                  autoCorrect={false}
                  autoCapitalize="none"
                  clearButtonMode="never"
                  accessibilityLabel="Buscar proyectos"
                  accessibilityHint="Busca por tema, país, ciudad o tipo de proyecto"
                />
                {query ? (
                  <IconButton icon="clear" color={Colors.muted} size={18} onPress={() => setQuery('')} accessibilityLabel="Borrar búsqueda" />
                ) : null}
              </View>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.chips}
                keyboardShouldPersistTaps="handled">
                {/* "Cierran pronto" justo después de "Todos": visible sin desplazar en móviles pequeños. */}
                <Chip
                  label={TYPE_FILTERS[0].label}
                  count={firstLoad ? undefined : typeCounts.ALL}
                  selected={type === 'ALL'}
                  onPress={() => setType('ALL')}
                />
                <Chip
                  label="Cierran pronto"
                  icon="hourglass"
                  variant="accent"
                  selected={soon}
                  onPress={() => {
                    // Al pedir los que cierran pronto, se ordena por fecha límite.
                    if (!soon) setSort('deadline');
                    setSoon(!soon);
                  }}
                  accessibilityHint={`Solo los que cierran en ${CLOSING_SOON_DAYS} días o menos`}
                />
                <View style={styles.chipDivider} />
                {TYPE_FILTERS.slice(1).map((f) => (
                  <Chip
                    key={f.value}
                    label={f.label}
                    type={f.value === 'ALL' ? undefined : f.value}
                    count={firstLoad ? undefined : typeCounts[f.value]}
                    selected={type === f.value}
                    onPress={() => setType(f.value)}
                  />
                ))}
              </ScrollView>
            </View>
          );
        case 'results':
          return (
            <View style={styles.resultsRow}>
              <AppText variant="label" color={Colors.ink2} style={styles.count}>
                {firstLoad ? 'Cargando…' : plural(results.length, 'proyecto', 'proyectos')}
              </AppText>
              <SegmentedControl
                role="radio"
                accessibilityLabel="Ordenar por"
                options={SORT_OPTIONS}
                value={sort}
                onChange={setSort}
                style={styles.sort}
              />
            </View>
          );
        case 'card':
          return (
            <View style={styles.inset}>
              <EnterItem index={item.index} animate={!reduceMotion}>
                <OpportunityCard opportunity={item.o} onOpen={openProject} />
              </EnterItem>
            </View>
          );
        case 'state':
          if (firstLoad) {
            return (
              <View style={styles.inset}>
                <CardSkeletons />
              </View>
            );
          }
          if (error && items.length === 0) {
            return (
              <EmptyState
                title="Sin conexión"
                text="No hemos podido cargar los proyectos. Revisa tu conexión y vuelve a intentarlo."
                action={{ label: 'Reintentar', onPress: refresh, loading: refreshing }}
              />
            );
          }
          return (
            <EmptyState
              title="Nada por aquí"
              text="No hay proyectos abiertos con estos filtros. Prueba con otra búsqueda."
              action={filtersActive ? { label: 'Quitar filtros', variant: 'secondary', onPress: resetFilters } : undefined}
            />
          );
      }
    },
    [query, type, soon, sort, typeCounts, results.length, firstLoad, error, items.length, refresh, refreshing, filtersActive, resetFilters, reduceMotion],
  );

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]}>
      <FlatList
        data={rows}
        keyExtractor={keyOf}
        renderItem={renderItem}
        ItemSeparatorComponent={Separator}
        ListHeaderComponent={
          <View style={styles.header}>
            <TabHeader
              title="Explorar"
              subtitle={
                items.length > 0
                  ? `${plural(items.length, 'proyecto abierto', 'proyectos abiertos')}: busca y filtra`
                  : 'Busca y filtra todos los proyectos abiertos'
              }
            />
            {error && items.length > 0 ? <OfflineBanner onRetry={refresh} /> : null}
          </View>
        }
        stickyHeaderIndices={STICKY_INDICES}
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
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

/** Separación entre tarjetas; sin hueco extra tras la fila fija de controles. */
function Separator({ leadingItem }: { leadingItem?: Row }) {
  return leadingItem?.kind === 'controls' ? null : <View style={styles.separator} />;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: Colors.paper },
  content: { paddingBottom: Spacing.xl, flexGrow: 1 },
  header: { paddingHorizontal: Spacing.md, gap: Spacing.sm },
  controls: {
    backgroundColor: Colors.paper, // opaca: queda fija encima de las tarjetas
    paddingTop: Spacing.sm,
    gap: Spacing.sm,
  },
  search: {
    marginHorizontal: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.controlBorder,
    borderRadius: Radius.pill,
    paddingLeft: Spacing.md,
    paddingRight: Spacing.xs,
    minHeight: MIN_TOUCH + 4,
  },
  input: { ...Typography.body, flex: 1, color: Colors.ink, paddingVertical: Spacing.sm, fontSize: 16 },
  chips: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.sm, gap: Spacing.sm, alignItems: 'center' },
  chipDivider: { width: 1, height: Sizes.chipDivider, backgroundColor: Colors.rule, marginHorizontal: Spacing.xxs },
  resultsRow: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.xs,
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  count: { flexGrow: 1 },
  sort: { flexGrow: 1, minWidth: 240 },
  separator: { height: Spacing.md },
  inset: { paddingHorizontal: Spacing.md },
});
