# WhatsApp vía Twilio — entrante (gestionar) y saliente (handoff)

Dos direcciones:
- **Saliente (handoff):** el bot envía la oportunidad por WhatsApp a `WHATSAPP_RECIPIENTS` (los
  admins), que la pegan en el canal de difusión (los Canales de WhatsApp no tienen API).
- **Entrante:** un gestor manda una oportunidad **por WhatsApp** → llega al webhook
  `/webhooks/twilio` → mismo pipeline que Telegram (clasifica, extrae, deduplica, guarda) → te
  responde por WhatsApp. Autorización por número en `WHATSAPP_ALLOWED_SENDERS`.

## C) WhatsApp ENTRANTE (webhook) — pasos en Twilio

Twilio tiene que poder **llegar** a tu API por internet. En local se hace con un túnel (ngrok);
en producción es la URL pública de tu EC2.

1. Túnel a tu API local (en otra terminal):
   ```
   brew install ngrok        # si no lo tienes
   ngrok http 8000
   ```
   Copia la URL https que te da, p.ej. `https://abce-1-2-3-4.ngrok-free.app`.
2. En la consola de Twilio: **Messaging › Try it out › Send a WhatsApp message › Sandbox settings**
   (es donde antes ponía `https://timberwolf-mastiff-9776.twil.io/demo-reply`).
   - **When a message comes in** → `https://<tu-ngrok>/webhooks/twilio` · Método **POST** · Guardar.
3. Desde tu WhatsApp (ya unido con `join entire-oxygen`) envía una oportunidad al
   **+1 415 523 8886**. El bot la procesa y te responde con la ficha + identificador.
4. Añade los números de gestores autorizados en `.env`:
   `WHATSAPP_ALLOWED_SENDERS=34644117336,34600111222`
5. Producción: en tu **Sender**/Messaging Service, pon el mismo webhook apuntando a la URL
   pública de la EC2 (`https://tu-dominio/webhooks/twilio`) y `TWILIO_VALIDATE_SIGNATURE=true`.

---

## A) Probar YA con el Sandbox (gratis, sin aprobación)

1. Desde el WhatsApp del admin (**+34644117336**), envía un WhatsApp a **+1 415 523 8886** con el
   texto: **`join entire-oxygen`** (el código aparece en tu consola de Twilio › Sandbox).
   Esto "une" ese número al sandbox y abre una ventana de 24h.
2. En la consola de Twilio copia el **Auth Token** (el Account SID ya está en `.env`).
3. Rellena en `.env`:
   ```
   HANDOFF_MODE=whatsapp_twilio
   TWILIO_AUTH_TOKEN=tu_auth_token
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   TWILIO_CONTENT_SID=                      # vacío → texto libre (vale en la ventana de 24h)
   WHATSAPP_RECIPIENTS=34644117336
   ```
4. Reinicia: `docker compose up -d bot`
5. Prueba directa:
   ```
   docker compose run --rm bot python -m app.publisher.whatsapp_twilio text 34644117336 "Prueba CORRADI ✅"
   ```
   o sube una oportunidad por el bot de Telegram → te llega por WhatsApp.

> Sandbox = solo para pruebas. "May not reliably deliver international messages" y caduca la
> ventana de 24h; hay que reenviar `join` si pasa mucho tiempo.

## B) Producción (tu propio número + plantilla)

1. **Registra tu WhatsApp Sender** en Twilio (Messaging › Senders): tu número, con verificación
   de Meta Business detrás. Twilio te guía (Direct Customer self-sign-up).
2. Crea una **Content Template** en *Content Template Builder* (categoría Utility) con 5
   variables, p.ej.:
   ```
   📋 Nueva oportunidad para el canal:
   🌍 {{1}}
   ℹ️ {{2}}
   ⏳ Inscripción: {{3}}
   👉 {{4}}
   [{{5}}]
   ```
   Mapeo (lo genera el código, `whatsapp_cloud._template_params`):
   {{1}} título · {{2}} tipo · lugar · fechas · {{3}} deadline · {{4}} formulario · {{5}} id
3. Cuando Twilio/Meta la aprueben, copia su **ContentSid** (`HX...`).
4. En `.env`:
   ```
   TWILIO_WHATSAPP_FROM=whatsapp:+<tu_numero>
   TWILIO_CONTENT_SID=HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
   Con `TWILIO_CONTENT_SID` puesto, el bot envía **plantilla** (funciona en cualquier momento,
   no solo en la ventana de 24h).
5. `docker compose up -d bot`.

## Coste (con vuestro flujo)

- El handoff solo va a los **2 admins**, no a miles. Con ~10-100 oportunidades/mes →
  20-200 mensajes/mes.
- Precio ≈ tarifa de Meta (utility España ~0,01-0,03 €) **+ fee Twilio ~0,005 $/msg**
  ≈ **0,02-0,04 €/mensaje** → **~0,5-6 €/mes**. Despreciable frente al EC2.
- Tienes **15,50 $ de trial**; el sandbox no consume. Producción puede tener una pequeña cuota
  por el número/sender.
