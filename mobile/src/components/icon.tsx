import { SymbolView } from 'expo-symbols';
import { useWindowDimensions, type StyleProp, type ViewStyle } from 'react-native';

import { Colors, Sizes } from '@/constants/theme';

/**
 * Iconos de la app: SF Symbols en iOS y Material Symbols en Android (nombres comprobados contra
 * los tipos de expo-symbols de SDK 58). Siempre decorativos: oculto al lector de pantalla; el
 * significado lo da el texto o la accessibilityLabel del control que lo contiene.
 *
 * Crecen con el tamaño de letra del sistema (como el texto que acompañan), con tope 1.5×.
 * `allowFontScaling={false}` lo desactiva (iconos dentro de piezas de tamaño fijo).
 */
const ICONS = {
  bookmark: { ios: 'bookmark', android: 'bookmark' },
  bookmarkFill: { ios: 'bookmark.fill', android: 'bookmark_added' },
  bell: { ios: 'bell', android: 'notifications' },
  bellFill: { ios: 'bell.fill', android: 'notifications_active' },
  share: { ios: 'square.and.arrow.up', android: 'share' },
  search: { ios: 'magnifyingglass', android: 'search' },
  clear: { ios: 'xmark.circle.fill', android: 'cancel' },
  calendar: { ios: 'calendar', android: 'calendar_month' },
  place: { ios: 'mappin.and.ellipse', android: 'location_on' },
  people: { ios: 'person.2', android: 'group' },
  clock: { ios: 'clock', android: 'schedule' },
  hourglass: { ios: 'hourglass', android: 'hourglass_top' },
  offline: { ios: 'wifi.slash', android: 'wifi_off' },
  check: { ios: 'checkmark', android: 'check' },
  arrowRight: { ios: 'arrow.right', android: 'arrow_forward' },
  doc: { ios: 'doc.text', android: 'description' },
  external: { ios: 'arrow.up.right.square', android: 'open_in_new' },
  bolt: { ios: 'bolt.fill', android: 'bolt' },
  chevronDown: { ios: 'chevron.down', android: 'expand_more' },
  chevronUp: { ios: 'chevron.up', android: 'expand_less' },
  sort: { ios: 'arrow.up.arrow.down', android: 'swap_vert' },
  explore: { ios: 'safari', android: 'explore' },
  trash: { ios: 'trash', android: 'delete' },
  euro: { ios: 'eurosign.circle', android: 'euro' },
  organiser: { ios: 'building.2', android: 'apartment' },
  info: { ios: 'info.circle', android: 'info' },
  map: { ios: 'map', android: 'map' },
  list: { ios: 'list.bullet', android: 'format_list_bulleted' },
  close: { ios: 'xmark', android: 'close' },
  chevronRight: { ios: 'chevron.right', android: 'chevron_right' },
  globe: { ios: 'globe.europe.africa', android: 'public' },
  eye: { ios: 'eye', android: 'visibility' },
  checkCircle: { ios: 'checkmark.circle.fill', android: 'check_circle' },
  undo: { ios: 'arrow.uturn.backward', android: 'undo' },
  help: { ios: 'questionmark.circle', android: 'help' },
} as const;

export type IconName = keyof typeof ICONS;

interface Props {
  name: IconName;
  size?: number;
  color?: string;
  /** Escala con la letra del sistema (tope `Sizes.iconMaxScale`). Por defecto sí. */
  allowFontScaling?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function Icon({ name, size = 20, color = Colors.ink, allowFontScaling = true, style }: Props) {
  const { fontScale } = useWindowDimensions();
  const scale = allowFontScaling ? Math.min(fontScale, Sizes.iconMaxScale) : 1;
  return (
    <SymbolView
      name={ICONS[name]}
      size={Math.round(size * scale)}
      tintColor={color}
      style={style}
      accessibilityElementsHidden
      importantForAccessibility="no"
    />
  );
}
