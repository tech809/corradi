/**
 * Control segmentado (dos o más opciones excluyentes), p. ej. "Mapa | Lista".
 *
 *   <SegmentedControl
 *     accessibilityLabel="Vista"
 *     value={view}
 *     onChange={setView}
 *     options={[{ value: 'map', label: 'Mapa', icon: 'map' }, { value: 'list', label: 'Lista', icon: 'list' }]}
 *   />
 *
 * Cada segmento mide ≥44 pt y vibra al cambiar. La opción activa va rellena de tinta.
 * `role` dice qué es para el lector:
 * - 'tab' (por defecto): cambia lo que se ve ("Mapa | Lista"). "tablist" + "tab" con `selected`.
 * - 'radio': elige una opción de un ajuste ("Ordenar por"). "radiogroup" + "radio" con `checked`.
 * La posición ("1 de 2") la dice el propio lector: no se añade a mano.
 */
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, MIN_TOUCH, Radius, Spacing } from '@/constants/theme';
import { tapSelection } from '@/lib/haptics';

import { Icon, type IconName } from './icon';
import { AppText } from './text';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: IconName;
  accessibilityLabel?: string;
}

export type SegmentedRole = 'tab' | 'radio';

export interface SegmentedControlProps<T extends string> {
  options: readonly SegmentedOption<T>[];
  /** 'tab' (cambia la vista, por defecto) o 'radio' (elige un valor, p. ej. el orden). */
  role?: SegmentedRole;
  value: T;
  onChange: (value: T) => void;
  /** Nombre del grupo para el lector ("Vista", "Ordenar por"…). */
  accessibilityLabel?: string;
  style?: StyleProp<ViewStyle>;
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  role = 'tab',
  accessibilityLabel,
  style,
}: SegmentedControlProps<T>) {
  const radio = role === 'radio';
  return (
    <View style={[styles.wrap, style]} accessibilityRole={radio ? 'radiogroup' : 'tablist'} accessibilityLabel={accessibilityLabel}>
      {options.map((opt) => {
        const selected = opt.value === value;
        const fg = selected ? Colors.paper : Colors.ink;
        return (
          <Pressable
            key={opt.value}
            onPress={() => {
              if (selected) return;
              tapSelection();
              onChange(opt.value);
            }}
            accessibilityRole={radio ? 'radio' : 'tab'}
            accessibilityLabel={opt.accessibilityLabel ?? opt.label}
            accessibilityState={radio ? { checked: selected } : { selected }}
            style={({ pressed }) => [styles.segment, selected && styles.active, pressed && !selected && styles.pressed]}>
            {opt.icon ? <Icon name={opt.icon} size={16} color={fg} /> : null}
            <AppText variant="label" color={fg} align="center">
              {opt.label}
            </AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    padding: Spacing.xxs,
    gap: Spacing.xxs,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.controlBorder,
    backgroundColor: Colors.surface,
  },
  segment: {
    flex: 1,
    minHeight: MIN_TOUCH,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radius.pill,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs2,
  },
  active: { backgroundColor: Colors.ink },
  pressed: { backgroundColor: Colors.paper2 },
});
