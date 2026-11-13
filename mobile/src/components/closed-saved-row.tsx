import { memo, useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Colors, MIN_TOUCH, Radius, Spacing } from '@/constants/theme';
import { fetchOpportunity } from '@/lib/api';
import { cleanTitle, placeLabel } from '@/lib/format';
import type { Opportunity } from '@/lib/types';

import { IconButton } from './icon-button';
import { ClosedTag } from './tags';
import { AppText } from './text';

interface Props {
  identifier: string;
  /** Ficha guardada (savedRecords). Si está, no se pide nada a la red. */
  record?: Opportunity;
  /** Callbacks estables: reciben el identificador. */
  onOpen: (identifier: string) => void;
  onRemove: (identifier: string) => void;
}

/** Proyecto guardado que ya no está abierto. Se pinta con la ficha guardada (sin conexión). */
export const ClosedSavedRow = memo(function ClosedSavedRow({ identifier, record, onOpen, onRemove }: Props) {
  const [fetchedTitle, setFetchedTitle] = useState<string | null>(null);

  // Solo para guardados antiguos sin ficha guardada.
  useEffect(() => {
    if (record) return;
    let alive = true;
    fetchOpportunity(identifier)
      .then((o) => alive && setFetchedTitle(o.title))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [identifier, record]);

  const rawTitle = record?.title ?? fetchedTitle;
  const title = rawTitle ? cleanTitle(rawTitle) || rawTitle : 'Proyecto guardado';
  const place = record ? placeLabel(record) : null;

  return (
    <View style={styles.row}>
      <Pressable
        onPress={() => onOpen(identifier)}
        style={({ pressed }) => [styles.main, pressed && styles.pressed]}
        accessibilityRole="button"
        accessibilityLabel={[title, place, 'Ya no está abierto'].filter(Boolean).join('. ')}
        accessibilityHint="Abre la ficha">
        <ClosedTag />
        <AppText variant="cardTitle" color={Colors.ink2}>
          {title}
        </AppText>
        {place ? (
          <AppText variant="meta" color={Colors.muted}>
            {place}
          </AppText>
        ) : null}
        <AppText variant="meta" color={Colors.muted}>
          Ya no está abierto
        </AppText>
      </Pressable>
      <IconButton
        icon="trash"
        color={Colors.muted}
        onPress={() => onRemove(identifier)}
        accessibilityLabel={`Quitar de guardados: ${title}`}
      />
    </View>
  );
});

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingLeft: Spacing.md,
    paddingRight: Spacing.xs,
    paddingVertical: Spacing.ms,
    borderRadius: Radius.card,
    backgroundColor: Colors.paper2,
  },
  main: { flex: 1, gap: Spacing.xs2, minHeight: MIN_TOUCH },
  pressed: { opacity: 0.7 },
});
