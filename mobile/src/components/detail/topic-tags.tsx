/**
 * Temas del proyecto bajo el título: etiquetas pequeñas, no pulsables (máx. 4 + "+N").
 * El lector lo lee como un solo elemento: "Temas: inclusión social, sostenibilidad y 2 más".
 */
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/text';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { topicList } from '@/lib/format';

const MAX_TAGS = 4;

function spokenList(items: string[], rest: number): string {
  if (rest > 0) return `${items.join(', ')} y ${rest} más`;
  if (items.length < 2) return items.join('');
  return `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}`;
}

export function TopicTags({ topic }: { topic: string | null | undefined }) {
  const all = topicList(topic);
  if (all.length === 0) return null;
  const shown = all.slice(0, MAX_TAGS);
  const rest = all.length - shown.length;

  return (
    <View style={styles.row} accessible accessibilityLabel={`Temas: ${spokenList(shown, rest)}`}>
      {shown.map((t) => (
        <View key={t} style={styles.tag}>
          <AppText variant="caption" color={Colors.ink2}>
            {t}
          </AppText>
        </View>
      ))}
      {rest > 0 ? (
        <View style={styles.tag}>
          <AppText variant="caption" color={Colors.ink2}>
            +{rest}
          </AppText>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs },
  tag: {
    backgroundColor: Colors.paper2,
    borderRadius: Radius.pill,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xxs,
  },
});
