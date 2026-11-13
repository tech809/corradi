/**
 * Pressable con un leve "hundido" (escala 0.98 con muelle) al pulsar. Sin animación si el
 * sistema pide reducir movimiento. Base de tarjetas y superficies pulsables grandes.
 *
 * `style` es estático (no función): para estados de pulsado usa `pressedStyle`.
 */
import { useState } from 'react';
import { Pressable, type PressableProps, type StyleProp, type ViewStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';

import { Motion } from '@/constants/theme';
import { useReduceMotion } from '@/lib/a11y';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export interface PressableScaleProps extends Omit<PressableProps, 'style'> {
  style?: StyleProp<ViewStyle>;
  /** Estilo extra mientras está pulsado (p. ej. un fondo un poco más oscuro). */
  pressedStyle?: StyleProp<ViewStyle>;
  /** Escala al pulsar. Por defecto Motion.press.scale (0.98). */
  scaleTo?: number;
}

const SPRING = { damping: Motion.press.damping, stiffness: Motion.press.stiffness };

export function PressableScale({
  style,
  pressedStyle,
  scaleTo = Motion.press.scale,
  onPressIn,
  onPressOut,
  ...rest
}: PressableScaleProps) {
  const reduceMotion = useReduceMotion();
  const scale = useSharedValue(1);
  const [pressed, setPressed] = useState(false);
  const animated = useAnimatedStyle(() => ({ transform: [{ scale: scale.get() }] }));

  return (
    <AnimatedPressable
      {...rest}
      onPressIn={(e) => {
        setPressed(true);
        if (!reduceMotion) scale.set(withSpring(scaleTo, SPRING));
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        setPressed(false);
        if (!reduceMotion) scale.set(withSpring(1, SPRING));
        onPressOut?.(e);
      }}
      style={[style, pressed ? pressedStyle : null, animated]}
    />
  );
}
