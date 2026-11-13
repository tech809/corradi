/**
 * Tarjeta de una oportunidad.
 *
 *   <OpportunityCard opportunity={o} onOpen={openProject} seen={seen.has(o.identifier)} reminderOn={…} />
 *
 * - Normal: portada (foto; tipo + país encima) con la etiqueta de tipo; título limpio
 *   (`cleanTitle`, sin cortar); una línea "Ciudad · tema" (sin repetir el país de la portada);
 *   otra "fechas · duración · coste" (coste solo si se sabe: "Gratis" / "Cuota 300 €"); el plazo (arcilla si quedan ≤3 días) con campana si hay
 *   recordatorio; etiquetas Última llamada (solo `isLastCall`) / Cerrado / Visto.
 * - `compact`: miniatura 56×56 a la izquierda y texto a la derecha (listas del mapa), título
 *   en hasta 3 líneas.
 * - `onOpen(id)` es la alternativa estable a `onPress` (evita crear una función por fila).
 * - El lector lee la tarjeta como un único botón con todo el contenido y la pista "Abre la ficha".
 * - `seen`: `<Cover dimmed>` atenúa SOLO la capa de foto/marca (opacidad 0.6), nunca el
 *   degradado ni el texto de la portada (país), + etiqueta "Visto". La etiqueta de tipo y los
 *   textos de la tarjeta van fuera de esa capa, así que mantienen ≥4.5:1.
 * - La portada no repite el tipo (`showType={false}`): ya lo dice la etiqueta de tipo encima.
 * - Estilo de tarjeta de la web: filete `rule` de 1 px, sombra mínima, radio `Radius.card`.
 */
import { memo } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { CardBorder, Colors, Radius, Shadows, Sizes, Spacing } from '@/constants/theme';
import {
  cityLabel,
  cleanTitle,
  costShort,
  deadlineInfo,
  durationText,
  flagEmoji,
  formatDateRange,
  isClosed,
  isLastCall,
  placeLabel,
  topicList,
  typeLabel,
  typeShortLabel,
} from '@/lib/format';
import type { Opportunity } from '@/lib/types';

import { Cover, coverShowsCountry } from './cover';
import { Icon } from './icon';
import { PressableScale } from './pressable-scale';
import { ClosedTag, LastCallTag, SeenTag, TypeChip } from './tags';
import { AppText } from './text';

export interface OpportunityCardProps {
  opportunity: Opportunity;
  /** Al tocar. Usa esto u `onOpen`. */
  onPress?: () => void;
  /** Alternativa estable a `onPress`: recibe el identificador. */
  onOpen?: (identifier: string) => void;
  /** Versión reducida con miniatura (listas del mapa). */
  compact?: boolean;
  /** Ya abierta antes por el usuario. */
  seen?: boolean;
  /** Tiene recordatorio de plazo activado. */
  reminderOn?: boolean;
  style?: StyleProp<ViewStyle>;
}

const COVER_HEIGHT = Sizes.cardCover;

/** Texto que lee el lector de pantalla para la tarjeta entera. */
export function opportunityA11yLabel(o: Opportunity, opts: { seen?: boolean; reminderOn?: boolean } = {}): string {
  const closed = isClosed(o);
  const status = [closed ? 'Cerrado' : isLastCall(o) ? 'Última llamada' : null, opts.seen ? 'Visto' : null];
  return [
    typeLabel(o.type),
    ...status,
    cleanTitle(o.title),
    placeLabel(o),
    topicList(o.topic)[0] ?? null,
    formatDateRange(o.start_date, o.end_date),
    durationText(o),
    costShort(o),
    deadlineInfo(o).text,
    opts.reminderOn ? 'Recordatorio activado' : null,
  ]
    .filter(Boolean)
    .join('. ');
}

