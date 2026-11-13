/**
 * Barra fija de abajo de la ficha: "Quiero apuntarme" si el enlace es un formulario o el Portal
 * Europeo; "Ver cómo apuntarte" si solo lleva a la información (redes, Telegram, PDF…). Más
 * "Más detalles" si hay infopack aparte. Con letra grande (fontScale > 1.3) los botones se
 * apilan. Proyecto cerrado: invita a ver los abiertos del mismo país.
 */
import { useRef } from 'react';
import { StyleSheet, useWindowDimensions, View, type LayoutChangeEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/button';
import { AppText } from '@/components/text';
import { Colors, Shadows, Spacing } from '@/constants/theme';
import type { Opportunity } from '@/lib/types';

import { applyUrl, infopackUrl, isDirectApplyUrl, isFormUrl, isPortalUrl, openUrl } from './apply';

export interface ApplyBarProps {
  o: Opportunity;
  closed: boolean;
  /** Nombre del país en español (para "Ver proyectos abiertos en …"). */
  country: string | null;
  onSeeOpen: () => void;
  onLayout?: (e: LayoutChangeEvent) => void;
}

export function ApplyBar({ o, closed, country, onSeeOpen, onLayout }: ApplyBarProps) {
  const insets = useSafeAreaInsets();
  const { fontScale } = useWindowDimensions();
  const stacked = fontScale > 1.3;
  const url = applyUrl(o);
  const info = infopackUrl(o);
  const formHelper = !closed && isFormUrl(url);
  const direct = isDirectApplyUrl(url);
  const hint = !url
    ? 'Aún no tenemos el enlace de inscripción'
    : formHelper
      ? 'Se abre el formulario de inscripción'
      : isPortalUrl(url)
        ? 'Abre la oferta en el Portal Europeo de la Juventud'
        : 'Abre el enlace con la información para apuntarte';
  // Evita abrir dos veces el enlace con un doble toque (el ref no espera a un render).
  const opening = useRef(false);

  async function open(target: () => Promise<void>) {
    if (opening.current) return;
    opening.current = true;
    try {
      await target();
    } finally {
      opening.current = false;
    }
  }

  return (
    <View
      onLayout={onLayout}
      style={[styles.bar, { paddingBottom: Math.max(insets.bottom, Spacing.ms) }]}>
      <View style={[styles.row, stacked && styles.column]}>
        {closed ? (
          <Button
            label={country ? `Ver proyectos abiertos en ${country}` : 'Ver proyectos abiertos'}
            icon="explore"
            onPress={onSeeOpen}
            style={[styles.main, stacked && styles.full]}
          />
        ) : (
          <Button
            label={!url || direct ? 'Quiero apuntarme' : 'Ver cómo apuntarte'}
            disabled={!url}
            onPress={() => {
              if (url) void open(() => openUrl(url));
            }}
            accessibilityHint={hint}
            style={[styles.main, stacked && styles.full]}
          />
        )}
        {info ? (
          <Button
            label="Más detalles"
            variant="secondary"
            onPress={() => void open(() => openUrl(info))}
            accessibilityLabel="Más detalles: convocatoria completa (infopack)"
            style={[styles.secondary, stacked && styles.full]}
          />
        ) : null}
      </View>
      {formHelper ? (
        <AppText variant="caption" color={Colors.muted} align="center" importantForAccessibility="no" accessibilityElementsHidden>
          Se abre el formulario de inscripción
        </AppText>
      ) : null}
      {!closed && !url ? (
        <AppText variant="caption" color={Colors.muted} align="center">
          Aún no tenemos el enlace de inscripción de este proyecto.
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.ms,
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    ...Shadows.up,
  },
  row: { flexDirection: 'row', gap: Spacing.sm, alignItems: 'stretch' },
  column: { flexDirection: 'column' },
  main: { flex: 1, paddingHorizontal: Spacing.ms },
  secondary: { paddingHorizontal: Spacing.md, flexShrink: 1 },
  full: { flex: 0, alignSelf: 'stretch' },
});
