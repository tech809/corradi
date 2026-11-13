/**
 * Botón de solo icono: caja real de 44×44 pt. `accessibilityLabel` es obligatoria.
 * `selected` (p. ej. "Guardado") se anuncia como estado. Vibración ligera al tocar.
 * `variant="filled"` = círculo crema con sombra, para ponerlo encima de una foto/portada.
 */
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, MIN_TOUCH, Shadows } from '@/constants/theme';
import { tapLight } from '@/lib/haptics';

import { Icon, type IconName } from './icon';

export interface IconButtonProps {
  icon: IconName;
  onPress: () => void;
  accessibilityLabel: string;
  accessibilityHint?: string;
  /** Color del icono (≥3:1 contra el fondo). Por defecto Colors.ink. */
  color?: string;
  size?: number;
  selected?: boolean;
  disabled?: boolean;
  variant?: 'plain' | 'filled';
  style?: StyleProp<ViewStyle>;
}

export function IconButton({
  icon,
  onPress,
  accessibilityLabel,
  accessibilityHint,
  color = Colors.ink,
  size = 22,
  selected,
  disabled,
  variant = 'plain',
  style,
}: IconButtonProps) {
  return (
    <Pressable
      onPress={() => {
        tapLight();
        onPress();
      }}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ selected: !!selected, disabled: !!disabled }}
      style={({ pressed }) => [
        styles.btn,
        variant === 'filled' && styles.filled,
        pressed && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}>
      <Icon name={icon} size={size} color={color} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: { width: MIN_TOUCH, height: MIN_TOUCH, borderRadius: MIN_TOUCH / 2, alignItems: 'center', justifyContent: 'center' },
  filled: { backgroundColor: Colors.surface, ...Shadows.sm },
  pressed: { backgroundColor: Colors.paper2 },
  disabled: { opacity: 0.4 },
});
