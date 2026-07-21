# Archivo — WhatsApp (aparcado)

El lanzamiento es **Telegram-only** (ver README principal). Estas guías documentan la
integración de WhatsApp (handoff saliente + entrante vía Twilio, y la alternativa con
Meta Cloud API directo) que funcionó en su momento pero no forma parte del flujo actual.

Se conservan por si se reactiva WhatsApp en una fase posterior del proyecto. El código
sigue en `app/publisher/whatsapp_twilio.py`, `app/publisher/whatsapp_cloud.py` y
`app/api/twilio_webhook.py` (marcado como aparcado en sus docstrings), controlado por
`HANDOFF_MODE=none` en `.env`.
