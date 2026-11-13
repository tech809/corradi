/**
 * Sistema de diseño de Corradi (paleta de la web "Atlas": app/api/static/atlas-theme.css).
 * La app va solo en modo claro, como la web.
 *
 * Reglas de uso (contraste comprobado con WCAG 2.2, ver el informe de la pasada de calidad):
 * - Texto sobre fondos claros (paper, paper2, surface): ink, ink2, muted o clayText. Nunca `clay`
 *   para texto: `clay` es solo para rellenos (botón principal, etiqueta "Última llamada").
 * - Bordes de controles (inputs, chips sin seleccionar, interruptores): controlBorder (≥3:1).
 *   `rule` es solo para separadores decorativos.
 * - Colores por tipo de proyecto: SIEMPRE `TypeColors` / `typeColor()` (chips, portadas, mapa).
 * - Tipografía: usa `Typography` (o el componente `AppText`). En Android no combines
 *   `fontWeight` con una familia propia: usa la familia del peso (Fonts.sansSemiBold…).
 */
import { Platform, type TextStyle, type ViewStyle } from 'react-native';

import type { OpportunityType } from '@/lib/types';

// ---------- Color ----------

export const Colors = {
  paper: '#f7f0e2', // fondo principal
  paper2: '#ebe1d0', // fondos hundidos, etiquetas neutras
  surface: '#fffaf1', // tarjetas
  ink: '#263528', // texto principal y marca
  ink2: '#364c3b', // texto secundario fuerte
  inkDeep: '#1b281e', // fondos oscuros (texto paper encima: 13.5:1)
  muted: '#585f56', // texto secundario (≥5:1 sobre paper/surface, 5.1:1 sobre paper2)
  clay: '#ad573e', // relleno de acción / urgencia (texto blanco encima: 5:1)
  clayText: '#9c4d37', // texto color arcilla sobre fondos claros (≥4.6:1)
  clayDark: '#89422d', // estado pulsado de rellenos clay
  sage: '#dce1ca',
  peach: '#e7bb9d',
  rule: '#d3c9b8', // separadores decorativos (NO bordes de controles)
  controlBorder: '#857b6a', // bordes de controles (≥3:1 sobre paper, paper2 y surface)
  overlay: 'rgba(38,53,40,0.35)', // velo de modales/hojas
  white: '#ffffff',
  /** Texto e iconos encima de una foto (siempre sobre `scrim`/`photoButtonBg`). */
  onPhoto: '#ffffff',
  /**
   * Fondo de botones redondos encima de una foto. Icono `onPhoto` encima: 3.6:1 en el peor caso
   * (foto blanca pura), suficiente para iconos (≥3:1, WCAG 1.4.11) pero NO para texto: para texto
   * sobre foto usa `PHOTO_SCRIM_GRADIENT` o `photoPillBg`.
   */
  photoButtonBg: 'rgba(27,40,30,0.55)',
  /** Píldora sólida para texto encima de una foto (texto `onPhoto` encima ≥5:1 sobre blanco puro). */
  photoPillBg: 'rgba(27,40,30,0.7)',
  /** Velo oscuro sobre fotos (barra de estado, píldoras). */
  scrim: 'rgba(0,0,0,0.22)',
  /** Velo claro de estados pulsados sobre fondos oscuros (toast). */
  overlayLight: 'rgba(255,255,255,0.12)',
  /** Fondo crema translúcido para etiquetas encima de una portada (texto ≥6:1 sobre cualquier foto). */
  overlayTag: 'rgba(255,250,241,0.92)',
  danger: '#b3261e',
  // Mapa base (opcional: src/components/opportunity-map.tsx puede usarlos o definir los suyos).
  /** Tierra. */
  mapLand: '#f7f0e2',
  /** Usos del suelo y edificios. */
  mapLand2: '#ebe1d0',
  /** Parques y zonas verdes. */
  mapPark: '#dce1ca',
  /** Agua (mar, lagos). */
  mapWater: '#d9e2de',
  /** Ríos y canales. */
  mapWaterway: '#c4d2cc',
  /** Contorno de edificios. */
  mapBuildingOutline: '#ddd1bd',
} as const;

