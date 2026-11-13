/**
 * Portada de un proyecto. Siempre es una foto: la del proyecto (`image_url`) o, si no tiene, una
 * de la colección de la web elegida con el mismo hash que el mapa web (`coverImageUrl` en
 * format.ts), así la app y la web enseñan la misma foto. Debajo está la portada de marca (color
 * del tipo + marca Corradi): es lo que se ve mientras carga, sin conexión o si la foto falla.
 *
 * Textos encima ('card' y 'hero'): tipo + país abajo a la izquierda. Sobre la foto van sobre un
 * degradado inferior (`PHOTO_SCRIM_GRADIENT`) que garantiza ≥4.5:1 sea cual sea la foto.
 * La portada es decorativa: el lector de pantalla la ignora (el título y el lugar ya se leen).
 *
 *   <Cover o={o} height={112} />                 // banda de tarjeta (enseña el país)
 *   <Cover o={o} height={240} variant="hero" />  // cabecera de la ficha
 *   <Cover o={o} height={56} variant="thumb" />  // miniatura cuadrada (lista del mapa), sin textos
 *
 * `caption={false}` quita los textos (p. ej. si la pantalla ya enseña tipo y país al lado).
 * `showType={false}` quita solo el tipo del texto (cuando hay un <TypeChip> visible encima o al
 * lado: tarjetas, cabecera de la ficha). El país se mantiene.
 * `dimmed` atenúa (opacidad 0.6) SOLO la capa de foto/marca, nunca el degradado ni los textos:
 * es lo que usan las tarjetas "Vistas". Con `dimmed` el degradado se pinta también sin foto,
 * para que el texto siga ≥4.5:1 sobre la marca aclarada.
 * `coverShowsCountry(o, variant)` dice si la portada enseña el país (para no repetirlo debajo).
 */
import { Image } from 'expo-image';
import { useState } from 'react';
import { StyleSheet, Text, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, Fonts, PHOTO_SCRIM_GRADIENT, Radius, Spacing, Typography, typeColor, typeGlyph } from '@/constants/theme';
import { useReduceMotion } from '@/lib/a11y';
import { countryName, coverImageUrl, typeShortLabel } from '@/lib/format';
import type { Opportunity } from '@/lib/types';

const MARK_WHITE = require('@/assets/brand/corradi-mark-white.png'); // copia 1x (1000 px) de corradi-mark-white@5x.png: Metro no resuelve el sufijo @5x

export type CoverVariant = 'card' | 'hero' | 'thumb';

export interface CoverProps {
  /** `title` es opcional: solo se usa para elegir foto si no hay identificador. */
  o: Pick<Opportunity, 'identifier' | 'type' | 'country_code' | 'image_url'> & { title?: string | null };
  height: number;
  /** 'card' (por defecto), 'hero' (textos más grandes) o 'thumb' (cuadrado, sin textos). */
  variant?: CoverVariant;
  /** Tipo + país encima (por defecto sí, salvo en 'thumb'). */
  caption?: boolean;
  /** Enseña el tipo en el texto de la portada (por defecto sí). Apágalo si hay un TypeChip visible. */
  showType?: boolean;
  /** Atenúa solo la foto/marca (opacidad 0.6), p. ej. en proyectos ya vistos. Los textos no. */
  dimmed?: boolean;
  style?: StyleProp<ViewStyle>;
}

/** Opacidad de la capa de foto/marca con `dimmed`. */
const DIMMED_OPACITY = 0.6;

/** ¿La portada enseña el nombre del país? (Para que la tarjeta no lo repita en su línea de datos.) */
export function coverShowsCountry(
  o: Pick<Opportunity, 'country_code'>,
  variant: CoverVariant = 'card',
  caption = variant !== 'thumb',
): boolean {
  return caption && variant !== 'thumb' && countryName(o.country_code) != null;
}

/** Hash estable (djb2) del identificador → 3 números en [0, 1) para variar la marca. */
function seeds(id: string): [number, number, number] {
  let h = 5381;
  for (let i = 0; i < id.length; i++) h = ((h << 5) + h + id.charCodeAt(i)) | 0;
  const u = h >>> 0;
  return [(u % 997) / 997, ((u >>> 10) % 991) / 991, ((u >>> 20) % 983) / 983];
}

