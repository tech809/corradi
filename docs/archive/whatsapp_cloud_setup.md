# Alta de WhatsApp Cloud API para el handoff

El bot manda la oportunidad por WhatsApp a los **números admin** (`WHATSAPP_RECIPIENTS`), que
luego la **reenvían/pegan en el canal de difusión** (los Canales de WhatsApp no tienen API,
así que ese último paso es humano).

Como el bot inicia el mensaje, Meta obliga a usar una **plantilla aprobada** (template).

## 1. Crear la app y el número (Meta)

1. Entra en **developers.facebook.com** → crea una app de tipo *Business*.
2. Añade el producto **WhatsApp**. Meta te da un **número de prueba** y un **Phone number ID**
   y un **token temporal** (24h). Para producción: añade tu propio número y genera un
   **token permanente** (System User en Business Manager) o usa un **BSP** (Twilio, 360dialog).
3. Apunta:
   - `WHATSAPP_PHONE_NUMBER_ID` → el Phone number ID del número emisor.
   - `WHATSAPP_CLOUD_TOKEN` → el token (permanente para producción).

## 2. Dar de alta los destinatarios

- Con el **número de prueba** de Meta, solo puedes enviar a números que añadas a la lista de
  *recipients* de prueba en el panel (incluye ahí el +34644117336).
- En **producción**, los destinatarios deben haber dado **opt-in** (basta que tus 2 admins
  acepten recibir estos mensajes; déjalo registrado).

## 3. Crear la plantilla (template)

En **WhatsApp Manager → Plantillas → Crear**:
- **Nombre:** `nueva_oportunidad` (debe coincidir con `WHATSAPP_TEMPLATE_NAME`)
- **Idioma:** Español (`es`)
- **Categoría:** *Utility*
- **Cuerpo** (con 5 variables, sin saltos de línea dentro de cada variable):

```
📋 Nueva oportunidad para el canal:

🌍 {{1}}
ℹ️ {{2}}
⏳ Inscripción: {{3}}
👉 {{4}}
[{{5}}]

Cópiala y pégala en el canal de difusión.
```

- Ejemplos de valores al enviarla a revisión:
  `{{1}}` DIGITAL DETOX · `{{2}}` Intercambio juvenil · Polonia · 23/06/2026 - 30/06/2026 ·
  `{{3}}` 02/07/2026 · `{{4}}` https://forms.gle/xxxx · `{{5}}` CORRADI-2026-0001

Espera a que Meta la **apruebe** (suele ser minutos/horas).

## 4. Configurar el `.env`

```
HANDOFF_MODE=whatsapp_cloud
WHATSAPP_RECIPIENTS=34644117336            # y los demás admin, separados por coma, sin '+'
WHATSAPP_CLOUD_TOKEN=EAAG...               # tu token
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_TEMPLATE_NAME=nueva_oportunidad
WHATSAPP_TEMPLATE_LANG=es
```

Reinicia el bot: `docker compose up -d bot`.

## 5. Probar

- **Texto libre** (rápido, requiere que el admin haya escrito antes al número del bot dentro
  de 24h):
  ```
  docker compose run --rm bot python -m app.publisher.whatsapp_cloud text 34644117336 "Prueba ✅"
  ```
- **Plantilla** (flujo real): sube una oportunidad por el bot de Telegram; el handoff saldrá
  por WhatsApp a los destinatarios.

## Notas

- Coste: utility ~0,01-0,03 €/mensaje (a 2 números es despreciable). El texto libre dentro de
  la ventana de 24h es gratis.
- Mientras no rellenes token/phone_id, el handoff por Cloud API queda **inactivo** (el bot avisa
  por log y no falla). `HANDOFF_MODE=telegram` (bot dedicado de reenvío, ver README principal)
  sigue siendo el modo real de producción hoy, no un interino.
- El bot ya construye los 5 parámetros desde la oportunidad
  (`app/publisher/whatsapp_cloud.py::_template_params`). Si cambias la plantilla, ajusta ahí.