/**
 * Degradado inferior de las portadas con foto (CSS `backgroundImage`, RN ≥0.76 con la nueva
 * arquitectura). Desde el 25 % del alto el velo es ≥0.66 de inkDeep (texto blanco encima 5.0:1
 * incluso sobre una foto blanca pura) y desde el 60 %, 0.82 (8.6:1). Así el texto de la portada
 * sigue ≥4.5:1 aunque crezca hacia arriba con la letra grande (tope 1.6× en la portada).
 * El 0–25 % superior queda casi limpio: ahí solo va la etiqueta de tipo, que lleva su propio fondo.
 */
export const PHOTO_SCRIM_GRADIENT =
  'linear-gradient(to bottom, rgba(27,40,30,0) 0%, rgba(27,40,30,0.66) 25%, rgba(27,40,30,0.82) 60%, rgba(27,40,30,0.86) 100%)';

/**
 * Colores por tipo de proyecto. Un único sistema para chips, portadas y mapa.
 * - accent: punto/pin del mapa y leyenda (≥3:1 contra blanco y contra el mapa claro #f2f3f0;
 *   texto blanco encima ≥4.6:1, así que vale para la letra del pin).
 * - chipBg / chipText: etiqueta de tipo (≥6:1; chipText también ≥7:1 sobre surface).
 * - cover: fondo de la portada sin foto (texto blanco ≥6.9:1; blanco al 75 % ≥4.7:1).
 */
export interface TypeColorSet {
  accent: string;
  chipBg: string;
  chipText: string;
  cover: string;
}

export const TypeColors: Record<OpportunityType, TypeColorSet> = {
  YOUTH_EXCHANGE: { accent: '#946414', chipBg: '#f3e3c4', chipText: '#6b4a12', cover: '#7a5212' },
  TRAINING_COURSE: { accent: '#2f5d62', chipBg: '#d6e4e3', chipText: '#1f4246', cover: '#2f5d62' },
  VOLUNTEERING: { accent: '#5f7d43', chipBg: '#e1e9d6', chipText: '#3f5a2b', cover: '#476134' },
};

/** Para proyectos sin tipo (la API puede mandar null). */
export const TypeColorsFallback: TypeColorSet = {
  accent: Colors.ink2,
  chipBg: Colors.paper2,
  chipText: Colors.ink,
  cover: Colors.ink2,
};

/** Letra del tipo para el pin del mapa y la leyenda (no depender solo del color). */
export const TypeGlyphs: Record<OpportunityType, string> = {
  YOUTH_EXCHANGE: 'I',
  TRAINING_COURSE: 'C',
  VOLUNTEERING: 'V',
};

export function typeColor(type: OpportunityType | null | undefined): TypeColorSet {
  return (type && TypeColors[type]) || TypeColorsFallback;
}

export function typeGlyph(type: OpportunityType | null | undefined): string {
  return (type && TypeGlyphs[type]) || '·';
}

// ---------- Tipografía ----------

/**
 * Familias. Los nombres coinciden con los ficheros de assets/fonts (sin extensión) y con lo que
 * carga `useFonts` en src/app/_layout.tsx. La serif es la del sistema (no se descarga nada).
 */
export const Fonts = {
  serif: Platform.select({ ios: 'Georgia', android: 'serif', default: 'Georgia' }),
  sans: 'Manrope-Regular',
  sansMedium: 'Manrope-Medium',
  sansSemiBold: 'Manrope-SemiBold',
  sansBold: 'Manrope-Bold',
  display: 'Sora-SemiBold',
  displayBold: 'Sora-Bold',
} as const;

export type TypographyVariant =
  | 'display'
  | 'title1'
  | 'title2'
  | 'title3'
  | 'cardTitle'
  | 'cardTitleSm'
  | 'bodyLg'
  | 'body'
  | 'label'
  | 'button'
  | 'meta'
  | 'caption'
  | 'eyebrow';