export const OpportunityCard = memo(function OpportunityCard({
  opportunity: o,
  onPress,
  onOpen,
  compact = false,
  seen = false,
  reminderOn = false,
  style,
}: OpportunityCardProps) {
  const closed = isClosed(o);
  const lastCall = isLastCall(o);
  const deadline = deadlineInfo(o);
  const place = placeLabel(o);
  const dates = formatDateRange(o.start_date, o.end_date);
  const duration = durationText(o);
  const flag = flagEmoji(o.country_code);
  const title = cleanTitle(o.title) || o.title;
  const deadlineColor = closed ? Colors.muted : deadline.tone === 'urgent' ? Colors.clayText : Colors.ink2;
  const topic = topicList(o.topic)[0] ?? null;
  // Si la portada ya enseña el país, aquí solo la ciudad.
  const where = coverShowsCountry(o) ? cityLabel(o) : place;
  const whereLine = [where, topic].filter(Boolean).join(' · ');
  const whenLine = [dates, duration, costShort(o)].filter(Boolean).join(' · ');
  const handlePress = onOpen ? () => onOpen(o.identifier) : onPress;

  const a11y = {
    accessibilityRole: 'button' as const,
    accessibilityLabel: opportunityA11yLabel(o, { seen, reminderOn }),
    accessibilityHint: 'Abre la ficha',
  };

  const deadlineRow = (
    <View style={styles.deadlineRow}>
      <Icon name="hourglass" size={14} color={deadlineColor} />
      <AppText variant="label" color={deadlineColor} style={styles.shrink}>
        {deadline.text}
      </AppText>
      {reminderOn ? <Icon name="bellFill" size={14} color={Colors.clayText} /> : null}
    </View>
  );

  const statusTags =
    closed || lastCall || seen ? (
      <View style={styles.tags}>
        {closed ? <ClosedTag /> : lastCall ? <LastCallTag /> : null}
        {seen ? <SeenTag /> : null}
      </View>
    ) : null;

  if (compact) {
    return (
      <PressableScale {...a11y} onPress={handlePress} style={[styles.card, styles.compact, style]} pressedStyle={styles.pressed}>
        <Cover o={o} height={Sizes.thumb} variant="thumb" dimmed={seen} style={styles.thumb} />
        <View style={styles.compactBody}>
          <AppText variant="eyebrow" color={Colors.muted}>
            {typeShortLabel(o.type)}
          </AppText>
          <AppText variant="cardTitleSm" numberOfLines={3}>
            {title}
          </AppText>
          {place ? (
            <AppText variant="meta" color={Colors.ink2}>
              {flag ? `${flag} ` : ''}
              {place}
            </AppText>
          ) : null}
          {deadlineRow}
          {statusTags}
        </View>
      </PressableScale>
    );
  }

  return (
    <PressableScale {...a11y} onPress={handlePress} style={[styles.card, style]} pressedStyle={styles.pressed}>
      <View style={styles.coverWrap}>
        {/* `dimmed` atenúa solo la foto; el país, el degradado y la etiqueta de tipo no. */}
        <Cover o={o} height={COVER_HEIGHT} showType={false} dimmed={seen} />
        <TypeChip type={o.type} overlay style={styles.typeOverlay} />
      </View>
      <View style={styles.body}>
        {statusTags}
        <AppText variant="cardTitle">{title}</AppText>
        {whereLine ? (
          <AppText variant="meta" color={Colors.ink2}>
            {whereLine}
          </AppText>
        ) : null}
        {whenLine ? (
          <AppText variant="meta" color={Colors.muted}>
            {whenLine}
          </AppText>
        ) : null}
        {deadlineRow}
      </View>
    </PressableScale>
  );
});

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    ...CardBorder,
    ...Shadows.card,
  },
  pressed: { backgroundColor: Colors.paper2 },
  coverWrap: {
    height: COVER_HEIGHT,
    // 1 px menos que la tarjeta: queda dentro del filete.
    borderTopLeftRadius: Radius.card - 1,
    borderTopRightRadius: Radius.card - 1,
    overflow: 'hidden',
  },
  typeOverlay: { position: 'absolute', top: Spacing.ms, left: Spacing.ms },
  body: { padding: Spacing.md, gap: Spacing.sm },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs2 },
  deadlineRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs2 },
  shrink: { flexShrink: 1 },
  compact: { flexDirection: 'row', alignItems: 'flex-start', padding: Spacing.ms, gap: Spacing.ms },
  thumb: { width: Sizes.thumb, borderRadius: Radius.sm },
  compactBody: { flex: 1, gap: Spacing.xs },
});
