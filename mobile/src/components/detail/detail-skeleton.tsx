/** Ficha fantasma mientras se carga un proyecto (sin pulso si se reduce movimiento). */
import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { useReduceMotion } from '@/lib/a11y';

export function DetailSkeleton({ heroHeight }: { heroHeight: number }) {
  const reduceMotion = useReduceMotion();
  const opacity = useSharedValue(1);

  useEffect(() => {
    if (reduceMotion) {
      cancelAnimation(opacity);
      opacity.set(1);
      return;
    }
    opacity.set(withRepeat(withTiming(0.5, { duration: 900 }), -1, true));
    return () => cancelAnimation(opacity);
  }, [reduceMotion, opacity]);

  const pulse = useAnimatedStyle(() => ({ opacity: opacity.get() }));

  return (
    <View
      style={styles.screen}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel="Cargando proyecto"
      accessibilityState={{ busy: true }}>
      <Animated.View style={[{ height: heroHeight }, styles.hero, pulse]} />
      <Animated.View style={[styles.body, pulse]}>
        <View style={[styles.bar, { width: 110, height: 24, borderRadius: Radius.pill }]} />
        <View style={[styles.bar, { width: '92%', height: 30 }]} />
        <View style={[styles.bar, { width: '70%', height: 30 }]} />
        <View style={[styles.bar, { width: '45%', height: 14 }]} />
        <View style={styles.card}>
          {[0, 1, 2, 3].map((i) => (
            <View key={i} style={styles.row}>
              <View style={[styles.bar, styles.icon]} />
              <View style={styles.lines}>
                <View style={[styles.bar, { width: '30%', height: 12 }]} />
                <View style={[styles.bar, { width: '80%', height: 16 }]} />
              </View>
            </View>
          ))}
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: Colors.paper },
  hero: { backgroundColor: Colors.paper2 },
  body: { padding: Spacing.md, gap: Spacing.ms },
  bar: { backgroundColor: Colors.paper2, borderRadius: Radius.xs },
  card: {
    marginTop: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    padding: Spacing.md,
    gap: Spacing.md,
  },
  row: { flexDirection: 'row', gap: Spacing.ms, alignItems: 'center' },
  icon: { width: 22, height: 22, borderRadius: 11 },
  lines: { flex: 1, gap: Spacing.sm },
});
