"""Configuración central leída de variables de entorno (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # python-dotenv es opcional (p.ej. en dry-run/tests sin dependencias instaladas)
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


def _ids(raw: str | None) -> list[int]:
    return [int(x.strip()) for x in (raw or "").split(",") if x.strip()]


def _phones(raw: str | None) -> list[str]:
    """Normaliza números a formato Cloud API: solo dígitos, sin '+', espacios ni guiones."""
    out = []
    for x in (raw or "").split(","):
        digits = "".join(c for c in x if c.isdigit())
        if digits:
            out.append(digits)
    return out


@dataclass(frozen=True)
class Config:
    # Infra
    database_url: str = os.getenv("DATABASE_URL", "postgresql://corradi:corradi@localhost:5432/corradi")

    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    # Username público del canal (sin @), para enlazar directamente a cada post del resumen diario.
    telegram_channel_username: str = os.getenv("TELEGRAM_CHANNEL_USERNAME", "")
    admin_telegram_ids: list[int] = field(default_factory=lambda: _ids(os.getenv("ADMIN_TELEGRAM_IDS")))
    whatsapp_handoff_group_id: str = os.getenv("WHATSAPP_HANDOFF_TELEGRAM_GROUP_ID", "")

    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")  # 'gemini' | 'fake' (dry-run sin claves)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
    embed_model: str = os.getenv("EMBED_MODEL", "gemini-embedding-001")
    embed_dim: int = int(os.getenv("EMBED_DIM", "768"))

    # Negocio
    # Fecha límite estimada cuando el mensaje no trae ninguna: +5 días normalmente, y solo
    # +2 días si el mensaje anuncia última hora / últimas plazas.
    default_deadline_days: int = int(os.getenv("DEFAULT_DEADLINE_DAYS", "5"))
    last_minute_deadline_days: int = int(os.getenv("LAST_MINUTE_DEADLINE_DAYS", "2"))
    # Solo se aceptan oportunidades cuya fecha límite de inscripción caiga dentro de estos
    # meses (red de seguridad ante años mal inferidos, p.ej. "17/07" sin año procesado
    # después del 17 de julio -> el LLM podría empujarlo un año de más).
    max_deadline_months: int = int(os.getenv("MAX_DEADLINE_MONTHS", "3"))
    dedup_threshold: float = float(os.getenv("DEDUP_THRESHOLD", "0.88"))
    # Umbral relajado para detectar la MISMA oportunidad en otro idioma (EN/ES): solo se
    # aplica cuando además coinciden país y fecha de inicio, así que puede ser más bajo sin
    # provocar falsos positivos entre oportunidades realmente distintas.
    dedup_crosslang_threshold: float = float(os.getenv("DEDUP_CROSSLANG_THRESHOLD", "0.72"))
    # Anti-abuso: máximo de oportunidades que puede crear un coordinador al día, y nº de
    # envíos consecutivos que no son oportunidad (spam) antes de bloquear automáticamente
    # (con 2: el 1er mensaje que no es oportunidad avisa, el 2º seguido bloquea).
    max_daily_opportunities: int = int(os.getenv("MAX_DAILY_OPPORTUNITIES", "3"))
    spam_block_threshold: int = int(os.getenv("SPAM_BLOCK_THRESHOLD", "2"))
    timezone: str = os.getenv("TIMEZONE", "Europe/Madrid")
    summary_hour: int = int(os.getenv("SUMMARY_HOUR", "20"))
    identifier_prefix: str = os.getenv("IDENTIFIER_PREFIX", "CORRADI")
    # URL pública del mapa interactivo; si está vacía, el resumen diario no lo enlaza.
    map_public_url: str = os.getenv("MAP_PUBLIC_URL", "")

    # Handoff a WhatsApp: 'telegram' (grupo) | 'whatsapp_cloud' (API oficial) | 'none'
    handoff_mode: str = os.getenv("HANDOFF_MODE", "telegram")
    # WhatsApp Business Cloud API
    whatsapp_cloud_token: str = os.getenv("WHATSAPP_CLOUD_TOKEN", "")
    whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    whatsapp_recipients: list[str] = field(default_factory=lambda: _phones(os.getenv("WHATSAPP_RECIPIENTS")))
    whatsapp_template_name: str = os.getenv("WHATSAPP_TEMPLATE_NAME", "nueva_oportunidad")
    whatsapp_template_lang: str = os.getenv("WHATSAPP_TEMPLATE_LANG", "es")
    graph_api_version: str = os.getenv("GRAPH_API_VERSION", "v21.0")
    # WhatsApp vía Twilio (BSP)
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_whatsapp_from: str = os.getenv("TWILIO_WHATSAPP_FROM", "")   # p.ej. whatsapp:+14155238886
    twilio_content_sid: str = os.getenv("TWILIO_CONTENT_SID", "")       # HX... (plantilla; vacío = texto libre)
    # WhatsApp ENTRANTE (gestores que envían oportunidades por WhatsApp)
    whatsapp_allowed_senders: list[str] = field(default_factory=lambda: _phones(os.getenv("WHATSAPP_ALLOWED_SENDERS")))
    twilio_validate_signature: bool = os.getenv("TWILIO_VALIDATE_SIGNATURE", "false").lower() == "true"

    # Chatbot del mapa (pregunta en lenguaje natural sobre las oportunidades abiertas, ver
    # docs/chatbot_mapa.md). Reutiliza GEMINI_API_KEY y cfg.llm_model, no una clave/modelo aparte.
    # Tope de gasto mensual real (medido con usage_metadata, no estimado): al alcanzarlo el
    # endpoint deja de llamar a Gemini hasta que empiece el mes siguiente.
    chat_monthly_budget_usd: float = float(os.getenv("CHAT_MONTHLY_BUDGET_USD", "5.0"))
    # Rate-limit por IP en memoria (el proceso `api` corre sin --workers, ver docker/api.Dockerfile).
    chat_rate_limit_per_hour: int = int(os.getenv("CHAT_RATE_LIMIT_PER_HOUR", "10"))
    chat_rate_limit_per_day: int = int(os.getenv("CHAT_RATE_LIMIT_PER_DAY", "30"))
    # Cuánto se cachea en memoria el catálogo compacto de abiertas antes de reconstruirlo.
    chat_catalog_cache_seconds: int = int(os.getenv("CHAT_CATALOG_CACHE_SECONDS", "180"))

    # Instagram (Graph API, cuenta Business/Creator). Vacío = publicación en IG desactivada
    # sin más (no rompe nada, el resto del pipeline sigue igual — mismo patrón que WhatsApp).
    instagram_token: str = os.getenv("INSTAGRAM_LONG_LIVED_TOKEN", "")
    instagram_business_id: str = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    # Base pública desde la que la Graph API descarga las imágenes (nuestra propia API,
    # GET /ig/{identifier}/post.png y /story.png) — no un repo aparte, como hacía tur-app.
    instagram_image_base_url: str = os.getenv("INSTAGRAM_IMAGE_BASE_URL", "")
    instagram_max_attempts: int = int(os.getenv("INSTAGRAM_MAX_ATTEMPTS", "5"))
    # Espaciado mínimo entre publicaciones. A 0 (por defecto): publicación directa en cuanto
    # llega, sin cola de por medio — a petición expresa, tras ver que un espaciado alto (20
    # min) hacía que el barrido de 2h en 2h solo soltase una oportunidad por pasada y un
    # backlog grande (p.ej. el de SALTO) tardase casi un día entero en publicarse en
    # Instagram, muy por detrás de Telegram. Si el volumen crece, aquí es donde se retomaría
    # un espaciado > 0.
    instagram_min_gap_minutes: int = int(os.getenv("INSTAGRAM_MIN_GAP_MINUTES", "0"))
    # Carpeta compartida entre `bot` (genera el .mp4 del Reel, pesado) y `api` (solo lo
    # sirve tal cual por GET /ig/{id}/reel.mp4) — volumen `media_data` en docker-compose.
    media_dir: str = os.getenv("MEDIA_DIR", "/data/media")

    # Tope de publicaciones DIRECTAS por pasada del escaneo diario de SALTO (mediodía) — a
    # partir de aquí, lo que siga pasando el filtro se encola en `salto_backlog` para salir
    # en la pasada de las 17:00 (misma tabla/mecanismo que el backlog inicial, ver
    # `app/scheduler/scrape_salto.py` y `publish_salto_backlog.py`). Pedido explícito tras
    # ver 3 Training Course publicarse de golpe el mismo día (2026-07-28).
    salto_scrape_daily_cap: int = int(os.getenv("SALTO_SCRAPE_DAILY_CAP", "2"))


cfg = Config()
