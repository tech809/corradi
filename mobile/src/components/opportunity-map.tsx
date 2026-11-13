/**
 * Mapa nativo con MapLibre + teselas de OpenFreeMap: sin clave, sin cuenta y sin coste.
 * Los proyectos van en una sola fuente GeoJSON con agrupación (clusters), que es lo que
 * MapLibre pinta más rápido. Este módulo carga código nativo: NO importarlo en Expo Go
 * (ver src/app/(tabs)/mapa.tsx).
 *
 * - Estilo: el *positron* de OpenFreeMap, descargado una vez y recoloreado a la marca (papel,
 *   salvia, agua verdosa) con los nombres en español (`name:es` de OpenMapTiles). Se guarda en la
 *   caché del móvil; si no hay copia y la descarga falla, se usa la URL tal cual.
 * - Punto relleno con la letra del tipo en blanco = ubicación exacta; anillo con la letra en el
 *   color del tipo = solo se sabe el país. Colores de `TypeColors` (theme.ts).
 * - `ref.flyTo([lng, lat], zoom)` mueve la cámara (lo usa el parámetro `focus` de la pantalla).
 *   Si el mapa aún no ha cargado (o falló), el vuelo queda pendiente hasta que cargue.
 * - `ref.resetView()` vuelve a la vista inicial (toda Europa): alternativa a pellizcar.
 * - Con "reducir movimiento" la cámara salta sin animación.
 * - La atribución a OpenStreetMap/OpenFreeMap se queda visible y tocable (lo exige su licencia):
 *   arriba a la derecha, justo debajo de los controles (`topInset`), lejos de la barra de
 *   pestañas y de la tarjeta del proyecto seleccionado.
 */