/** Escala tipográfica (tamaño/interlineado en pt). Sin fontWeight: el peso va en la familia. */
export const Typography: Record<TypographyVariant, TextStyle> = {
  // Titulares serif con el tracking de la web (≈ −0.045em en los grandes, algo menos al bajar de
  // tamaño para no apelmazar: −0.04em en cardTitle, −0.024em en cardTitleSm).
  display: { fontFamily: Fonts.serif, fontSize: 44, lineHeight: 46, letterSpacing: -1.5 },
  title1: { fontFamily: Fonts.serif, fontSize: 34, lineHeight: 40, letterSpacing: -1.5 },
  title2: { fontFamily: Fonts.serif, fontSize: 30, lineHeight: 35, letterSpacing: -1.3 },
  title3: { fontFamily: Fonts.serif, fontSize: 22, lineHeight: 28, letterSpacing: -0.9 },
  cardTitle: { fontFamily: Fonts.serif, fontSize: 20, lineHeight: 25, letterSpacing: -0.8 },
  cardTitleSm: { fontFamily: Fonts.serif, fontSize: 17, lineHeight: 22, letterSpacing: -0.4 },
  bodyLg: { fontFamily: Fonts.sans, fontSize: 17, lineHeight: 26 },
  body: { fontFamily: Fonts.sans, fontSize: 15, lineHeight: 22 },
  label: { fontFamily: Fonts.sansSemiBold, fontSize: 14, lineHeight: 18 },
  button: { fontFamily: Fonts.sansSemiBold, fontSize: 16, lineHeight: 21 },
  meta: { fontFamily: Fonts.sansMedium, fontSize: 13, lineHeight: 18 },
  caption: { fontFamily: Fonts.sans, fontSize: 12, lineHeight: 16 },
  eyebrow: {
    fontFamily: Fonts.display,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
};

// ---------- Espaciado, radios, sombras ----------

/** Rejilla de 4 pt. (xs/sm/md/lg/xl conservan sus valores anteriores.) */
export const Spacing = {
  none: 0,
  /** Solo para ajustes finos (huecos entre líneas de una misma pieza). */
  xxs: 2,
  xs: 4,
  /** Hueco entre etiquetas pequeñas e iconos con su texto. */
  xs2: 6,
  sm: 8,
  ms: 12,
  md: 16,
  ml: 20,
  lg: 24,
  xl: 32,
  xxl: 40,
  xxxl: 48,
} as const;

export const Radius = {
  xs: 6,
  sm: 10,
  md: 16,
  lg: 20,
  xl: 28,
  /** Tarjetas de proyecto (OpportunityCard, tarjeta de encaje de la ficha): 10 px, como las de la web. */
  card: 10,
  pill: 999,
} as const;

const SHADOW_INK = '#263528';

/** Borde de las tarjetas: filete `rule` de 1 px, como las tarjetas de la web. */
export const CardBorder = {
  borderWidth: 1,
  borderColor: Colors.rule,
} as const satisfies ViewStyle;

/** Sombras tintadas de tinta. `up` es para barras/hojas pegadas abajo. */
export const Shadows = {
  /** Casi imperceptible: para tarjetas con `CardBorder`. */
  card: {
    shadowColor: SHADOW_INK,
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  sm: {
    shadowColor: SHADOW_INK,
    shadowOpacity: 0.06,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  md: {
    shadowColor: SHADOW_INK,
    shadowOpacity: 0.12,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
  up: {
    shadowColor: SHADOW_INK,
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: -4 },
    elevation: 8,
  },
} as const satisfies Record<string, ViewStyle>;

// ---------- Movimiento ----------

/** Constantes de animación. Respeta siempre `useReduceMotion()` (src/lib/a11y.ts). */
export const Motion = {
  press: { damping: 18, stiffness: 300, scale: 0.98 },
  enter: { duration: 220, stagger: 40 },
  pop: { duration: 220 },
} as const;

/** Área táctil mínima (pt). */
export const MIN_TOUCH = 44;

/** Medidas fijas de piezas repetidas (pt). */
export const Sizes = {
  /** Alto de la portada de una tarjeta. */
  cardCover: 112,
  /** Miniatura cuadrada de las tarjetas compactas. */
  thumb: 56,
  /** Alto mínimo de una etiqueta pulsable (con hitSlop llega a 44). */
  tagMinHeight: 26,
  /** Alto del separador vertical entre grupos de chips. */
  chipDivider: 24,
  /** Tope de escalado de iconos con la letra del sistema. */
  iconMaxScale: 1.5,
} as const;
