/**
 * Botón de texto.
 *
 * - primary: relleno arcilla, texto blanco (5:1), alto mínimo 52.
 * - secondary: fondo surface + borde controlBorder, texto tinta, alto mínimo 48.
 * - ghost: sin fondo, texto clayText, alto mínimo 44.
 *
 * El texto se centra y ocupa las líneas que haga falta (nunca se corta, ni con letra grande). En `loading` se ve un
 * spinner en lugar del icono, el texto se mantiene y el lector anuncia "ocupado".
 */
import { ActivityIndicator, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, MIN_TOUCH, Radius, Spacing } from '@/constants/theme';

import { Icon, type IconName } from './icon';
import { AppText } from './text';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';

export interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  icon?: IconName;
  /** Icono detrás del texto en lugar de delante. */
  iconPosition?: 'start' | 'end';
  disabled?: boolean;
  loading?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  style?: StyleProp<ViewStyle>;
}

const FG: Record<ButtonVariant, string> = { primary: Colors.white, secondary: Colors.ink, ghost: Colors.clayText };

export function Button({
  label,
  onPress,
  variant = 'primary',
  icon,
  iconPosition = 'start',
  disabled,
  loading,
  accessibilityLabel,
  accessibilityHint,
  style,
}: ButtonProps) {
  const fg = FG[variant];
  const inactive = !!(disabled || loading);
  const glyph = loading ? (
    <ActivityIndicator size="small" color={fg} />
  ) : icon ? (
    <Icon name={icon} size={18} color={fg} />
  ) : null;

  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy: !!loading }}
      style={({ pressed }) => [
        styles.base,
        styles[variant],
        pressed && PRESSED[variant],
        disabled && !loading && styles.disabled,
        style,
      ]}>
      {iconPosition === 'start' ? glyph : null}
      <View style={styles.labelWrap}>
        <AppText variant="button" color={fg} align="center">
          {label}
        </AppText>
      </View>
      {iconPosition === 'end' ? glyph : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 48,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.ms,
    borderRadius: Radius.pill,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  primary: { backgroundColor: Colors.clay, minHeight: 52 },
  secondary: { backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.controlBorder },
  ghost: { backgroundColor: 'transparent', minHeight: MIN_TOUCH, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  disabled: { opacity: 0.5 },
  labelWrap: { flexShrink: 1 },
});

const PRESSED = StyleSheet.create({
  primary: { backgroundColor: Colors.clayDark },
  secondary: { backgroundColor: Colors.paper2 },
  ghost: { backgroundColor: Colors.paper2 },
});
