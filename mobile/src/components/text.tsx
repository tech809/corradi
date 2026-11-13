/**
 * Texto de la app con la escala tipográfica del tema. Úsalo en lugar de <Text> de RN.
 *
 *   <AppText variant="title1" accessibilityRole="header">Explorar</AppText>
 *   <AppText variant="meta" color={Colors.muted}>Cierra en 3 días</AppText>
 *
 * - El escalado de fuente del sistema está permitido (no lo desactives).
 * - No uses `numberOfLines` en texto esencial salvo listas compactas: a tamaños grandes se corta.
 * - No pases `fontWeight`: el peso está en la familia (Android no combina bien ambos).
 */
import type { Ref } from 'react';
import { Text, type HostInstance, type TextProps, type TextStyle } from 'react-native';

import { Colors, Fonts, Typography, type TypographyVariant } from '@/constants/theme';

export { Fonts };

export interface AppTextProps extends TextProps {
  /** Estilo de la escala. Por defecto 'body'. */
  variant?: TypographyVariant;
  /** Color del texto. Por defecto Colors.ink. */
  color?: string;
  align?: TextStyle['textAlign'];
  ref?: Ref<HostInstance>;
}

export function AppText({ variant = 'body', color = Colors.ink, align, style, ref, ...rest }: AppTextProps) {
  return (
    <Text
      ref={ref}
      {...rest}
      style={[Typography[variant], { color }, align ? { textAlign: align } : null, style]}
    />
  );
}