export function Cover({ o, height, variant = 'card', caption, showType = true, dimmed = false, style }: CoverProps) {
  const reduceMotion = useReduceMotion();
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const [width, setWidth] = useState(0);
  const candidate = coverImageUrl(o);
  const url = candidate !== failedUrl ? candidate : null;
  const thumb = variant === 'thumb';
  const hero = variant === 'hero';
  const showCaption = (caption ?? !thumb) && !thumb;
  const country = countryName(o.country_code);
  const typeText = showType ? typeShortLabel(o.type) : null;
  const hasText = showCaption && (!!typeText || !!country);
  // Degradado: siempre bajo texto sobre foto, y también sobre la marca si está atenuada.
  const scrimmed = hasText && (!!url || dimmed);

  return (
    <View
      style={[styles.box, { height }, thumb && { width: height }, style]}
      onLayout={thumb ? undefined : (e) => setWidth(e.nativeEvent.layout.width)}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants">
      {/* Capa de foto/marca: lo único que se atenúa con `dimmed`. */}
      <View style={[styles.fill, { backgroundColor: typeColor(o.type).cover }, dimmed && styles.dimmed]} pointerEvents="none">
        {/* Portada de marca: visible mientras carga la foto, sin conexión o si falla. Atenuada, sin
            la píldora ISO (perdería contraste; el país ya va en el texto de abajo). */}
        <BrandLayer o={o} height={height} width={width} thumb={thumb} hero={hero} withIso={!url && !thumb && !dimmed} />

        {url ? (
          <Image
            source={{ uri: url }}
            style={StyleSheet.absoluteFill}
            contentFit="cover"
            transition={reduceMotion ? 0 : 200}
            recyclingKey={o.identifier}
            cachePolicy="memory-disk"
            accessible={false}
            accessibilityIgnoresInvertColors
            onError={() => setFailedUrl(url)}
          />
        ) : null}

        {thumb && !url ? (
          <View style={styles.thumbCenter}>
            <Text style={styles.thumbGlyph} allowFontScaling={false}>
              {typeGlyph(o.type)}
            </Text>
          </View>
        ) : null}
      </View>

      {scrimmed ? <View style={styles.scrim} pointerEvents="none" /> : null}

      {hasText ? (
        <View
          style={[
            styles.caption,
            {
              left: hero ? Spacing.ml : Spacing.md,
              right: hero ? Spacing.ml : Spacing.md,
              bottom: hero ? Spacing.ml : Spacing.ms,
              // Sin foto, el texto no pisa la marca (mitad derecha).
              maxWidth: !url && width > 0 ? width * 0.6 : undefined,
            },
          ]}>
          {typeText ? (
            <Text style={[Typography.eyebrow, styles.eyebrow, !scrimmed && styles.eyebrowOnBrand]} maxFontSizeMultiplier={1.6}>
              {typeText}
            </Text>
          ) : null}
          {country ? (
            <Text style={[hero ? Typography.title2 : Typography.title3, styles.country]} maxFontSizeMultiplier={1.4}>
              {country}
            </Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

/** Color del tipo + marca Corradi girada (y la píldora ISO del país si no hay foto). */
function BrandLayer({
  o,
  height,
  width,
  thumb,
  hero,
  withIso,
}: {
  o: CoverProps['o'];
  height: number;
  width: number;
  thumb: boolean;
  hero: boolean;
  withIso: boolean;
}) {
  const [r1, r2, r3] = seeds(o.identifier || 'corradi');
  const country = countryName(o.country_code);
  const iso = country ? (o.country_code ?? '').trim().toUpperCase() : null;

  // La marca vive en la mitad derecha para no quedar detrás de los textos (contraste comprobado).
  const markSize = thumb ? height * 0.9 : Math.min(height * 1.3, width * 0.46);
  const markStyle: ImageStyle = thumb
    ? { width: markSize, height: markSize, left: height * 0.05, top: height * 0.05, transform: [{ rotate: `${(r3 - 0.5) * 30}deg` }] }
    : {
        width: markSize,
        height: markSize,
        right: -markSize * (0.1 + 0.15 * r1),
        top: (height - markSize) / 2 + (r2 - 0.5) * height * 0.5,
        transform: [{ rotate: `${(r3 - 0.5) * 36}deg` }],
      };

  return (
    <>
      {thumb || width > 0 ? (
        <Image source={MARK_WHITE} style={[styles.mark, markStyle]} contentFit="contain" accessible={false} />
      ) : null}
      {withIso && iso ? (
        <View style={[styles.isoPill, { top: hero ? Spacing.md : Spacing.ms, right: hero ? Spacing.md : Spacing.ms }]}>
          <Text style={styles.isoText} maxFontSizeMultiplier={1.6}>
            {iso}
          </Text>
        </View>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  box: { width: '100%', overflow: 'hidden' },
  fill: { ...StyleSheet.absoluteFill },
  dimmed: { opacity: DIMMED_OPACITY },
  mark: { position: 'absolute', opacity: 0.1 },
  scrim: { ...StyleSheet.absoluteFill, backgroundImage: PHOTO_SCRIM_GRADIENT },
  caption: { position: 'absolute', gap: Spacing.xxs },
  eyebrow: { color: Colors.onPhoto },
  // Sobre el color del tipo (sin foto) el blanco al 75 % sigue ≥4.7:1.
  eyebrowOnBrand: { opacity: 0.75 },
  country: { color: Colors.onPhoto },
  isoPill: {
    position: 'absolute',
    backgroundColor: Colors.scrim,
    borderRadius: Radius.pill,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xxs,
  },
  isoText: { ...Typography.eyebrow, letterSpacing: 1, color: Colors.white },
  thumbCenter: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, alignItems: 'center', justifyContent: 'center' },
  thumbGlyph: { fontFamily: Fonts.displayBold, fontSize: 20, lineHeight: 24, color: Colors.white },
});
