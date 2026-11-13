/**
 * Ficha de un proyecto. Responde primero a "¿es para mí, cuánto pago y cómo me apunto?":
 * portada → tipo y título → tarjeta "¿Es para ti?" → resumen → secciones → barra fija con
 * "Quiero apuntarme". Cabecera propia (transparente sobre la portada, papel al hacer scroll).
 */
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View, type HostInstance, type LayoutChangeEvent } from 'react-native';
import Animated, {
  useAnimatedReaction,
  useAnimatedRef,
  useAnimatedScrollHandler,
  useSharedValue,
  type SharedValue,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { scheduleOnRN } from 'react-native-worklets';

import { Button } from '@/components/button';
import { AnchorSection } from '@/components/detail/anchor-section';
import { ApplyBar } from '@/components/detail/apply-bar';
import { DetailHeader, HEADER_BAR_HEIGHT } from '@/components/detail/detail-header';
import { applyUrl, needsEscNotice } from '@/components/detail/apply';
import { DetailSkeleton } from '@/components/detail/detail-skeleton';
import { FitCard } from '@/components/detail/fit-card';
import { HowToApply } from '@/components/detail/how-to-apply';
import { reminderWhen } from '@/components/detail/reminder-text';
import { TopicTags } from '@/components/detail/topic-tags';
import { CollapsibleText, TextSection } from '@/components/detail-parts';
import { Cover } from '@/components/cover';
import { Icon } from '@/components/icon';
import { EmptyState } from '@/components/screen-states';
import { ClosedTag, LastCallTag, TypeChip } from '@/components/tags';
import { AppText } from '@/components/text';
import { showToast } from '@/components/toast';
import { Colors, Radius, Spacing, typeColor } from '@/constants/theme';
import { focusOn, useReduceMotion } from '@/lib/a11y';
import { fetchOpportunity } from '@/lib/api';
import {
  cleanTitle,
  countryListText,
  countryName,
  coverImageUrl,
  formatDate,
  isClosed,
  isFillerText,
  isLastCall,
  looksEnglishShort,
  spainEligibility,
} from '@/lib/format';
import { tapLight } from '@/lib/haptics';
import { countDetailOpen, maybeAskForReviewAfterSave } from '@/lib/review';
import { shareOpportunity } from '@/lib/share';
import type { Opportunity } from '@/lib/types';
import { useOpportunityData, useSavedState, useSeenState } from '@/state/opportunities';

/** Alto visible de la portada por debajo de la cabecera. */
const HERO_HEIGHT = 200;
/** Espera antes de pedir valoración tras guardar (deja leer el toast). */
const REVIEW_DELAY_MS = 1500;

/** El texto si tiene contenido real; null si está vacío o es relleno de la extracción. */
function realText(text: string | null | undefined, minChars?: number): string | null {
  return isFillerText(text, { minChars }) ? null : (text ?? '').trim();
}

function goBack() {
  if (router.canGoBack()) router.back();
  else router.replace('/');
}

export default function ProyectoScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  // Hooks estrechos: marcar como visto (SeenMarker) no repinta esta pantalla.
  const { getById } = useOpportunityData();
  const { savedRecords } = useSavedState();
  const known = id ? (getById(id) ?? savedRecords[id]) : undefined;
  // Lo descargado y el fallo van ligados a su id: al cambiar de proyecto no se enseña el anterior.
  const [fetched, setFetched] = useState<{ id: string; data: Opportunity } | null>(null);
  const [failedId, setFailedId] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const o = known ?? (fetched && fetched.id === id ? fetched.data : null);

  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const headerHeight = insets.top + HEADER_BAR_HEIGHT;
  const heroTotal = headerHeight + HERO_HEIGHT;

  // Si no está en la lista ni en guardados (enlace antiguo, aviso…), se pide la ficha.
  const needsFetch = !!id && !known;
  useEffect(() => {
    if (!needsFetch || !id) return;
    let alive = true;
    fetchOpportunity(id)
      .then((data) => {
        if (alive) setFetched({ id, data });
      })
      .catch(() => {
        if (alive) setFailedId(id);
      });
    return () => {
      alive = false;
    };
  }, [id, needsFetch, attempt]);

  // Scroll compartido con la cabecera.
  const scrollY = useSharedValue(0);
  const solidAt = useSharedValue(heroTotal - headerHeight);
  const titleAt = useSharedValue(Number.MAX_SAFE_INTEGER);
  const [solid, setSolid] = useState(false);
  const [titleVisible, setTitleVisible] = useState(false);

  const failed = !o && !!id && failedId === id;
  useEffect(() => {
    // En el estado de error no hay portada: la cabecera va en papel desde el principio.
    solidAt.set(failed ? 0 : heroTotal - headerHeight);
  }, [failed, heroTotal, headerHeight, solidAt]);

  useAnimatedReaction(
    () => scrollY.get() >= solidAt.get(),
    (now, prev) => {
      if (now !== prev) scheduleOnRN(setSolid, now);
    },
  );
  useAnimatedReaction(
    () => scrollY.get() >= titleAt.get(),
    (now, prev) => {
      if (now !== prev) scheduleOnRN(setTitleVisible, now);
    },
  );

  const title = o ? cleanTitle(o.title) : '';

  return (
    <View style={styles.screen}>
      <Stack.Screen options={{ headerShown: false, title: title || 'Proyecto' }} />
      <StatusBar style={o && !solid && !failed ? 'light' : 'dark'} />
      {id ? <SeenMarker id={id} /> : null}

      {o ? (
        <Detail
          o={o}
          scrollY={scrollY}
          solidAt={solidAt}
          titleAt={titleAt}
          headerHeight={headerHeight}
          heroTotal={heroTotal}
          reduceMotion={reduceMotion}
          titleVisible={titleVisible}
          title={title}
        />
      ) : (
        <>
          <DetailHeader
            scrollY={scrollY}
            solidAt={solidAt}
            titleAt={titleAt}
            reduceMotion={reduceMotion}
            titleVisible={false}
            title=""
            onBack={goBack}
          />
          {failed ? (
            <View style={[styles.error, { paddingTop: headerHeight }]}>
              <EmptyState
                title="No hemos podido abrirlo"
                text="Puede que el proyecto ya no exista o que no tengas conexión.">
                <Button
                  label="Reintentar"
                  onPress={() => {
                    setFailedId(null);
                    setAttempt((n) => n + 1);
                  }}
                />
                <Button label="Volver" variant="ghost" onPress={goBack} />
              </EmptyState>
            </View>
          ) : (
            <DetailSkeleton heroHeight={heroTotal} />
          )}
        </>
      )}
    </View>
  );
}

