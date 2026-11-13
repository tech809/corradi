/**
 * Piezas de la ficha de proyecto.
 *
 * - <FactRow icon label value />  dato clave con icono. Se lee como un solo elemento
 *   "Destino: Kaunas, Lituania". `children` (p. ej. un botón) queda fuera del grupo y se puede
 *   alcanzar por separado.
 * - <Section title>…</Section>  bloque con titular serif (rol header) y separador.
 * - <TextSection title text />  sección de texto largo con "Leer más" (≥44 pt, estado expanded).
 * - <CollapsibleText text />  solo el texto plegable, sin titular. Si el texto parece inglés
 *   (`looksEnglish`), lleva la nota "Texto original en inglés" y el lector lo lee con voz inglesa.
 */
import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, MIN_TOUCH, Spacing } from '@/constants/theme';
import { looksEnglish } from '@/lib/format';

import { Icon, type IconName } from './icon';
import { AppText } from './text';

export interface FactRowProps {
  icon: IconName;
  label: string;
  value?: string | null;
  /** Texto para el lector si `value` no basta (p. ej. sin la bandera emoji). */
  spokenValue?: string;
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
}

export function FactRow({ icon, label, value, spokenValue, children, style }: FactRowProps) {
  if (!value && !children) return null;
  const spoken = spokenValue ?? value;
  return (
    <View style={[styles.fact, style]}>
      <View style={styles.factIcon}>
        <Icon name={icon} size={20} color={Colors.clayText} />
      </View>
      <View style={styles.factBody}>
        <View accessible accessibilityLabel={spoken ? `${label}: ${spoken}` : label}>
          <AppText variant="meta" color={Colors.muted}>
            {label}
          </AppText>
          {value ? <AppText variant="bodyLg">{value}</AppText> : null}
        </View>
        {children}
      </View>
    </View>
  );
}

export interface SectionProps {
  title: string;
  children: ReactNode;
  /** Sin separador superior (primera sección). */
  first?: boolean;
  /** Elemento a la derecha del titular. */
  accessory?: ReactNode;
  style?: StyleProp<ViewStyle>;
}

export function Section({ title, children, first, accessory, style }: SectionProps) {
  return (
    <View style={[styles.section, first && styles.sectionFirst, style]}>
      <View style={styles.sectionHead}>
        <AppText variant="title3" accessibilityRole="header" style={styles.sectionTitle}>
          {title}
        </AppText>
        {accessory}
      </View>
      {children}
    </View>
  );
}

const COLLAPSED_LINES = 6;

export interface CollapsibleTextProps {
  text: string | null | undefined;
  /** Para la etiqueta del botón: "Leer más de {label}". */
  label?: string;
  lines?: number;
}

/** Texto largo que se abre con "Leer más" si no cabe. */
export function CollapsibleText({ text, label, lines = COLLAPSED_LINES }: CollapsibleTextProps) {
  const [open, setOpen] = useState(false);
  const clean = (text ?? '').trim();
  if (!clean) return null;
  const long = clean.length > 360 || clean.split('\n').length > lines;
  const suffix = label ? ` de ${label}` : '';
  const english = looksEnglish(clean);

  return (
    <View style={styles.collapsible}>
      {english ? (
        <AppText variant="caption" color={Colors.muted}>
          Texto original en inglés
        </AppText>
      ) : null}
      <AppText
        variant="body"
        color={Colors.ink2}
        numberOfLines={long && !open ? lines : undefined}
        accessibilityLanguage={english ? 'en' : undefined}
        selectable>
        {clean}
      </AppText>
      {long ? (
        <Pressable
          onPress={() => setOpen((v) => !v)}
          accessibilityRole="button"
          accessibilityLabel={open ? `Mostrar menos${suffix}` : `Leer más${suffix}`}
          accessibilityState={{ expanded: open }}
          style={({ pressed }) => [styles.more, pressed && styles.morePressed]}>
          <AppText variant="label" color={Colors.clayText}>
            {open ? 'Mostrar menos' : 'Leer más'}
          </AppText>
          <Icon name={open ? 'chevronUp' : 'chevronDown'} size={14} color={Colors.clayText} />
        </Pressable>
      ) : null}
    </View>
  );
}

/** Sección con titular y texto plegable. No pinta nada si no hay texto. */
export function TextSection({ title, text, first }: { title: string; text: string | null | undefined; first?: boolean }) {
  if (!(text ?? '').trim()) return null;
  return (
    <Section title={title} first={first}>
      <CollapsibleText text={text} label={title} />
    </Section>
  );
}

const styles = StyleSheet.create({
  fact: { flexDirection: 'row', gap: Spacing.ms, paddingVertical: Spacing.ms },
  factIcon: { width: 24, alignItems: 'center', paddingTop: 2 },
  factBody: { flex: 1, gap: Spacing.sm },
  section: {
    paddingVertical: Spacing.ml,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.rule,
    gap: Spacing.sm,
  },
  sectionFirst: { borderTopWidth: 0, paddingTop: Spacing.sm },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  sectionTitle: { flex: 1 },
  collapsible: { gap: Spacing.xs },
  more: {
    minHeight: MIN_TOUCH,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    alignSelf: 'flex-start',
    paddingRight: Spacing.sm,
  },
  morePressed: { opacity: 0.6 },
});
