/** Enlace de texto dentro de la ficha ("Ver en el mapa", "Consulta qué está cubierto ↓"). Caja ≥44 pt. */
import { Pressable, StyleSheet } from 'react-native';

import { Icon, type IconName } from '@/components/icon';
import { AppText } from '@/components/text';
import { Colors, MIN_TOUCH, Spacing } from '@/constants/theme';

export interface InlineLinkProps {
  label: string;
  onPress: () => void;
  icon?: IconName;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  /** 'link' para navegar, 'button' para acciones en la misma pantalla. */
  role?: 'link' | 'button';
}

export function InlineLink({ label, onPress, icon, accessibilityLabel, accessibilityHint, role = 'button' }: InlineLinkProps) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={role}
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityHint={accessibilityHint}
      style={({ pressed }) => [styles.link, pressed && styles.pressed]}>
      {icon ? <Icon name={icon} size={16} color={Colors.clayText} /> : null}
      <AppText variant="label" color={Colors.clayText} style={styles.text}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  link: {
    minHeight: MIN_TOUCH,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    alignSelf: 'flex-start',
    paddingRight: Spacing.sm,
    marginVertical: -Spacing.sm,
  },
  pressed: { opacity: 0.6 },
  text: { flexShrink: 1, textDecorationLine: 'underline' },
});
