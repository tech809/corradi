import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * Configuración de la app Corradi.
 *
 * Variables de entorno (ver README.md):
 * - EAS_PROJECT_ID: id del proyecto en expo.dev. Hace falta para los avisos push.
 *   PENDIENTE: el propietario crea el proyecto con `npx eas-cli@latest init` y lo define aquí
 *   (o como variable de entorno en EAS). Sin él la app funciona, pero sin resumen diario; por
 *   eso una build `production` (EAS_BUILD_PROFILE, lo pone EAS) sin él FALLA a propósito.
 * - GOOGLE_SERVICES_JSON: ruta al google-services.json (config de Firebase que Android necesita
 *   para recibir push, FCM). En EAS es una variable de entorno de tipo "file". En local vale con
 *   dejar el fichero en mobile/google-services.json. Una build `production`
 *   de Android sin ninguno de los dos FALLA a propósito (no recibiría avisos).
 * El mapa es MapLibre con teselas de OpenFreeMap: no necesita clave ni cuenta.
 */
const EAS_PROJECT_ID = process.env.EAS_PROJECT_ID || undefined;

if (process.env.EAS_BUILD_PROFILE === 'production' && !EAS_PROJECT_ID) {
  throw new Error(
    'Falta EAS_PROJECT_ID: una build de producción sin él no podría recibir avisos push. ' +
      'Defínelo como variable de entorno del proyecto en expo.dev (ver mobile/README.md).',
  );
}

const LOCAL_GOOGLE_SERVICES_FILE = './google-services.json';

// Sin @types/node en el proyecto: se tipa solo lo que se usa de `fs`.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const fs: { existsSync: (file: string) => boolean } = require('fs');

/** Enlaces cortos de la web (/2026-0040). Android no admite \d: 4 caracteres, guion, 4 caracteres. */
const SHORT_LINK_PATH_PATTERN = '/....-....';

const WEB_HOST = 'mapa.proactivefuture.eu';
const PAPER = '#f7f0e2';
const CLAY = '#ad573e';

export default ({ config, projectRoot }: ConfigContext): ExpoConfig => {
  const googleServicesFile =
    process.env.GOOGLE_SERVICES_JSON ||
    (fs.existsSync(`${projectRoot}/google-services.json`) ? LOCAL_GOOGLE_SERVICES_FILE : undefined);
  if (process.env.EAS_BUILD_PROFILE === 'production' && process.env.EAS_BUILD_PLATFORM === 'android' && !googleServicesFile) {
    throw new Error(
      'Falta google-services.json: una build de producción de Android sin Firebase no podría recibir avisos push. ' +
        'Súbelo a expo.dev como variable de entorno de tipo archivo GOOGLE_SERVICES_JSON (ver mobile/README.md).',
    );
  }
  return {
    ...config,
    name: 'Corradi',
    slug: 'corradi',
    scheme: 'corradi',
    version: '1.0.0',
    orientation: 'portrait',
    userInterfaceStyle: 'light',
    icon: './assets/images/icon.png',
    backgroundColor: PAPER,
    ios: {
      bundleIdentifier: 'eu.proactivefuture.corradi',
      supportsTablet: false,
      associatedDomains: [`applinks:${WEB_HOST}`],
      config: {
        usesNonExemptEncryption: false,
      },
      infoPlist: {
        // La app solo está en español: que VoiceOver la lea con voz española.
        CFBundleDevelopmentRegion: 'es',
        CFBundleLocalizations: ['es'],
        // MapLibre incluye su gestor de ubicación (MLRNLocationManager llama a
        // requestWhenInUseAuthorization), así que el binario referencia CoreLocation y App Store
        // Connect rechaza la subida sin este texto (ITMS-90683). La app nunca lo pide: no usa
        // <UserLocation> ni la ubicación del usuario.
        NSLocationWhenInUseUsageDescription:
          'Corradi no usa tu ubicación; el mapa la necesita declarada pero nunca la pide.',
      },
    },
    android: {
      package: 'eu.proactivefuture.corradi',
      adaptiveIcon: {
        backgroundColor: CLAY,
        foregroundImage: './assets/images/android-icon-foreground.png',
        backgroundImage: './assets/images/android-icon-background.png',
        monochromeImage: './assets/images/android-icon-monochrome.png',
      },
      ...(googleServicesFile ? { googleServicesFile } : {}),
      // Gesto "atrás" predictivo (Android 13+). Nada depende de tenerlo apagado: la única
      // intercepción de "atrás" es la de la bienvenida (BackHandler), y RN la sigue recibiendo con
      // él activo (ReactActivity registra un OnBackPressedCallback siempre habilitado).
      predictiveBackGestureEnabled: true,
      // Permisos que añaden dependencias y la app no usa. La ubicación la declara el manifiesto de
      // MapLibre, pero el mapa nunca la pide (no hay punto azul ni "dónde estoy").
      blockedPermissions: [
        'android.permission.SYSTEM_ALERT_WINDOW',
        'android.permission.READ_EXTERNAL_STORAGE',
        'android.permission.WRITE_EXTERNAL_STORAGE',
        'android.permission.ACCESS_COARSE_LOCATION',
        'android.permission.ACCESS_FINE_LOCATION',
      ],
      intentFilters: [
        {
          action: 'VIEW',
          autoVerify: true,
          // Fichas (/proyecto/…) y enlaces cortos (/2026-0040, ver src/app/+native-intent.tsx).
          data: [
            { scheme: 'https', host: WEB_HOST, pathPrefix: '/proyecto/' },
            { scheme: 'https', host: WEB_HOST, pathPattern: SHORT_LINK_PATH_PATTERN },
          ],
          category: ['BROWSABLE', 'DEFAULT'],
        },
      ],
    },
    plugins: [
      'expo-router',
      [
        'expo-splash-screen',
        {
          backgroundColor: PAPER,
          image: './assets/images/splash-icon.png',
          imageWidth: 120,
        },
      ],
      [
        // Fuentes de la marca (las mismas de la web), incrustadas en la build.
        'expo-font',
        {
          fonts: [
            './assets/fonts/Manrope-Regular.ttf',
            './assets/fonts/Manrope-Medium.ttf',
            './assets/fonts/Manrope-SemiBold.ttf',
            './assets/fonts/Manrope-Bold.ttf',
            './assets/fonts/Sora-SemiBold.ttf',
            './assets/fonts/Sora-Bold.ttf',
          ],
        },
      ],
      [
        'expo-notifications',
        {
          icon: './assets/images/notification-icon.png',
          color: CLAY,
          defaultChannel: 'digest',
        },
      ],
      // Mapa nativo (MapLibre). No funciona en Expo Go: hace falta una build de EAS.
      '@maplibre/maplibre-react-native',
    ],
    experiments: {
      typedRoutes: true,
      reactCompiler: true,
    },
    extra: {
      ...config.extra,
      eas: {
        // PENDIENTE: id del proyecto de expo.dev (EAS_PROJECT_ID). Sin él no hay token push.
        ...(EAS_PROJECT_ID ? { projectId: EAS_PROJECT_ID } : {}),
      },
    },
  };
};