/**
 * Marca el proyecto como visto y cuenta la apertura. Va en su propio componente para que el
 * cambio de "vistos" solo lo repinte a él, no a la ficha.
 * La imagen-story NO se descarga aquí (1 MB y ~6 s de render): solo al pulsar Compartir.
 */
function SeenMarker({ id }: { id: string }) {
  const { markSeen } = useSeenState();
  useEffect(() => {
    markSeen(id);
    void countDetailOpen();
  }, [id, markSeen]);
  return null;
}

interface DetailProps {
  o: Opportunity;
  scrollY: SharedValue<number>;
  solidAt: SharedValue<number>;
  titleAt: SharedValue<number>;
  headerHeight: number;
  heroTotal: number;
  reduceMotion: boolean;
  titleVisible: boolean;
  title: string;
}

function Detail({ o, scrollY, solidAt, titleAt, headerHeight, heroTotal, reduceMotion, titleVisible, title }: DetailProps) {
  const insets = useSafeAreaInsets();
  const { savedIds, toggleSaved } = useSavedState();
  const saved = savedIds.has(o.identifier);
  const [sharing, setSharing] = useState(false);
  // Guardas contra el doble toque: un ref cambia al instante; el estado, en el siguiente render.
  const savingRef = useRef(false);
  const sharingRef = useRef(false);
  const [barHeight, setBarHeight] = useState(0);

  const scrollRef = useAnimatedRef<Animated.ScrollView>();
  const coveredTitleRef = useRef<HostInstance>(null);
  const layout = useRef({ sectionsY: 0, coveredY: 0 });

  const onScroll = useAnimatedScrollHandler((e) => {
    scrollY.set(e.contentOffset.y);
  });

  const closed = isClosed(o);
  // Solo la marca del mensaje original; la urgencia por fecha ya la dicen el texto y el color del plazo.
  const lastCall = isLastCall(o);
  const englishTitle = looksEnglishShort(title);
  const escSteps = !closed && needsEscNotice(o, applyUrl(o));
  const country = countryName(o.country_code);
  const toastOffset = Math.max(Spacing.md, barHeight - insets.bottom + Spacing.sm);

  // Resumen: si la descripción larga es el resumen ampliado, se enseña solo la larga (plegada).
  // Todo texto pasa por `realText`: el relleno de la extracción ("As per the Info-Pack…") no se enseña.
  const summary = realText(o.summary);
  const description = realText(o.detailed_description);
  let lead = summary ?? description;
  let about: string | null = null;
  if (summary && description && description.length > summary.length + 40) {
    if (description.startsWith(summary.slice(0, 60))) lead = description;
    else about = description;
  }

  const covered = realText(o.covered_costs);
  const hasCovered = !!covered;
  const hasCoords = o.latitude != null && o.longitude != null;
  const checked = typeof o.source_checked_at === 'string' ? formatDate(o.source_checked_at, true) : null;
  const imageCredit = o.image_url && o.image_credit ? o.image_credit : null;

  async function onSave() {
    if (savingRef.current) return;
    savingRef.current = true;
    tapLight();
    let result: Awaited<ReturnType<typeof toggleSaved>>;
    try {
      result = await toggleSaved(o.identifier, o);
    } catch {
      showToast('No hemos podido guardarlo. Inténtalo de nuevo.', { offset: toastOffset });
      return;
    } finally {
      savingRef.current = false;
    }

    if (!result.saved) {
      showToast(result.reminder === 'cancelled' ? 'Quitado de guardados. Ya no te avisaremos.' : 'Quitado de guardados', {
        actionLabel: 'Deshacer',
        onAction: () => void onSave(),
        icon: 'bookmark',
        offset: toastOffset,
      });
      return;
    }

    let message = 'Guardado';
    if (result.reminder === 'set' || result.reminder === 'already') {
      const when = reminderWhen(o);
      if (when) message = `Guardado. Te avisaremos el ${when.short} (${when.relative}).`;
    } else if (result.reminder === 'denied') {
      message = 'Guardado. Activa las notificaciones para que te avisemos.';
    }
    showToast(message, { icon: 'bookmarkFill', offset: toastOffset });
    setTimeout(() => void maybeAskForReviewAfterSave(), REVIEW_DELAY_MS);
  }

  async function onShare() {
    if (sharingRef.current) return;
    sharingRef.current = true;
    setSharing(true);
    try {
      await shareOpportunity(o);
    } finally {
      sharingRef.current = false;
      setSharing(false);
    }
  }

  function onSeeCovered() {
    const y = heroTotal + layout.current.sectionsY + layout.current.coveredY - headerHeight - Spacing.sm;
    scrollRef.current?.scrollTo({ y: Math.max(0, y), animated: !reduceMotion });
    focusOn(coveredTitleRef, reduceMotion ? 100 : 450);
  }

  function onSeeMap() {
    router.navigate({ pathname: '/mapa', params: { focus: o.identifier } });
  }

  function onSeeOpen() {
    if (country) router.navigate({ pathname: '/explorar', params: { q: country } });
    else router.navigate('/explorar');
  }

  function onTitleLayout(e: LayoutChangeEvent) {
    const { y, height } = e.nativeEvent.layout;
    // `y` es relativo al cuerpo, que empieza justo debajo de la portada.
    titleAt.set(heroTotal + y + height - headerHeight);
  }

  return (
    <View style={styles.screen}>
      {/* Primero en el árbol (va por encima con zIndex) para que TalkBack lea antes Volver/Guardar/Compartir. */}
      <DetailHeader
        scrollY={scrollY}
        solidAt={solidAt}
        titleAt={titleAt}
        reduceMotion={reduceMotion}
        titleVisible={titleVisible}
        title={title}
        onBack={goBack}
        actions={{ saved, onSave: () => void onSave(), sharing, onShare: () => void onShare() }}
      />

      <Animated.ScrollView
        ref={scrollRef}
        onScroll={onScroll}
        scrollEventThrottle={16}
        contentInsetAdjustmentBehavior="never"
        contentContainerStyle={{ paddingBottom: Spacing.xl }}>
        <Hero o={o} headerHeight={headerHeight} insetTop={insets.top} />

        <View style={styles.body}>
          <View style={styles.tags}>
            <TypeChip type={o.type} explain long />
            {closed ? <ClosedTag /> : lastCall ? <LastCallTag /> : null}
          </View>

          <View onLayout={onTitleLayout} style={styles.titleBlock}>
            <AppText
              variant="title2"
              accessibilityRole="header"
              accessibilityLanguage={englishTitle ? 'en' : undefined}
              selectable>
              {title}
            </AppText>
            <TopicTags topic={o.topic} />
            {o.organiser_name ? (
              <AppText variant="meta" color={Colors.muted}>
                Organiza {o.organiser_name}
              </AppText>
            ) : null}
          </View>

          {closed ? (
            <View style={styles.closedNote}>
              <AppText variant="label">Esta convocatoria ya ha cerrado</AppText>
              <AppText variant="meta" color={Colors.muted}>
                Ya no admite inscripciones. Hay muchas más abiertas{country ? ` en ${country} y otros países` : ''}.
              </AppText>
            </View>
          ) : null}

          <FitCard
            o={o}
            closed={closed}
            onSeeCovered={hasCovered ? onSeeCovered : null}
            onSeeMap={hasCoords ? onSeeMap : null}
            toastOffset={toastOffset}
          />

          {lead ? (
            <View style={styles.lead}>
              {/* Si está en inglés, CollapsibleText lo avisa y lo marca con accessibilityLanguage="en". */}
              <CollapsibleText text={lead} label="la descripción" />
            </View>
          ) : null}

          <View
            style={styles.sections}
            onLayout={(e) => {
              layout.current.sectionsY = e.nativeEvent.layout.y;
            }}>
            {escSteps ? <HowToApply /> : null}
            <AnchorSection
              title="Qué está cubierto"
              text={covered}
              titleRef={coveredTitleRef}
              onLayout={(e) => {
                layout.current.coveredY = e.nativeEvent.layout.y;
              }}
            />
            <TextSection title="Viaje" text={realText(o.travel_details)} />
            <TextSection title="Alojamiento" text={realText(o.accommodation_details)} />
            <TextSection title="Programa" text={realText(o.programme_details)} />
            <TextSection title="Perfil que buscan" text={realText(o.participant_profile)} />
            <TextSection title="Lo que aprenderás" text={realText(o.learning_outcomes)} />
            {about ? <TextSection title="Sobre el proyecto" text={about} /> : null}
            {spainEligibility(o) !== 'yes' ? (
              <TextSection title="Países participantes" text={countryListText(o.eligibility_countries)} />
            ) : null}
            <TextSection title="Contacto" text={realText(o.contact_information, 0)} />
          </View>

          <View style={styles.trust}>
            {checked ? (
              <View style={styles.trustRow} accessible accessibilityLabel={`Comprobado en la fuente el ${checked}`}>
                <Icon name="check" size={14} color={Colors.ink2} />
                <AppText variant="meta" color={Colors.ink2}>
                  Comprobado en la fuente el {checked}
                </AppText>
              </View>
            ) : null}
            <AppText variant="caption" color={Colors.muted}>
              Datos recogidos y ordenados por Corradi. Antes de apuntarte, confirma los requisitos en la convocatoria.
            </AppText>
            {imageCredit ? (
              <AppText variant="caption" color={Colors.muted}>
                {imageCredit}
              </AppText>
            ) : null}
          </View>
        </View>
      </Animated.ScrollView>

      <ApplyBar
        o={o}
        closed={closed}
        country={country}
        onSeeOpen={onSeeOpen}
        onLayout={(e) => setBarHeight(e.nativeEvent.layout.height)}
      />
    </View>
  );
}

