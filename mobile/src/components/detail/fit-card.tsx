/**
 * Tarjeta "¿Es para ti?": lo que hay que saber antes de nada (para quién, cuánto pagas, si
 * vale desde España, dónde, cuándo y hasta cuándo hay plazo). Cada fila se lee como un solo
 * elemento; los enlaces y el aviso quedan fuera del grupo y se alcanzan por separado.
 */
import { StyleSheet, View } from 'react-native';

import { FactRow } from '@/components/detail-parts';
import { AppText } from '@/components/text';
import { CardBorder, Colors, Fonts, Radius, Spacing } from '@/constants/theme';
import {
  audienceText,
  costSummary,
  deadlineInfo,
  durationText,
  flagEmoji,
  formatDateLong,
  formatDateRange,
  placeLabel,
  spainEligibility,
  type DeadlineTone,
} from '@/lib/format';
import type { Opportunity } from '@/lib/types';

import { InlineLink } from './inline-link';
import { ReminderControl } from './reminder-control';

export interface FitCardProps {
  o: Opportunity;
  closed: boolean;
  /** Lleva a la sección "Qué está cubierto" (null si no hay esa sección). */
  onSeeCovered: (() => void) | null;
  /** Abre el mapa centrado en el proyecto (null si no tiene coordenadas). */
  onSeeMap: (() => void) | null;
  toastOffset: number;
}

const TONE_COLOR: Record<DeadlineTone, string> = {
  urgent: Colors.clayText,
  soon: Colors.clayText,
  closed: Colors.muted,
  normal: Colors.ink,
  unknown: Colors.ink,
};

/** Valor de una fila con color propio: lo visual va oculto y el texto entra en la etiqueta del grupo. */
function ColoredValue({ text, color, strong }: { text: string; color: string; strong?: boolean }) {
  return (
    <AppText
      variant="bodyLg"
      color={color}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.coloredValue, strong && styles.strong]}>
      {text}
    </AppText>
  );
}

function Note({ children }: { children: string }) {
  return (
    <AppText variant="meta" color={Colors.muted} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {children}
    </AppText>
  );
}

export function FitCard({ o, closed, onSeeCovered, onSeeMap, toastOffset }: FitCardProps) {
  const audience = audienceText(o);
  const cost = costSummary(o);
  const spain = spainEligibility(o);
  const place = placeLabel(o);
  const flag = flagEmoji(o.country_code);
  const approx = !!o.approx_location && !!place;
  const range = formatDateRange(o.start_date, o.end_date);
  const duration = durationText(o);
  const dates = range ? [range, duration].filter(Boolean).join(' · ') : duration ? `Por confirmar · ${duration}` : 'Por confirmar';
  const deadline = deadlineInfo(o);
  const exactDeadline = !deadline.estimated && !closed && o.application_deadline ? formatDateLong(o.application_deadline) : null;
  const estimatedNote = deadline.estimated && !closed ? 'La convocatoria no da una fecha exacta: apúntate cuanto antes.' : null;

  const placeText = place ? `${place}${approx ? ' · ubicación aproximada' : ''}` : 'Por confirmar';
  const deadlineSpoken = [deadline.text, exactDeadline, estimatedNote].filter(Boolean).join('. ');

  return (
    <View style={styles.card}>
      <AppText variant="title3" accessibilityRole="header" style={styles.heading}>
        ¿Es para ti?
      </AppText>

      <FactRow icon="people" label="Para quién" value={audience} />

      {cost ? (
        <FactRow icon="euro" label="Cuánto pagas" value={cost} />
      ) : onSeeCovered ? (
        // Sin coste claro, pero hay una sección real "Qué está cubierto": se lleva allí.
        <FactRow icon="euro" label="Cuánto pagas" spokenValue="sin confirmar">
          <InlineLink
            label="Consulta qué está cubierto ↓"
            accessibilityLabel="Consulta qué está cubierto"
            accessibilityHint="Baja hasta la sección Qué está cubierto"
            onPress={onSeeCovered}
          />
        </FactRow>
      ) : null}

      {spain === 'yes' ? (
        <FactRow icon="globe" label="Desde España" value="Pueden apuntarse residentes en España" />
      ) : spain === 'check' ? (
        <FactRow icon="globe" label="Desde España" spokenValue="Revisa si admiten participantes desde España">
          <ColoredValue text="Revisa si admiten participantes desde España" color={Colors.clayText} />
        </FactRow>
      ) : null}

      <FactRow
        icon="place"
        label="Destino"
        value={flag && place ? `${flag}  ${placeText}` : placeText}
        spokenValue={placeText}>
        {onSeeMap ? (
          <InlineLink
            label="Ver en el mapa"
            icon="map"
            role="link"
            accessibilityHint="Abre el mapa centrado en este proyecto"
            onPress={onSeeMap}
          />
        ) : null}
      </FactRow>

      <FactRow icon="calendar" label="Fechas" value={dates} />

      <FactRow icon="hourglass" label="Plazo" spokenValue={deadlineSpoken}>
        <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.deadline}>
          <ColoredValue
            text={deadline.text}
            color={TONE_COLOR[deadline.tone]}
            strong={deadline.tone === 'urgent' || deadline.tone === 'soon'}
          />
          {exactDeadline ? <Note>{exactDeadline}</Note> : null}
          {estimatedNote ? <Note>{estimatedNote}</Note> : null}
        </View>
        {!closed ? <ReminderControl o={o} toastOffset={toastOffset} /> : null}
      </FactRow>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    // Mismo filete que las tarjetas de las listas; sin sombra.
    ...CardBorder,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xs,
  },
  heading: { marginBottom: Spacing.xs },
  // FactRow separa sus hijos de la etiqueta con `gap`: el valor va pegado, como en las demás filas.
  coloredValue: { marginTop: -Spacing.sm },
  strong: { fontFamily: Fonts.sansSemiBold },
  deadline: { gap: Spacing.xxs },
});
