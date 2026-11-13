/**
 * Como <TextSection> (mismo aspecto), pero con ref al titular para poder llevar ahí el foco del
 * lector de pantalla tras saltar a la sección (p. ej. "Consulta qué está cubierto ↓").
 * <Section> no expone ref del titular, por eso existe esta copia.
 */
import type { Ref } from 'react';
import { StyleSheet, View, type HostInstance, type LayoutChangeEvent } from 'react-native';

import { CollapsibleText } from '@/components/detail-parts';
import { AppText } from '@/components/text';
import { Colors, Spacing } from '@/constants/theme';

export interface AnchorSectionProps {
  title: string;
  text: string | null | undefined;
  titleRef?: Ref<HostInstance>;
  onLayout?: (e: LayoutChangeEvent) => void;
}

export function AnchorSection({ title, text, titleRef, onLayout }: AnchorSectionProps) {
  if (!(text ?? '').trim()) return null;
  return (
    <View style={styles.section} onLayout={onLayout}>
      <AppText ref={titleRef} variant="title3" accessibilityRole="header">
        {title}
      </AppText>
      <CollapsibleText text={text} label={title} />
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    paddingVertical: Spacing.ml,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.rule,
    gap: Spacing.sm,
  },
});
