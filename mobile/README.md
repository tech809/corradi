# Corradi · app móvil

App de Corradi (Expo SDK 58 + Expo Router + TypeScript + React Compiler) para iOS y Android. Lee
los datos de `https://mapa.proactivefuture.eu` (ver `src/lib/config.ts`). No hay cuentas: todo lo
que recuerda la app vive en el móvil.

## Arrancar en local

```bash
npm install
npx expo start          # abre en Expo Go o en una build instalada
npx tsc --noEmit        # tipos
npx expo lint           # lint
npx expo-doctor         # dependencias y configuración
```

**Límites de Expo Go:** sirve para ver pantallas y recordatorios locales.

- El **mapa no se ve en Expo Go** (MapLibre es código nativo): la pestaña Mapa enseña un aviso
  con «Ver como lista» (la vista Lista sí funciona) y «Abrir el mapa web».
- Los **avisos push no funcionan** en Expo Go para Android, en simuladores ni en builds sin
  `EAS_PROJECT_ID`. La app lo dice tal cual («Los avisos estarán disponibles en la versión de
  las tiendas») y no llega a pedir permiso. Para probarlos hace falta una build en un móvil real.

## Variables de entorno

Se leen en `app.config.ts` al compilar. En local, ponlas en `.env.local` (no se sube a git);
para los builds en la nube, como variables de entorno del proyecto en expo.dev
(`npx eas-cli@latest env:create`).

| Variable | Para qué | Si falta |
|---|---|---|
| `EAS_PROJECT_ID` | Id del proyecto en expo.dev. Hace falta para obtener el token push. | La app funciona, pero sin resumen diario (Ajustes y bienvenida lo indican). **Una build `production` falla a propósito** (`app.config.ts` lanza un error si `EAS_BUILD_PROFILE=production` y no hay `EAS_PROJECT_ID`): así no puede llegar a las tiendas una app sin push. |
| `GOOGLE_SERVICES_JSON` | Ruta al `google-services.json` (Firebase, push en Android). En EAS, variable de entorno de tipo **archivo** (ver abajo). | Se usa `mobile/google-services.json` si existe. Si no hay ninguno, Android no recibe push y **una build `production` de Android falla a propósito** (`EAS_BUILD_PROFILE=production` + `EAS_BUILD_PLATFORM=android`). |

El mapa (OpenFreeMap) no necesita clave.

### `google-services.json` (push en Android)

Android recibe los push a través de Firebase Cloud Messaging, y para eso la build **necesita**
`mobile/google-services.json`. Sin él la app compila, pero en Android no llega ningún aviso.

