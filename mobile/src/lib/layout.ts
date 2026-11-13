import { Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

/**
 * Espacio a dejar debajo de un elemento flotante (`position: 'absolute'`, `bottom: …`) DENTRO de
 * una pantalla de pestaña (NativeTabs) para que no lo tape la barra de pestañas: tarjetas del
 * mapa, créditos del mapa, botones flotantes.
 *
 * Por qué es distinto en cada plataforma (leído en el código instalado, SDK 58; PENDIENTE de
 * comprobar en dispositivo):
 * - iOS: el contenido de la pestaña se extiende por DEBAJO de la barra (UITabBarController), y
 *   expo-router envuelve cada pestaña en su propio `SafeAreaProvider`
 *   (node_modules/expo-router/build/native-tabs/NativeTabsView.ios.js, `wrappedContent`). Ese
 *   proveedor mide el `safeAreaInsets` de UIKit de la vista, que ya incluye la barra de pestañas:
 *   `insets.bottom` ≈ 49 + indicador de inicio. Sumar la altura de la barra otra vez la contaría
 *   dos veces.
 * - Android: expo-router envuelve el contenido en el `SafeAreaView` de react-native-screens con
 *   `edges: {bottom: true}` e `insetType: 'all'` (NativeTabsView.android.js), que aplica como
 *   relleno inferior max(alto de la barra inferior, barras del sistema)
 *   (react-native-screens/android/…/safearea/SafeAreaView.kt + TabsContainer.getInterfaceInsets).
 *   El contenido ya termina ENCIMA de la barra: solo hace falta el margen visual.
 *
 * Solo vale dentro de una pestaña: en pantallas del Stack (ficha, bienvenida) usa
 * `useSafeAreaInsets()` directamente.
 */
export function useTabBarClearance(extra = 8): number {
  const insets = useSafeAreaInsets();
  return Platform.OS === 'android' ? extra : insets.bottom + extra;
}
