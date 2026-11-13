/**
 * Etiquetas pequeñas (no son filtros: para filtros usa <Chip>).
 *
 * - <TypeChip type explain />  tipo de proyecto con sus colores; con `explain` (o `onPress`) es
 *   un botón que explica qué es ese formato (Alert con TYPE_EXPLAINERS) y lleva un icono ⓘ.
 *   `overlay` = fondo crema translúcido para ponerlo encima de una portada.
 * - <LastCallTag />, <ClosedTag />, <SeenTag />, <NewDot /> (etiqueta "Nuevo").
 *
 * Todas permiten escalar la fuente y no cortan el texto.
 */
import { Alert, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, Fonts, Radius, Sizes, Spacing, TypeColors, TypeColorsFallback, typeColor, type TypeColorSet } from '@/constants/theme';
import { typeExplainer, typeLabel, typeShortLabel } from '@/lib/format';
import { tapLight } from '@/lib/haptics';
import type { OpportunityType } from '@/lib/types';

import { Icon } from './icon';
import { AppText } from './text';

/** @deprecated Usa `TypeColors` / `typeColor()` de '@/constants/theme'. `block` = `cover`. */
export const TYPE_COLORS: Record<OpportunityType | 'OTHER', TypeColorSet & { block: string }> = {
  YOUTH_EXCHANGE: { ...TypeColors.YOUTH_EXCHANGE, block: TypeColors.YOUTH_EXCHANGE.cover },
  TRAINING_COURSE: { ...TypeColors.TRAINING_COURSE, block: TypeColors.TRAINING_COURSE.cover },
  VOLUNTEERING: { ...TypeColors.VOLUNTEERING, block: TypeColors.VOLUNTEERING.cover },
  OTHER: { ...TypeColorsFallback, block: TypeColorsFallback.cover },
};

/** @deprecated Usa `typeColor()` de '@/constants/theme'. */
export function typeColors(type: OpportunityType | null | undefined) {
  return { ...typeColor(type), block: typeColor(type).cover };
}

/** Enseña qué es un formato en un diálogo del sistema. */
export function explainType(type: OpportunityType | null | undefined): void {
  const text = typeExplainer(type);
  if (!text) return;
  Alert.alert(typeLabel(type), text, [{ text: 'Entendido' }]);
}

/** Fondo crema translúcido para etiquetas encima de una portada (texto ≥6:1 sobre cualquier foto). */
export const OVERLAY_TAG_BG = Colors.overlayTag;
/** Tope de escalado de fuente de la etiqueta de tipo encima de una foto. */
const OVERLAY_MAX_FONT_SCALE = 1.6;

interface TypeChipProps {
  type: OpportunityType | null | undefined;
  /** Si es true, al tocarlo explica el formato (Alert). */
  explain?: boolean;
  /** Acción propia al tocarlo (tiene prioridad sobre `explain`). */
  onPress?: () => void;
  /** Encima de una portada: fondo crema translúcido. */
  overlay?: boolean;
  /** Etiqueta larga ("Intercambio juvenil") en lugar de la corta. */
  long?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function TypeChip({ type, explain, onPress, overlay, long, style }: TypeChipProps) {
  const c = typeColor(type);
  const label = long ? typeLabel(type) : typeShortLabel(type);
  const action = onPress ?? (explain && typeExplainer(type) ? () => explainType(type) : undefined);
  const bg = { backgroundColor: overlay ? OVERLAY_TAG_BG : c.chipBg };

  const content = (
    <>
      {/* Encima de una foto, tope de escalado: a 3× taparía media portada. */}
      <AppText
        variant="caption"
        color={c.chipText}
        style={styles.text}
        maxFontSizeMultiplier={overlay ? OVERLAY_MAX_FONT_SCALE : undefined}>
        {label}
      </AppText>
      {action ? <Icon name="info" size={13} color={c.chipText} /> : null}
    </>
  );

  if (!action) {
    return (
      <View style={[styles.tag, styles.row, bg, style]} accessibilityLabel={typeLabel(type)}>
        {content}
      </View>
    );
  }
  return (
    <Pressable
      onPress={() => {
        tapLight();
        action();
      }}
      hitSlop={{ top: 10, bottom: 10, left: 6, right: 6 }}
      accessibilityRole="button"
      accessibilityLabel={`${typeLabel(type)}. Qué es`}
      accessibilityHint="Explica este tipo de proyecto"
      style={({ pressed }) => [styles.tag, styles.row, styles.pressable, bg, pressed && styles.pressed, style]}>
      {content}
    </Pressable>
  );
}

export function LastCallTag({ style }: { style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.tag, styles.row, { backgroundColor: Colors.clay }, style]}>
      <Icon name="bolt" size={11} color={Colors.white} />
      <AppText variant="caption" color={Colors.white} style={styles.text}>
        Última llamada
      </AppText>
    </View>
  );
}

export function ClosedTag({ style }: { style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.tag, { backgroundColor: Colors.paper2 }, style]}>
      <AppText variant="caption" color={Colors.ink2} style={styles.text}>
        Cerrado
      </AppText>
    </View>
  );
}

export function SeenTag({ style }: { style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.tag, styles.row, { backgroundColor: Colors.paper2 }, style]}>
      <Icon name="eye" size={12} color={Colors.ink2} />
      <AppText variant="caption" color={Colors.ink2} style={styles.text}>
        Visto
      </AppText>
    </View>
  );
}

/** Etiqueta "Nuevo" (tinta). */
export function NewDot({ style }: { style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.tag, { backgroundColor: Colors.ink }, style]}>
      <AppText variant="caption" color={Colors.paper} style={styles.text}>
        Nuevo
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: Radius.pill,
    alignSelf: 'flex-start',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs },
  pressable: { minHeight: Sizes.tagMinHeight },
  pressed: { opacity: 0.7 },
  text: { fontFamily: Fonts.sansSemiBold, letterSpacing: 0.1 },
});
