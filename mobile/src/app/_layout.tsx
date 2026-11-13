import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';

import { ToastHost } from '@/components/toast';
import { Colors } from '@/constants/theme';
import { useNotificationRouting } from '@/lib/notification-routing';
import { OpportunitiesProvider } from '@/state/opportunities';

SplashScreen.preventAutoHideAsync();

/**
 * Un enlace profundo (corradi://proyecto/…, enlace web o notificación) que abre directamente
 * una ficha deja las pestañas debajo: así "atrás" vuelve a la app en lugar de cerrarla.
 * (Expo Router SDK 58: `anchor` sustituye a `initialRouteName`.)
 */
export const unstable_settings = { anchor: '(tabs)' };

/**
 * Fuentes de la marca. En las builds ya van incrustadas (plugin expo-font en app.config.ts);
 * `useFonts` las carga también en Expo Go. Los nombres = fichero sin extensión (ver Fonts).
 */
const FONT_MAP = {
  'Manrope-Regular': require('@/assets/fonts/Manrope-Regular.ttf'),
  'Manrope-Medium': require('@/assets/fonts/Manrope-Medium.ttf'),
  'Manrope-SemiBold': require('@/assets/fonts/Manrope-SemiBold.ttf'),
  'Manrope-Bold': require('@/assets/fonts/Manrope-Bold.ttf'),
  'Sora-SemiBold': require('@/assets/fonts/Sora-SemiBold.ttf'),
  'Sora-Bold': require('@/assets/fonts/Sora-Bold.ttf'),
};

/** Máximo que esperamos a las fuentes antes de seguir con las del sistema. */
const FONT_TIMEOUT_MS = 4000;

/** Navegación por notificaciones y bienvenida: va dentro del árbol, una vez montado el Stack. */
function NotificationRouting() {
  useNotificationRouting();
  return null;
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(FONT_MAP);
  const [timedOut, setTimedOut] = useState(false);
  // Si fallan o tardan, seguimos con las del sistema: nunca bloquear la app en la pantalla de carga.
  const ready = fontsLoaded || !!fontError || timedOut;

  useEffect(() => {
    const id = setTimeout(() => setTimedOut(true), FONT_TIMEOUT_MS);
    return () => clearTimeout(id);
  }, []);

  useEffect(() => {
    if (ready) SplashScreen.hideAsync();
  }, [ready]);

  if (!ready) return null;

  return (
    <OpportunitiesProvider>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerTintColor: Colors.ink,
          headerStyle: { backgroundColor: Colors.paper },
          contentStyle: { backgroundColor: Colors.paper },
          headerBackButtonDisplayMode: 'minimal',
        }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="proyecto/[id]" options={{ title: '' }} />
        <Stack.Screen name="+not-found" options={{ title: '' }} />
        {/* Pantalla completa: la bienvenida no se descarta deslizando (hay que elegir). */}
        <Stack.Screen name="bienvenida" options={{ presentation: 'fullScreenModal', headerShown: false, gestureEnabled: false }} />
      </Stack>
      <ToastHost />
      <NotificationRouting />
    </OpportunitiesProvider>
  );
}
