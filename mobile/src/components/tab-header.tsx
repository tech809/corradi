/**
 * Cabecera de pestaña (las NativeTabs no tienen barra de título).
 *
 *   const titleRef = useRef<HostInstance>(null);
 *   <TabHeader ref={titleRef} eyebrow="Erasmus+ desde España" title="Explorar" subtitle="220 proyectos" right={<IconButton …/>} />
 *   useEffect(() => focusOn(titleRef), []);   // src/lib/a11y.ts
 *
 * El título es `header` para el lector; `ref` apunta al título (para mover el foco).
 */
import type { ReactNode, Ref } from 'react';
import { StyleSheet, View, type HostInstance, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, Spacing } from '@/constants/theme';

import { AppText } from './text';

export interface TabHeaderProps {
  title: string;
  eyebrow?: string | null;
  subtitle?: string | null;
  /** Accesorio a la derecha del título (p. ej. un IconButton). */
  right?: ReactNode;
  /** Contenido extra debajo (buscador, chips…). */
  children?: ReactNode;
  /** Ref al título (React 19: `ref` es una prop normal). */
  ref?: Ref<HostInstance>;
  style?: StyleProp<ViewStyle>;
}

export function TabHeader({ title, eyebrow, subtitle, right, children, ref, style }: TabHeaderProps) {
  return (
    <View style={[styles.wrap, style]}>
      {eyebrow ? (
        <AppText variant="eyebrow" color={Colors.clayText}>
          {eyebrow}
        </AppText>
      ) : null}
      <View style={styles.titleRow}>
        <AppText ref={ref} variant="title1" accessibilityRole="header" style={styles.title}>
          {title}
        </AppText>
        {right ? <View style={styles.right}>{right}</View> : null}
      </View>
      {subtitle ? (
        <AppText variant="body" color={Colors.muted}>
          {subtitle}
        </AppText>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingTop: Spacing.md, paddingBottom: Spacing.sm, gap: Spacing.xs },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  title: { flex: 1 },
  right: { flexDirection: 'row', alignItems: 'center' },
});