import {
  Camera,
  GeoJSONSource,
  Layer,
  Map,
  type CameraRef,
  type GeoJSONSourceRef,
  type LngLat,
  type PressEventWithFeatures,
} from '@maplibre/maplibre-react-native';
import type { ExpressionSpecification, LayerSpecification, StyleSpecification } from '@maplibre/maplibre-gl-style-spec';
import { File, Paths } from 'expo-file-system';
import { useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from 'react';
import { StyleSheet, View, useWindowDimensions, type NativeSyntheticEvent } from 'react-native';

import { Colors, typeColor, typeGlyph } from '@/constants/theme';
import type { Opportunity } from '@/lib/types';

// ---------------------------------------------------------------------------
// Estilo de marca

/** Estilo claro y sobrio de OpenFreeMap. Sus glifos incluyen Noto Sans Regular/Bold/Italic. */
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';
const STYLE_CACHE_FILE = 'openfreemap-positron.json';
const STYLE_FETCH_TIMEOUT_MS = 5000;
const FONT_BOLD = ['Noto Sans Bold'];

/** Colores del mapa base (tokens `Colors.map*` de theme.ts: papel, salvia y un agua verdosa apagada). */
const MAP_COLORS = {
  land: Colors.mapLand,
  landuse: Colors.mapLand2,
  green: Colors.mapPark,
  water: Colors.mapWater,
  waterway: Colors.mapWaterway,
  building: Colors.mapLand2,
  buildingOutline: Colors.mapBuildingOutline,
  halo: Colors.mapLand,
};

/** Pines y grupos: colores fijos (los del tipo salen de `typeColor`). */
const PIN_COLORS = {
  cluster: Colors.ink,
  clusterText: Colors.paper,
  clusterStroke: Colors.paper,
  /** Relleno del anillo (ubicación aproximada) y borde/letra del punto relleno. */
  contrast: Colors.white,
};

/** Medidas de pines y grupos a tamaño de letra 1 (crecen con `textScale`). */
const PIN = {
  clusterRadius: { small: 16, medium: 20, large: 26 },
  /** Número de proyectos a partir del cual el grupo es mediano / grande. */
  clusterSteps: { medium: 10, large: 30 },
  clusterStroke: 3,
  clusterText: 13,
  radius: 10,
  radiusSelected: 13,
  haloRadius: 20,
  haloOpacity: 0.25,
  strokeExact: 1.5,
  strokeApprox: 2.5,
  glyph: 11,
  glyphSelected: 14,
} as const;

/** Agrupación de la fuente GeoJSON y margen de toque alrededor de cada pin (pt). */
const CLUSTER = { radius: 42, maxZoom: 7 } as const;
const HITBOX = 12;

/** Márgenes de la cámara y de la atribución (pt). */
const CAMERA_EDGE = 16;
const ATTRIBUTION_OFFSET = { top: 4, right: 8 } as const;

/** Duración de las animaciones de cámara (ms; 0 con "reducir movimiento"). */
const DURATION = { fly: 900, ease: 450, reset: 700 } as const;
/** Zooms: límites, por defecto de `flyTo` y de respaldo al abrir un grupo. */
const ZOOM = { min: 2, max: 14, flyDefault: 8, clusterFallback: 6, clusterExtra: 0.5, clusterBase: 5 } as const;

/**
 * Nombres en español si los hay. Las teselas de OpenFreeMap (esquema OpenMapTiles) traen
 * `name:es`, `name:latin` (transliteración) y `name` (local); comprobado en el TileJSON de
 * https://tiles.openfreemap.org/planet (capas place, water_name, transportation_name…).
 */
const NAME_ES: ExpressionSpecification = ['coalesce', ['get', 'name:es'], ['get', 'name:latin'], ['get', 'name']];

type Props = Record<string, unknown>;

/** Recolorea el positron y pone los nombres en español. Ids/capas del estilo a 11-2026. */
function brandStyle(style: StyleSpecification): StyleSpecification {
  const layers = style.layers.map((layer): LayerSpecification => {
    const src = layer as LayerSpecification & { paint?: Props; layout?: Props; 'source-layer'?: string };
    const paint: Props = { ...(src.paint ?? {}) };
    const layout: Props = { ...(src.layout ?? {}) };
    const sourceLayer = src['source-layer'];

    if (layer.type === 'background') paint['background-color'] = MAP_COLORS.land;
    if (layer.type === 'fill') {
      if (sourceLayer === 'water') paint['fill-color'] = MAP_COLORS.water;
      else if (sourceLayer === 'park' || layer.id === 'landcover_wood' || layer.id === 'landcover_grass')
        paint['fill-color'] = MAP_COLORS.green;
      else if (sourceLayer === 'landuse') paint['fill-color'] = MAP_COLORS.landuse;
      else if (sourceLayer === 'building') {
        paint['fill-color'] = MAP_COLORS.building;
        paint['fill-outline-color'] = MAP_COLORS.buildingOutline;
      } else if (layer.id === 'road_area_pier') paint['fill-color'] = MAP_COLORS.land;
    }
    if (layer.type === 'line') {
      if (sourceLayer === 'waterway') paint['line-color'] = MAP_COLORS.waterway;
      else if (layer.id === 'road_pier') paint['line-color'] = MAP_COLORS.land;
    }
    if (layer.type === 'symbol') {
      // Solo las etiquetas de nombre (las placas de carretera usan `ref`).
      const field = layout['text-field'];
      if (field !== undefined && JSON.stringify(field).includes('"name')) layout['text-field'] = NAME_ES;
      if (paint['text-halo-color'] !== undefined) paint['text-halo-color'] = MAP_COLORS.halo;
    }
    return { ...src, paint, layout } as LayerSpecification;
  });
  return { ...style, layers };
}

function isStyle(x: unknown): x is StyleSpecification {
  const s = x as Partial<StyleSpecification> | null;
  return !!s && s.version === 8 && Array.isArray(s.layers) && typeof s.sources === 'object';
}

/** Estilo ya recoloreado de esta sesión (memoria) y la descarga en curso (una por sesión). */
let memoryStyle: StyleSpecification | null = null;
let download: Promise<StyleSpecification | null> | null = null;

function cacheFile(): File | null {
  try {
    return new File(Paths.cache, STYLE_CACHE_FILE);
  } catch {
    return null;
  }
}

/** Copia guardada en disco (sin recolorear: así un cambio de colores en la app se aplica siempre). */
function readCachedStyle(): StyleSpecification | null {
  if (memoryStyle) return memoryStyle;
  try {
    const file = cacheFile();
    if (!file?.exists) return null;
    const raw: unknown = JSON.parse(file.textSync());
    if (!isStyle(raw)) return null;
    memoryStyle = brandStyle(raw);
    return memoryStyle;
  } catch {
    return null;
  }
}

async function downloadStyle(): Promise<StyleSpecification | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), STYLE_FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(STYLE_URL, { signal: controller.signal });
    if (!res.ok) return null;
    const text = await res.text();
    const raw: unknown = JSON.parse(text);
    if (!isStyle(raw)) return null;
    try {
      // `write` es asíncrono: un fallo (disco lleno, permisos) no debe quedar sin capturar.
      const file = cacheFile();
      if (file) void file.write(text).catch(() => {});
    } catch {
      // sin caché: se descargará la próxima vez
    }
    return raw;
  } catch {
    return null; // sin red o respuesta rara
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Estilo a pasar a `<Map mapStyle>`: null mientras se descarga la primera vez (máx. 5 s).
 * Con copia en caché se usa al momento y se refresca en segundo plano para la próxima apertura
 * (no se cambia el estilo con el mapa ya pintado: lo recargaría entero). Si la descarga falla
 * se usa la URL tal cual (sin recolorear) y se reintentará en el siguiente montaje.
 */
function useMapStyle(): StyleSpecification | string | null {
  const [style, setStyle] = useState<StyleSpecification | string | null>(readCachedStyle);
  useEffect(() => {
    download ??= downloadStyle().then((raw) => {
      if (raw) memoryStyle = brandStyle(raw);
      else download = null;
      return raw ? memoryStyle : null;
    });
    let cancelled = false;
    void download.then((branded) => {
      if (!cancelled) setStyle((prev) => prev ?? branded ?? STYLE_URL);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return style;
}

// ---------------------------------------------------------------------------
// Mapa

/** Europa entera, con España y Canarias a la vista. */
const EUROPE_BOUNDS: [number, number, number, number] = [-19, 27, 42, 71];

/** Tamaño máximo de letra que seguimos al sistema dentro del mapa (los círculos no crecen más). */
const MAX_FONT_SCALE = 1.6;

const IS_CLUSTER: ExpressionSpecification = ['has', 'point_count'];
const IS_POINT: ExpressionSpecification = ['!', ['has', 'point_count']];

/** Margen de la cámara: lo que tapan los controles de arriba y la barra de pestañas de abajo. */
function cameraPadding(top: number, bottom: number) {
  return { top, bottom: bottom + CAMERA_EDGE, left: CAMERA_EDGE, right: CAMERA_EDGE };
}

export type LocatedOpportunity = Opportunity & { latitude: number; longitude: number };

export interface OpportunityMapHandle {
  /** Centra la cámara en `lngLat` (con animación salvo "reducir movimiento"). */
  flyTo: (lngLat: LngLat, zoom?: number) => void;
  /** Vuelve a la vista inicial (toda Europa). */
  resetView: () => void;
}

export interface OpportunityMapProps {
  points: LocatedOpportunity[];
  selectedId: string | null;
  onSelect: (identifier: string | null) => void;
  reduceMotion?: boolean;
  /** Alto de lo que tapa el mapa por arriba (controles medidos con onLayout). */
  topInset: number;
  /** Lo que tapa el mapa por abajo (barra de pestañas): margen inferior de la cámara. */
  bottomInset: number;
  /** El estilo del mapa no se pudo cargar (sin red, servidor caído). */
  onLoadError?: () => void;
  /** El mapa ha cargado (también tras un fallo anterior). */
  onLoad?: () => void;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  ref?: Ref<OpportunityMapHandle>;
}

export function OpportunityMap({
  points,
  selectedId,
  onSelect,
  reduceMotion = false,
  topInset,
  bottomInset,
  onLoadError,
  onLoad,
  accessibilityLabel,
  accessibilityHint,
  ref,
}: OpportunityMapProps) {
  const mapStyle = useMapStyle();
  const camera = useRef<CameraRef>(null);
  const source = useRef<GeoJSONSourceRef>(null);
  // Un flyTo pedido antes de que cargue el mapa se guarda y se aplica al terminar de cargar
  // (si no, la vista inicial lo pisaría). Si la carga falla, sigue pendiente.
  const loaded = useRef(false);
  const pending = useRef<{ center: LngLat; zoom: number } | null>(null);
  // Se recalcula en cada cambio del tamaño de letra del sistema (useWindowDimensions re-renderiza).
  const { fontScale } = useWindowDimensions();
  const textScale = Math.min(Math.max(fontScale, 1), MAX_FONT_SCALE);
  const padding = cameraPadding(topInset, bottomInset);

  useImperativeHandle(
    ref,
    () => ({
      flyTo: (center, zoom = ZOOM.flyDefault) => {
        if (!loaded.current) {
          pending.current = { center, zoom };
          return;
        }
        camera.current?.flyTo({
          center,
          zoom,
          padding: cameraPadding(topInset, bottomInset),
          duration: reduceMotion ? 0 : DURATION.fly,
        });
      },
      resetView: () => {
        // Sin cargar, la vista inicial ya es Europa: basta con olvidar un vuelo pendiente.
        pending.current = null;
        if (!loaded.current) return;
        camera.current?.fitBounds(EUROPE_BOUNDS, {
          padding: cameraPadding(topInset, bottomInset),
          duration: reduceMotion ? 0 : DURATION.reset,
        });
      },
    }),
    [reduceMotion, topInset, bottomInset],
  );

  const data = useMemo<GeoJSON.FeatureCollection>(
    () => ({
      type: 'FeatureCollection',
      features: points.map((o) => ({
        type: 'Feature',
        id: o.identifier,
        geometry: { type: 'Point', coordinates: [o.longitude, o.latitude] },
        properties: {
          id: o.identifier,
          color: typeColor(o.type).accent,
          glyph: typeGlyph(o.type),
          approx: Boolean(o.approx_location),
        },
      })),
    }),
    [points],
  );

  const sel = selectedId ?? '';
  const isSelected: ExpressionSpecification = ['==', ['get', 'id'], sel];
  // Círculos y letras crecen con la letra del sistema (hasta MAX_FONT_SCALE).
  const s = (n: number) => Math.round(n * textScale * 10) / 10;

  const onSourcePress = async (e: NativeSyntheticEvent<PressEventWithFeatures>) => {
    // Que el toque no llegue también al mapa (que cerraría la tarjeta).
    e.stopPropagation();
    const feature = e.nativeEvent.features[0];
    if (!feature || feature.geometry.type !== 'Point') return;
    const props = feature.properties ?? {};
    const center = feature.geometry.coordinates as LngLat;
    const duration = reduceMotion ? 0 : DURATION.ease;
    if (props.cluster) {
      // Toque en un grupo: acercar hasta que se separe.
      try {
        const zoom = await source.current?.getClusterExpansionZoom(Number(props.cluster_id));
        camera.current?.easeTo({ center, zoom: (zoom ?? ZOOM.clusterBase) + ZOOM.clusterExtra, duration });
      } catch {
        camera.current?.easeTo({ center, zoom: ZOOM.clusterFallback, duration });
      }
      return;
    }
    if (typeof props.id === 'string') onSelect(props.id);
  };

  // Primera descarga del estilo (sin caché): fondo papel, como el del mapa.
  if (!mapStyle) return <View style={[StyleSheet.absoluteFill, styles.placeholder]} />;

  return (
    <Map
      style={StyleSheet.absoluteFill}
      mapStyle={mapStyle}
      touchRotate={false}
      touchPitch={false}
      compass={false}
      logo={false}
      attribution
      // Arriba a la derecha, bajo los controles: así no la tapan ni la barra de pestañas ni la
      // tarjeta del proyecto seleccionado (que ocupa todo el ancho abajo).
      attributionPosition={{ top: topInset + ATTRIBUTION_OFFSET.top, right: ATTRIBUTION_OFFSET.right }}
      tintColor={Colors.clayText}
      accessible
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      onDidFinishLoadingMap={() => {
        loaded.current = true;
        onLoad?.();
        const p = pending.current;
        pending.current = null;
        if (p) camera.current?.flyTo({ ...p, padding, duration: reduceMotion ? 0 : DURATION.fly });
      }}
      onDidFailLoadingMap={() => {
        loaded.current = false;
        onLoadError?.();
      }}
      onPress={() => onSelect(null)}>
      <Camera
        ref={camera}
        initialViewState={{ bounds: EUROPE_BOUNDS, padding }}
        minZoom={ZOOM.min}
        maxZoom={ZOOM.max}
      />
      <GeoJSONSource
        id="proyectos"
        ref={source}
        data={data}
        cluster
        clusterRadius={CLUSTER.radius}
        clusterMaxZoom={CLUSTER.maxZoom}
        hitbox={{ top: HITBOX, right: HITBOX, bottom: HITBOX, left: HITBOX }}
        onPress={onSourcePress}>
        {/* Grupos: círculo tinta con borde papel y el número. */}
        <Layer
          id="grupos"
          type="circle"
          filter={IS_CLUSTER}
          paint={{
            'circle-color': PIN_COLORS.cluster,
            'circle-radius': [
              'step',
              ['get', 'point_count'],
              s(PIN.clusterRadius.small),
              PIN.clusterSteps.medium,
              s(PIN.clusterRadius.medium),
              PIN.clusterSteps.large,
              s(PIN.clusterRadius.large),
            ],
            'circle-stroke-width': PIN.clusterStroke,
            'circle-stroke-color': PIN_COLORS.clusterStroke,
          }}
        />
        <Layer
          id="grupos-numero"
          type="symbol"
          filter={IS_CLUSTER}
          layout={{
            'text-field': ['get', 'point_count_abbreviated'],
            'text-font': FONT_BOLD,
            'text-size': s(PIN.clusterText),
            'text-allow-overlap': true,
            'text-ignore-placement': true,
          }}
          paint={{ 'text-color': PIN_COLORS.clusterText }}
        />
        {/* Halo del proyecto seleccionado. */}
        <Layer
          id="proyecto-halo"
          type="circle"
          filter={['all', IS_POINT, isSelected]}
          paint={{
            'circle-radius': s(PIN.haloRadius),
            'circle-color': ['get', 'color'],
            'circle-opacity': PIN.haloOpacity,
          }}
        />
        {/* Proyectos sueltos: relleno = ubicación exacta; anillo = solo el país. */}
        <Layer
          id="proyectos-punto"
          type="circle"
          filter={IS_POINT}
          layout={{ 'circle-sort-key': ['case', isSelected, 1, 0] }}
          paint={{
            'circle-radius': ['case', isSelected, s(PIN.radiusSelected), s(PIN.radius)],
            'circle-color': ['case', ['get', 'approx'], PIN_COLORS.contrast, ['get', 'color']],
            'circle-stroke-color': ['case', ['get', 'approx'], ['get', 'color'], PIN_COLORS.contrast],
            'circle-stroke-width': ['case', ['get', 'approx'], PIN.strokeApprox, PIN.strokeExact],
          }}
        />
        {/* Letra del tipo (no depender solo del color). */}
        <Layer
          id="proyectos-letra"
          type="symbol"
          filter={IS_POINT}
          layout={{
            'text-field': ['get', 'glyph'],
            'text-font': FONT_BOLD,
            'text-size': ['case', isSelected, s(PIN.glyphSelected), s(PIN.glyph)],
            'text-allow-overlap': true,
            'text-ignore-placement': true,
          }}
          paint={{ 'text-color': ['case', ['get', 'approx'], ['get', 'color'], PIN_COLORS.contrast] }}
        />
      </GeoJSONSource>
    </Map>
  );
}

const styles = StyleSheet.create({
  placeholder: { backgroundColor: MAP_COLORS.land },
});