1. En [console.firebase.google.com](https://console.firebase.google.com) crea (o abre) un
   proyecto de Firebase.
2. Añade una app **Android** con el paquete `eu.proactivefuture.corradi`.
3. Descarga `google-services.json` y dáselo a la build de una de estas dos formas
   (`app.config.ts` lo enlaza en `android.googleServicesFile`):
   - **EAS (recomendado):** variable de entorno de tipo archivo
     `npx eas-cli@latest env:create --name GOOGLE_SERVICES_JSON --type file --value ./google-services.json --environment production --environment preview`.
     EAS pone en `GOOGLE_SERVICES_JSON` la ruta del fichero durante la build.
   - **Local:** déjalo en `mobile/google-services.json` (se detecta con `fs.existsSync`).
     Solo contiene identificadores públicos del proyecto (no es un secreto): se puede subir a git.
4. Sube además la clave de la **cuenta de servicio de FCM v1** a EAS
   (`npx eas-cli@latest credentials` › Android › Push Notifications: FCM V1). Esa clave SÍ es
   secreta: no va al repositorio.

## Builds (EAS)

```bash
npx eas-cli@latest login
npx eas-cli@latest init                                              # crea el proyecto y da el EAS_PROJECT_ID
npx eas-cli@latest build --profile preview-ios-sim --platform ios    # .app para el simulador de iOS (sin firma)
npx eas-cli@latest build --profile preview --platform android        # APK para probar (distribución interna)
npx eas-cli@latest build --profile preview --platform ios            # requiere registrar los iPhone de prueba
npx eas-cli@latest build --profile production --platform all         # AAB + IPA para las tiendas
npx eas-cli@latest submit --profile production --platform ios|android
```

- `preview-ios-sim`: build interna para el simulador (`ios.simulator: true`). No es un
  development build (`expo-dev-client` no está instalado): lleva el JS dentro, como `preview`.
  Ahí se ven el mapa y las fuentes, pero no hay push (simulador).
- El número de build lo lleva EAS (`appVersionSource: remote`, `autoIncrement` en
  `production`). La versión visible (`1.0.0`) está en `app.config.ts`.

## Fuentes

Manrope (texto) y Sora (rótulos), las mismas de la web, en `assets/fonts/`. En las builds van
incrustadas con el plugin `expo-font` de `app.config.ts`; en Expo Go las carga `useFonts` en
`src/app/_layout.tsx` (máximo 4 s; si fallan se sigue con las del sistema). La serif de los
titulares es la del sistema (Georgia en iOS, `serif` en Android). Escala y nombres:
`src/constants/theme.ts` (`Fonts`, `Typography`).

## Cómo funcionan los avisos

- **Resumen diario (push):** al activarlo (bienvenida o Ajustes) la app comprueba primero si
  este binario puede recibir push (móvil real, `EAS_PROJECT_ID`, no Expo Go en Android); si no,
  devuelve `unavailable` sin pedir permiso. Si puede, pide permiso, obtiene el token Expo y lo
  manda a `POST /api/push/register` con `{token, platform, types, daily_digest}` (`types` vacío =
  todos). Desactivarlo llama a `POST /api/push/unregister`.
- **Sin llamadas de más:** se guarda lo último registrado (`{token, types, digest}`) y solo se
  vuelve a llamar al servidor si cambia algo. Si el token nativo (APNs/FCM) no ha cambiado y lo
  registrado está al día, se reutiliza el token Expo guardado (no se pide otra vez a Expo). Si el sistema rota el token
  (`addPushTokenListener`), se registra el nuevo y se da de baja el antiguo. Si al arrancar el
  permiso del sistema se ha retirado, se da de baja el token pero se conserva la preferencia:
  al volver a dar permiso se registra solo. Lo que falla sin red se reintenta al arrancar y al
  volver la app a primer plano (como mucho cada 15 s).
- **Sin carreras:** registrar, dar de baja y sincronizar van en una fila (`serial` en
  `src/lib/push.ts`): si se desactiva mientras un registro está en vuelo, la baja va después y lo
  deshace; si cambian los tipos durante el envío, se manda lo nuevo.
- **Servidor:** cron a las **19:30** (`push_digest`) manda un único aviso si hay proyectos
  nuevos de los tipos elegidos, con `data: {screen: 'nuevos', ids: [...]}` y canal Android
  `digest`; cron a las **19:50** (`push_digest --receipts-only`) lee los recibos de Expo y borra
  los tokens muertos. Tablas `push_devices` (migración `0024`) y `push_tickets` (`0027`).
- **Me interesa** (bienvenida, «¿Qué te interesa?», y Ajustes): los tipos marcados filtran el resumen push y la pestaña Nuevos
  (`usePushPrefs().types` en `src/lib/push.ts`).
- **Recordatorios de plazo (locales):** se programan en el propio móvil, canal `reminders`,
  `data: {screen: 'proyecto', id}` (`src/lib/reminders.ts`).
- **Al tocar una notificación** (también con la app cerrada): el resumen abre Nuevos con
  `?ids=ID1,ID2` (enseña justo esos) y el recordatorio abre la ficha. Cada toque se atiende una
  sola vez (por `request.identifier`). Código: `src/lib/notification-routing.ts`.

## Enlaces profundos

- Esquema propio: `corradi://proyecto/CORRADI-2026-0731`.
- Enlaces web: `https://mapa.proactivefuture.eu/proyecto/{id}` abre la ficha en la app si está
  instalada (iOS *universal links* vía `associatedDomains`; Android *app links* con `autoVerify`).
- Enlaces cortos: `https://mapa.proactivefuture.eu/2026-0040` → ficha `CORRADI-2026-0040`. La
  reescritura la hace `src/app/+native-intent.tsx` (`redirectSystemPath`, patrón `^/\d{4}-\d{4}$`).
  Android los captura con `pathPattern: '/....-....'` (Android no admite `\d`: cualquier ruta de
  4+1+4 caracteres abre la app; si no es un enlace corto, se ve la pantalla de «no encontrada»).
  En iOS hace falta que el AASA del servidor incluya esas rutas.
- Ruta desconocida: `src/app/+not-found.tsx` («No encontramos esa página», botón a Nuevos).
- `unstable_settings.anchor = '(tabs)'` en `src/app/_layout.tsx`: una ficha abierta por enlace o
  notificación tiene las pestañas debajo, así «atrás» vuelve a la app.
- Mapa centrado en un proyecto: `router.navigate({ pathname: '/mapa', params: { focus: id } })`.

## Mapa

MapLibre (`@maplibre/maplibre-react-native` 11) con el estilo *positron* de OpenFreeMap
(`https://tiles.openfreemap.org/styles/positron`): sin clave, sin cuenta y sin coste. La app
descarga ese estilo una vez, lo guarda en la caché del móvil (`expo-file-system`) y lo recolorea
a la marca (tierra papel, usos del suelo papel hundido, parques salvia, agua verdosa) con los
nombres en español (`name:es`, si no `name:latin`, si no `name`). Si no hay copia y la descarga
falla, usa la URL tal cual. Si el mapa no carga (sin red), una píldora lo dice y ofrece «Ver
como lista». Colores
por tipo de `TypeColors` y letra del tipo en cada punto (punto relleno = ubicación exacta;
anillo = solo el país). Los números de los grupos usan la fuente *Noto Sans Bold* de los glifos
de OpenFreeMap. Hay vista **Lista** (agrupada por país, con encabezados, y por plazo
dentro de cada país), que es la de por defecto con lector de pantalla. La atribución a
OpenStreetMap/OpenFreeMap se muestra en el propio mapa (arriba a la derecha, bajo los controles)
y **no debe quitarse** (licencia ODbL).

- **Carga diferida:** las pestañas nativas montan todas las pantallas al arrancar; el mapa
  (MapLibre y la descarga del estilo) solo se monta la primera vez que se entra en la pestaña Mapa.
- «**Ver toda Europa**» vuelve a la vista inicial (alternativa a pellizcar, WCAG 2.5.7). Si hay
  pines de ubicación aproximada, una leyenda lo explica («Anillo: ubicación aproximada»).
- En la vista Lista, encabezados de país fijos al desplazar y un campo «Buscar país».

**Barra de pestañas y elementos flotantes:** usa `useTabBarClearance()` (`src/lib/layout.ts`).
En iOS el contenido de la pestaña pasa por debajo de la barra y `insets.bottom` ya la incluye; en
Android el contenido termina encima de la barra. El fichero explica de dónde sale cada cosa.
Pendiente de comprobar en dispositivo.

## Recursos gráficos

`assets/images/` se genera a partir del símbolo «Estrella polar» del kit de marca
(`../design/`): icono iOS 1024 sin transparencia, icono adaptativo de Android (primer plano,
fondo y monocromo), icono de notificación (silueta blanca) y splash. `welcome.jpg` (bienvenida)
es un recorte 4:3 de `../app/api/static/photo-team.jpg` (la foto más grande disponible,
1600×900): 1200×900 px y <250 KB
(`sips -c 900 1200 --cropOffset 0 266 photo-team.jpg` y luego `-s formatOptions 55`). Se muestra
entera a 4:3 dentro del scroll; ninguna foto del repositorio llega a 1290 px de ancho con ese
alto, así que en los iPhone «Pro Max» se amplía un ~7 %. `assets/brand/` tiene la marca Corradi.

## Antes de publicar

- [ ] **EAS:** `npx eas-cli@latest init` y definir `EAS_PROJECT_ID` (variable de EAS para las
      builds en la nube). Sin él no hay push, y la build `production` se para con un error a
      propósito (comprobación en `app.config.ts`).
- [ ] **Android push:** `google-services.json` como variable de EAS de tipo archivo
      `GOOGLE_SERVICES_JSON` (o en `mobile/`, ver arriba) y clave FCM v1 subida a EAS. Sin él, la
      build `production` de Android se para con un error a propósito. Comprobar con
      `npx expo config --type public` que aparece `android.googleServicesFile`.
- [ ] **Apple:** cuenta de Apple Developer y app en App Store Connect; rellenar
      `submit.production.ios` (`ascAppId`, `appleTeamId`) en `eas.json`. Poner el **Team ID** en
      `APPLE_TEAM_ID` del servidor (sirve `/.well-known/apple-app-site-association`).
- [ ] **Google Play:** app en Play Console, cuenta de servicio subida a EAS para `eas submit`.
      Con Play App Signing, copiar la huella **SHA‑256** del certificado de firma de la app
      (Play Console › Integridad de la app) a `ANDROID_CERT_SHA256` del servidor (sirve
      `/.well-known/assetlinks.json`).
- [ ] **APNs:** lo gestiona EAS en el primer build de iOS.
- [ ] **Ubicación (decidido, no tocar sin motivo):** la app no usa la ubicación. En Android se
      bloquean `ACCESS_COARSE_LOCATION` y `ACCESS_FINE_LOCATION` (las añade el manifiesto de
      MapLibre). En iOS el binario de MapLibre referencia CoreLocation
      (`requestWhenInUseAuthorization`), y App Store Connect rechaza la subida sin
      `NSLocationWhenInUseUsageDescription`; por eso se declara con un texto honesto («Corradi no
      usa tu ubicación; el mapa la necesita declarada pero nunca la pide»). En las fichas de las
      tiendas (privacidad de la app / seguridad de los datos): **no se recoge la ubicación**.
- [ ] **Servidor:** desplegar el backend; aplicar a mano las migraciones `0024_push_devices.sql` y
      `0027_push_tickets.sql`; añadir al crontab
      `30 19 * * * docker exec corradi-bot python -m app.scheduler.push_digest` y
      `50 19 * * * docker exec corradi-bot python -m app.scheduler.push_digest --receipts-only`.
- [ ] Página de privacidad publicada en `/privacidad-app` (la enlaza Ajustes y la piden las tiendas).
- [ ] **Enlaces cortos:** el AASA (`/.well-known/apple-app-site-association`) del servidor debe
      incluir las rutas `/NNNN-NNNN` además de `/proyecto/*`.
- [ ] Probar en un móvil real (build `preview`): activar avisos, tocar un resumen y un
      recordatorio con la app cerrada, abrir un enlace `https://mapa.proactivefuture.eu/proyecto/…`
      y uno corto (`https://mapa.proactivefuture.eu/2026-0040`), y una ruta inexistente.
- [ ] **Dependencias quitadas** (no las usaba nada): `@expo/ui`, `expo-glass-effect` y
      `expo-sharing` (y su plugin). Compartir usa el `Share` de React Native (`src/lib/share.ts`).
