import Constants, { ExecutionEnvironment } from 'expo-constants';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, type ComponentType } from 'react';
import { ActivityIndicator, Linking, Pressable, ScrollView, SectionList, StyleSheet, TextInput, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/button';
import { Chip } from '@/components/chip';
import { Cover } from '@/components/cover';
import { Icon } from '@/components/icon';
import { IconButton } from '@/components/icon-button';
import type { LocatedOpportunity, OpportunityMapHandle, OpportunityMapProps } from '@/components/opportunity-map';
import { OpportunityCard } from '@/components/opportunity-card';
import { PressableScale } from '@/components/pressable-scale';
import { CardSkeletons, EmptyState } from '@/components/screen-states';
import { SegmentedControl } from '@/components/segmented-control';
import { AppText } from '@/components/text';
import { showToast } from '@/components/toast';
import { Colors, MIN_TOUCH, Motion, Radius, Shadows, Spacing, Typography } from '@/constants/theme';
import { announce, useReduceMotion, useScreenReader } from '@/lib/a11y';
import { WEB_URLS } from '@/lib/config';
import { useTabBarClearance } from '@/lib/layout';
import {
  cleanTitle,
  countryName,
  deadlineInfo,
  flagEmoji,
  parseDay,
  placeLabel,
  plural,
  typeLabel,
  typeShortLabel,
} from '@/lib/format';
import { OPPORTUNITY_TYPES, type Opportunity, type OpportunityType } from '@/lib/types';
import { useOpportunityData } from '@/state/opportunities';

/**
 * Pestaña Mapa: mapa (MapLibre) o lista de los mismos proyectos, con filtro por tipo.
 *
 * - Otras pantallas abren un proyecto aquí con `router.navigate({ pathname: '/mapa', params: { focus: id } })`:
 *   se selecciona, la cámara vuela hasta él y el parámetro se limpia.
 * - Con lector de pantalla la vista por defecto es Lista (el mapa no se puede recorrer). La lista
 *   va agrupada por país, con un encabezado por país.
 * - Lo que flota sobre el mapa (tarjeta del proyecto, créditos de OpenStreetMap) queda encima de
 *   la barra de pestañas (`useTabBarClearance`); el margen superior de la cámara es la altura
 *   medida de los controles.
 * - Si el mapa no carga (sin red), una píldora lo dice y ofrece la lista; un vuelo pendiente
 *   (`focus`) se hace cuando por fin cargue.
 * - MapLibre es código nativo que Expo Go no trae: allí el mapa muestra un aviso y la lista
 *   funciona igual. El require va condicionado para que Expo Go ni siquiera evalúe el módulo.
 * - Las pestañas nativas montan todas las pantallas al arrancar: el mapa (motor + descarga del
 *   estilo) solo se monta la primera vez que se entra en esta pestaña (`visited`).
 * - "Ver toda Europa" devuelve la cámara a la vista inicial sin pellizcar (WCAG 2.5.7).
 */
const IS_EXPO_GO = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
const OpportunityMap: ComponentType<OpportunityMapProps> | null = IS_EXPO_GO
  ? null
  : // eslint-disable-next-line @typescript-eslint/no-require-imports
    require('@/components/opportunity-map').OpportunityMap;

type ViewMode = 'map' | 'list';

/** Etiquetas de los chips en plural, como en Explorar. */
const TYPE_CHIP_LABELS: Record<OpportunityType, string> = {
  YOUTH_EXCHANGE: 'Intercambios',
  TRAINING_COURSE: 'Cursos',
  VOLUNTEERING: 'Voluntariado',
};

const APPROX_LEGEND = 'Anillo: ubicación aproximada';
/** Muestra del anillo de la leyenda (como el pin de ubicación aproximada). */
const LEGEND_RING = { size: 12, border: 2 } as const;

const VIEW_OPTIONS = [
  { value: 'map', label: 'Mapa', icon: 'map' },
  { value: 'list', label: 'Lista', icon: 'list' },
] as const;

/** Zoom al llegar con `focus`: ciudad si la ubicación es exacta, país si es aproximada. */
const FOCUS_ZOOM = { exact: 9, approx: 5.5 } as const;

function isLocated(o: Opportunity): o is LocatedOpportunity {
  return typeof o.latitude === 'number' && typeof o.longitude === 'number';
}

/** Por país (en español) y, dentro de cada país, por plazo (sin plazo al final). */
function byCountryThenDeadline(a: Opportunity, b: Opportunity): number {
  const ca = countryName(a.country_code);
  const cb = countryName(b.country_code);
  if (ca !== cb) {
    if (!ca) return 1;
    if (!cb) return -1;
    return ca.localeCompare(cb, 'es');
  }
  const da = parseDay(a.application_deadline)?.getTime() ?? Number.POSITIVE_INFINITY;
  const db = parseDay(b.application_deadline)?.getTime() ?? Number.POSITIVE_INFINITY;
  return da - db;
}

interface CountrySection {
  key: string;
  /** Nombre del país sin bandera (lo que lee el lector de pantalla). */
  name: string;
  title: string;
  data: Opportunity[];
}

/** Sin tildes y en minúsculas, para buscar "espana" o "Rumanía" igual. */
function fold(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

/** Agrupa una lista YA ordenada por país en secciones (sin país, al final con su propio título). */
function groupByCountry(sorted: Opportunity[]): CountrySection[] {
  const sections: CountrySection[] = [];
  for (const o of sorted) {
    const name = countryName(o.country_code);
    const key = name ?? '—';
    let last = sections[sections.length - 1];
    if (!last || last.key !== key) {
      const flag = flagEmoji(o.country_code);
      last = { key, name: name ?? 'Sin país', title: name ? `${flag ? `${flag} ` : ''}${name}` : 'Sin país', data: [] };
      sections.push(last);
    }
    last.data.push(o);
  }
  return sections;
}

function selectionLabel(o: Opportunity): string {
  const place = placeLabel(o);
  const placeText = place ? `${place}${o.approx_location ? ', ubicación aproximada' : ''}` : 'Sin ubicar';
  return `${typeLabel(o.type)}: ${cleanTitle(o.title) || o.title}. ${placeText}. ${deadlineInfo(o).text}`;
}

const openProject = (id: string) => router.push({ pathname: '/proyecto/[id]', params: { id } });

export default function MapaScreen() {
  const { items, loading, getById } = useOpportunityData();
  const { focus } = useLocalSearchParams<{ focus?: string }>();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const screenReader = useScreenReader();
  const clearance = useTabBarClearance(Spacing.sm);
  const mapRef = useRef<OpportunityMapHandle>(null);
  const flownTick = useRef(0);
  // Alto real de los controles de arriba (cambia con el tamaño de letra): margen de la cámara.
  const [controlsHeight, setControlsHeight] = useState(0);
  const [mapFailed, setMapFailed] = useState(false);
  // Las pestañas nativas precargan esta pantalla: el mapa espera a la primera visita.
  const [visited, setVisited] = useState(false);
  useFocusEffect(
    useCallback(() => {
      setVisited(true);
    }, []),
  );

  // null = aún no ha elegido: Lista con lector de pantalla, Mapa sin él.
  const [chosenView, setChosenView] = useState<ViewMode | null>(null);
  const view: ViewMode = chosenView ?? (screenReader ? 'list' : 'map');
  const [filter, setFilter] = useState<OpportunityType | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [flyTarget, setFlyTarget] = useState<{ o: LocatedOpportunity; tick: number } | null>(null);
  const [handledFocus, setHandledFocus] = useState<string | null>(null);
  const [countryQuery, setCountryQuery] = useState('');
  const deferredCountryQuery = useDeferredValue(countryQuery);

  const visible = useMemo(() => (filter ? items.filter((o) => o.type === filter) : items), [items, filter]);
  const located = useMemo(() => visible.filter(isLocated), [visible]);
  const sorted = useMemo(() => [...visible].sort(byCountryThenDeadline), [visible]);
  const sections = useMemo(() => groupByCountry(sorted), [sorted]);
  const shownSections = useMemo(() => {
    const q = fold(deferredCountryQuery);
    return q ? sections.filter((s) => fold(s.name).includes(q)) : sections;
  }, [sections, deferredCountryQuery]);
  const hasApprox = useMemo(() => located.some((o) => o.approx_location), [located]);
  const counts = useMemo(() => {
    const c: Record<OpportunityType, number> = { YOUTH_EXCHANGE: 0, TRAINING_COURSE: 0, VOLUNTEERING: 0 };
    for (const o of items) if (o.type) c[o.type]++;
    return c;
  }, [items]);
  const unlocated = visible.length - located.length;
  const selected = selectedId ? getById(selectedId) : undefined;

  // Llegada con ?focus=ID (se ajusta el estado durante el render, patrón recomendado por React):
  // seleccionar, quitar un filtro que lo oculte y preparar el vuelo de la cámara.
  const focusItem = focus ? getById(focus) : undefined;
  if (!focus && handledFocus) setHandledFocus(null);
  if (focus && focus !== handledFocus && (focusItem || !loading)) {
    setHandledFocus(focus);
    if (focusItem) {
      if (filter && focusItem.type !== filter) setFilter(null);
      setSelectedId(focusItem.identifier);
      if (isLocated(focusItem)) {
        setFlyTarget((prev) => ({ o: focusItem, tick: (prev?.tick ?? 0) + 1 }));
        if (OpportunityMap) setChosenView('map');
      }
    }
  }

  // Efectos externos del `focus` ya atendido: limpiar el parámetro y avisar si no existe.
  useEffect(() => {
    if (!focus || focus !== handledFocus) return;
    if (!getById(focus)) showToast('Ese proyecto ya no está en el mapa', { icon: 'info' });
    router.setParams({ focus: undefined });
  }, [focus, handledFocus, getById]);

  // El mapa está montado: vista Mapa, pestaña ya visitada y controles medidos.
  const mapMounted = !!OpportunityMap && view === 'map' && visited && controlsHeight > 0;

  // Vuela cuando el mapa ya está montado (puede venir de la vista Lista o montarse ahora por
  // primera vez). Una vez por destino; si el mapa aún no ha cargado, el vuelo queda pendiente en él.
  useEffect(() => {
    if (!flyTarget || flyTarget.tick === flownTick.current || !mapMounted || !mapRef.current) return;
    flownTick.current = flyTarget.tick;
    const { o } = flyTarget;
    mapRef.current.flyTo([o.longitude, o.latitude], o.approx_location ? FOCUS_ZOOM.approx : FOCUS_ZOOM.exact);
  }, [flyTarget, mapMounted]);

  const chooseView = (v: ViewMode) => {
    setChosenView(v);
    // Volver al mapa lo monta de nuevo: es el reintento natural tras un fallo de carga.
    if (v === 'map') setMapFailed(false);
  };

  const onMapError = () => {
    setMapFailed(true);
    // El vuelo pendiente se queda en el mapa que falló; si se vuelve a montar, que se repita.
    flownTick.current = 0;
    // Un solo aviso (announce sirve en iOS y Android; la píldora no lleva liveRegion).
    announce('No se pudo cargar el mapa');
  };

  const chooseFilter = (t: OpportunityType | null) => {
    setFilter(t);
    if (selected && t && selected.type !== t) setSelectedId(null);
    const n = t ? items.filter((o) => o.type === t).length : items.length;
    announce(`${t ? TYPE_CHIP_LABELS[t] : 'Todos'}: ${plural(n, 'proyecto', 'proyectos')}`);
  };

  const onSelect = (id: string | null) => {
    setSelectedId(id);
    const o = id ? getById(id) : undefined;
    if (o) announce(`Seleccionado. ${selectionLabel(o)}`);
  };

  const openWebMap = () =>
    WebBrowser.openBrowserAsync(`${WEB_URLS.home}mapa`, { toolbarColor: Colors.paper, controlsColor: Colors.clay }).catch(
      () => Linking.openURL(`${WEB_URLS.home}mapa`),
    );

  const showMap = view === 'map';
  const firstLoad = loading && items.length === 0;

  const controls = (
    <View
      style={[styles.controls, showMap ? styles.controlsOverlay : null, { paddingTop: insets.top + Spacing.sm }]}
      pointerEvents="box-none"
      onLayout={(e) => {
        const h = Math.round(e.nativeEvent.layout.height);
        if (h !== controlsHeight) setControlsHeight(h);
      }}>
      <SegmentedControl accessibilityLabel="Vista" options={VIEW_OPTIONS} value={view} onChange={chooseView} style={styles.segmented} />
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
        keyboardShouldPersistTaps="handled"
        accessibilityLabel="Filtrar por tipo">
        <Chip label="Todos" count={items.length} selected={filter === null} onPress={() => chooseFilter(null)} />
        {OPPORTUNITY_TYPES.map((t) => (
          <Chip key={t} label={TYPE_CHIP_LABELS[t]} type={t} count={counts[t]} selected={filter === t} onPress={() => chooseFilter(t)} />
        ))}
      </ScrollView>
      {!showMap && !firstLoad && sorted.length > 0 ? (
        <View style={styles.search}>
          <Icon name="search" size={18} color={Colors.muted} />
          <TextInput
            value={countryQuery}
            onChangeText={setCountryQuery}
            placeholder="Buscar país"
            placeholderTextColor={Colors.muted}
            style={styles.input}
            returnKeyType="search"
            autoCorrect={false}
            autoCapitalize="none"
            clearButtonMode="never"
            accessibilityLabel="Buscar país"
          />
          {countryQuery ? (
            <IconButton icon="clear" color={Colors.muted} size={18} onPress={() => setCountryQuery('')} accessibilityLabel="Borrar búsqueda" />
          ) : null}
        </View>
      ) : null}
      {showMap && OpportunityMap && mapFailed ? (
        <View style={styles.notes}>
          <View style={[styles.pill, styles.failPill]}>
            <AppText variant="meta" color={Colors.ink2} style={styles.failText}>
              No se pudo cargar el mapa
            </AppText>
            <Button label="Ver como lista" icon="list" variant="secondary" onPress={() => chooseView('list')} />
          </View>
        </View>
      ) : showMap && OpportunityMap ? (
        <View style={styles.notes} pointerEvents="box-none">
          {mapMounted ? (
            <Pressable
              onPress={() => mapRef.current?.resetView()}
              accessibilityRole="button"
              accessibilityLabel="Ver toda Europa"
              accessibilityHint="Vuelve a la vista inicial del mapa"
              hitSlop={Spacing.xs}
              style={({ pressed }) => [styles.pill, styles.europeButton, pressed && styles.europePressed]}>
              <Icon name="globe" size={16} color={Colors.ink2} />
              <AppText variant="label" color={Colors.ink2}>
                Ver toda Europa
              </AppText>
            </Pressable>
          ) : null}
          {hasApprox ? (
            <View style={styles.pill} pointerEvents="none" accessible accessibilityLabel={APPROX_LEGEND}>
              <View style={styles.legendRing} />
              <AppText variant="meta" color={Colors.ink2}>
                {APPROX_LEGEND}
              </AppText>
            </View>
          ) : null}
          {firstLoad ? (
            <View style={styles.pill} pointerEvents="none" accessibilityLiveRegion="polite">
              <ActivityIndicator size="small" color={Colors.muted} />
              <AppText variant="meta" color={Colors.ink2}>
                Cargando proyectos…
              </AppText>
            </View>
          ) : unlocated > 0 ? (
            <View style={styles.pill} pointerEvents="none" accessibilityLiveRegion="polite">
              <AppText variant="meta" color={Colors.ink2}>
                {unlocated} sin ubicar · en la lista
              </AppText>
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );

  if (!showMap) {
    return (
      <View style={styles.root}>
        {controls}
        {firstLoad ? (
          <View style={styles.listPad}>
            <CardSkeletons count={4} compact />
          </View>
        ) : (
          <SectionList
            sections={shownSections}
            keyExtractor={(o) => o.identifier}
            renderItem={({ item }) => <OpportunityCard opportunity={item} onOpen={openProject} compact />}
            renderSectionHeader={({ section }) => (
              <View style={styles.sectionHeader}>
                <AppText variant="label" color={Colors.ink2} accessibilityRole="header" accessibilityLabel={section.name}>
                  {section.title}
                </AppText>
                <AppText variant="meta" color={Colors.muted} accessibilityLabel={plural(section.data.length, 'proyecto', 'proyectos')}>
                  {section.data.length}
                </AppText>
              </View>
            )}
            stickySectionHeadersEnabled
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="on-drag"
            contentContainerStyle={styles.listContent}
            contentInsetAdjustmentBehavior="automatic"
            ItemSeparatorComponent={Separator}
            ListHeaderComponent={
              sorted.length > 0 ? (
                <View style={styles.listHeader}>
                  <AppText variant="title3" accessibilityRole="header">
                    Proyectos por país
                  </AppText>
                  <AppText variant="meta" color={Colors.muted}>
                    {plural(sorted.length, 'proyecto', 'proyectos')}, ordenados por plazo dentro de cada país
                  </AppText>
                </View>
              ) : undefined
            }
            ListEmptyComponent={
              deferredCountryQuery.trim() && sorted.length > 0 ? (
                <EmptyState
                  title="Ningún país coincide"
                  text="Prueba con otro nombre o borra la búsqueda."
                  action={{ label: 'Borrar búsqueda', onPress: () => setCountryQuery(''), variant: 'secondary' }}
                />
              ) : filter ? (
                <EmptyState
                  title="Ahora no hay proyectos de este tipo"
                  text="Prueba con otro tipo o mira todos."
                  action={{ label: 'Ver todos', onPress: () => chooseFilter(null), variant: 'secondary' }}
                />
              ) : (
                <EmptyState title="Aún no hay proyectos" text="Cuando haya conexión te enseñamos los proyectos abiertos." />
              )
            }
          />
        )}
      </View>
    );
  }

  return (
    <View style={styles.root}>
      {OpportunityMap ? (
        // Se monta en la primera visita a la pestaña y cuando ya se conoce el alto de los
        // controles (la vista inicial lo usa). Hasta entonces, el fondo papel de `root`.
        mapMounted ? (
          <OpportunityMap
            ref={mapRef}
            points={located}
            selectedId={selectedId}
            onSelect={onSelect}
            reduceMotion={reduceMotion}
            topInset={controlsHeight}
            bottomInset={clearance}
            onLoadError={onMapError}
            onLoad={() => setMapFailed(false)}
            accessibilityLabel={`Mapa con ${plural(located.length, 'proyecto', 'proyectos')}`}
            accessibilityHint="Para recorrerlos uno a uno, cambia arriba a la vista Lista"
          />
        ) : null
      ) : (
        <View style={[styles.goNotice, { paddingTop: controlsHeight || insets.top + 140 }]}>
          <EmptyState
            title="El mapa se ve en la app de las tiendas"
            text="Esta versión de prueba no incluye el motor del mapa. Puedes ver los mismos proyectos en lista o abrir el mapa web.">
            <Button label="Ver como lista" icon="list" onPress={() => chooseView('list')} />
            <Button
              label="Abrir el mapa web"
              icon="external"
              variant="secondary"
              onPress={openWebMap}
              accessibilityHint="Se abre en el navegador"
            />
          </EmptyState>
        </View>
      )}

      {controls}

      {selected && OpportunityMap ? (
        <SelectedCard
          key={selected.identifier}
          o={selected}
          bottom={clearance}
          reduceMotion={reduceMotion}
          onClose={() => {
            setSelectedId(null);
            announce('Tarjeta cerrada');
          }}
        />
      ) : null}
    </View>
  );
}

function Separator() {
  return <View style={styles.separator} />;
}

function SelectedCard({
  o,
  bottom,
  reduceMotion,
  onClose,
}: {
  o: Opportunity;
  bottom: number;
  reduceMotion: boolean;
  onClose: () => void;
}) {
  const place = placeLabel(o);
  const flag = flagEmoji(o.country_code);
  const deadline = deadlineInfo(o);
  const deadlineColor = deadline.tone === 'closed' ? Colors.muted : deadline.tone === 'urgent' ? Colors.clayText : Colors.ink2;

  return (
    <Animated.View
      entering={reduceMotion ? undefined : FadeInDown.duration(Motion.enter.duration)}
      style={[styles.card, { bottom }]}>
      <PressableScale
        onPress={() => openProject(o.identifier)}
        accessibilityRole="button"
        accessibilityLabel={selectionLabel(o)}
        accessibilityHint="Abre la ficha"
        style={styles.cardMain}
        pressedStyle={styles.cardPressed}>
        <Cover o={o} height={64} variant="thumb" style={styles.cardThumb} />
        <View style={styles.cardBody}>
          <AppText variant="eyebrow" color={Colors.muted}>
            {typeShortLabel(o.type)}
          </AppText>
          <AppText variant="cardTitle" numberOfLines={2} style={styles.cardTitle}>
            {cleanTitle(o.title) || o.title}
          </AppText>
          {place ? (
            <AppText variant="meta" color={Colors.ink2} numberOfLines={2}>
              {flag ? `${flag} ` : ''}
              {place}
              {o.approx_location ? ' · ubicación aproximada' : ''}
            </AppText>
          ) : null}
          <AppText variant="label" color={deadlineColor}>
            {deadline.text}
          </AppText>
        </View>
      </PressableScale>
      <IconButton icon="close" onPress={onClose} accessibilityLabel="Cerrar la tarjeta" color={Colors.ink2} size={18} style={styles.cardClose} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.paper },
  controls: { gap: Spacing.sm, paddingBottom: Spacing.sm },
  controlsOverlay: { position: 'absolute', top: 0, left: 0, right: 0 },
  segmented: { marginHorizontal: Spacing.md },
  chips: { paddingHorizontal: Spacing.md, gap: Spacing.sm },
  notes: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: Spacing.sm, paddingHorizontal: Spacing.md },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs2,
    paddingHorizontal: Spacing.ms,
    paddingVertical: Spacing.xs,
    borderRadius: Radius.pill,
    backgroundColor: Colors.surface,
    ...Shadows.sm,
  },
  europeButton: { minHeight: MIN_TOUCH },
  europePressed: { backgroundColor: Colors.paper2 },
  legendRing: {
    width: LEGEND_RING.size,
    height: LEGEND_RING.size,
    borderRadius: LEGEND_RING.size / 2,
    borderWidth: LEGEND_RING.border,
    borderColor: Colors.ink2,
    backgroundColor: Colors.white,
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
    minHeight: MIN_TOUCH,
  },
  input: { ...Typography.body, flex: 1, color: Colors.ink, paddingVertical: Spacing.sm, fontSize: 16 },
  goNotice: { flex: 1, justifyContent: 'center', paddingHorizontal: Spacing.md },
  listPad: { paddingHorizontal: Spacing.md, paddingTop: Spacing.sm },
  listContent: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xl },
  listHeader: { paddingTop: Spacing.sm, paddingBottom: Spacing.xs, gap: 2 },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
    // Fijo arriba al desplazar: fondo opaco para que no se transparenten las tarjetas.
    backgroundColor: Colors.paper,
  },
  failPill: { paddingVertical: Spacing.xs, paddingLeft: Spacing.md, gap: Spacing.sm, flexShrink: 1, flexWrap: 'wrap' },
  failText: { flexShrink: 1 },
  separator: { height: Spacing.ms },
  card: {
    position: 'absolute',
    left: Spacing.md,
    right: Spacing.md,
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: Colors.surface,
    borderRadius: Radius.lg,
    ...Shadows.md,
  },
  cardMain: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.ms,
    padding: Spacing.ms,
    borderTopLeftRadius: Radius.lg,
    borderBottomLeftRadius: Radius.lg,
  },
  cardPressed: { backgroundColor: Colors.paper },
  cardThumb: { borderRadius: Radius.sm },
  cardBody: { flex: 1, gap: Spacing.xs },
  cardTitle: { fontSize: 17, lineHeight: 22 },
  cardClose: { margin: Spacing.xs },
});
