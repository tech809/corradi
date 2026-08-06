# Archivo — WhatsApp Business API (aparcado)

El lanzamiento es **Telegram-only** de cara al usuario final; la difusión real de WhatsApp
sigue siendo copiar-pegar a mano (bot dedicado que reenvía cada oportunidad por DM, ver
"Reenvío a WhatsApp" en el README principal). Estas guías documentan la integración con la
API oficial de WhatsApp Business (mensajería automática, no el canal de difusión) — handoff
saliente + entrante vía Twilio, y la alternativa con Meta Cloud API directo — que funcionó
en su momento pero no forma parte del flujo actual.

Se conservan por si se activa WhatsApp Business API en una fase posterior del proyecto. El
código sigue en `app/publisher/whatsapp_twilio.py`, `app/publisher/whatsapp_cloud.py` y
`app/api/twilio_webhook.py` (marcado como aparcado en sus docstrings), controlado por
`HANDOFF_MODE` en `.env` (`telegram` = bot dedicado activo hoy; `whatsapp_twilio` /
`whatsapp_cloud` = estas guías; `none` = nada).