/**
 * Portada decorativa. Con foto (la propia o, si no trae, la del banco de fotos de la web), la foto
 * llega hasta arriba (debajo de la cabecera) con un velo tras la barra de estado; sin foto posible,
 * la portada de marca empieza bajo la cabecera para que la etiqueta del país no quede tapada.
 */
function Hero({ o, headerHeight, insetTop }: { o: Opportunity; headerHeight: number; insetTop: number }) {
  if (coverImageUrl(o)) {
    return (
      <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        {/* Sin el tipo: el TypeChip de debajo ya lo dice. Nunca atenuada (`dimmed` es para listas). */}
        <Cover o={o} height={headerHeight + HERO_HEIGHT} variant="hero" showType={false} />
        <View style={[styles.statusScrim, { height: insetTop + Spacing.sm }]} />
      </View>
    );
  }
  return (
    <View
      style={{ paddingTop: headerHeight, backgroundColor: typeColor(o.type).cover }}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants">
      <Cover o={o} height={HERO_HEIGHT} variant="hero" showType={false} />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: Colors.paper },
  error: { flex: 1, justifyContent: 'center', padding: Spacing.md },
  statusScrim: { position: 'absolute', top: 0, left: 0, right: 0, backgroundColor: Colors.scrim },
  body: { paddingHorizontal: Spacing.md, paddingTop: Spacing.ml, gap: Spacing.md },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, alignItems: 'center' },
  titleBlock: { gap: Spacing.xs },
  closedNote: { backgroundColor: Colors.paper2, borderRadius: Radius.md, padding: Spacing.md, gap: Spacing.xs },
  lead: { marginTop: Spacing.xs },
  sections: { marginTop: Spacing.sm },
  trust: { gap: Spacing.xs, paddingTop: Spacing.sm },
  trustRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs },
});
