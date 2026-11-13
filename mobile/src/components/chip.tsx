/**
 * Chip de filtro / selección (≥44 pt de alto).
 *
 *   <Chip label="Curso" type="TRAINING_COURSE" selected={f === 'TC'} onPress={…} />
 *   <Chip label="Cierra pronto" variant="accent" selected onPress={…} />
 *   <Chip label="Italia" size="sm" />   // etiqueta no interactiva (fondo paper2)
 *
 * - Sin seleccionar: fondo surface + borde controlBorder; seleccionado: fondo ink + texto paper
 *   (variant 'accent': fondo clay + texto blanco).
 * - `type` añade delante un punto con el color y la letra del tipo (igual que el mapa).
 * - Vibración de selección al tocar. Rol "button" con estado `selected`.
 */
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, Fonts, MIN_TOUCH, Radius, Spacing, typeColor, typeGlyph } from '@/constants/theme';
import { tapSelection } from '@/lib/haptics';
import type { OpportunityType } from '@/lib/types';

import { Icon, type IconName } from './icon';
import { AppText } from './text';

export interface ChipProps {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  /** 'default' (tinta al seleccionar) o 'accent' (arcilla al seleccionar). */
  variant?: 'default' | 'accent';
  /** 'md' interactivo (por defecto) o 'sm' etiqueta estática. */
  size?: 'md' | 'sm';
  /** Punto + letra del tipo delante del texto. */
  type?: OpportunityType | null;
  icon?: IconName;
  /** Número opcional detrás del texto: "Curso 12". Se lee como "Curso, 12 proyectos". */
  count?: number;
  disabled?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  style?: StyleProp<ViewStyle>;
}

export function TypeDot({ type, size = 18 }: { type: OpportunityType | null | undefined; size?: number }) {
  const c = typeColor(type);
  return (
    <View
      style={[styles.dot, { width: size, height: size, borderRadius: size / 2, backgroundColor: c.accent }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants">
      <AppText
        variant="caption"
        color={Colors.white}
        allowFontScaling={false}
        style={{ fontFamily: Fonts.displayBold, fontSize: size * 0.55, lineHeight: size * 0.75 }}>
        {typeGlyph(type)}
      </AppText>
    </View>
  );
}

export function Chip({
  label,
  selected = false,
  onPress,
  variant = 'default',
  size = 'md',
  type,
  icon,
  count,
  disabled,
  accessibilityLabel,
  accessibilityHint,
  style,
}: ChipProps) {
  if (size === 'sm') {
    return (
      <View style={[styles.small, style]} accessibilityLabel={accessibilityLabel}>
        {type ? <TypeDot type={type} size={14} /> : null}
        {icon ? <Icon name={icon} size={12} color={Colors.ink2} /> : null}
        <AppText variant="caption" color={Colors.ink2} style={styles.smallText}>
          {label}
        </AppText>
      </View>
    );
  }

  const fg = selected ? (variant === 'accent' ? Colors.white : Colors.paper) : Colors.ink;
  const selectedStyle = variant === 'accent' ? styles.selectedAccent : styles.selected;
  const a11yLabel = accessibilityLabel ?? (count != null ? `${label}, ${count} ${count === 1 ? 'proyecto' : 'proyectos'}` : label);

  return (
    <Pressable
      onPress={
        onPress
          ? () => {
              tapSelection();
              onPress();
            }
          : undefined
      }
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={a11yLabel}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ selected, disabled: !!disabled }}
      style={({ pressed }) => [
        styles.chip,
        selected && selectedStyle,
        pressed && !selected && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}>
      {type ? <TypeDot type={type} /> : null}
      {icon ? <Icon name={icon} size={16} color={fg} /> : null}
      <AppText variant="label" color={fg}>
        {label}
      </AppText>
      {count != null ? (
        <AppText variant="meta" color={fg}>
          {count}
        </AppText>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: MIN_TOUCH,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.controlBorder,
    backgroundColor: Colors.surface,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  selected: { backgroundColor: Colors.ink, borderColor: Colors.ink },
  selectedAccent: { backgroundColor: Colors.clay, borderColor: Colors.clay },
  pressed: { backgroundColor: Colors.paper2 },
  disabled: { opacity: 0.5 },
  dot: { alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: Colors.white },
  small: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    alignSelf: 'flex-start',
    backgroundColor: Colors.paper2,
    borderRadius: Radius.pill,
    paddingHorizontal: Spacing.ms - Spacing.xxs,
    paddingVertical: Spacing.xs,
  },
  smallText: { fontFamily: Fonts.sansSemiBold },
});
