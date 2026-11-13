"""Banner «Descarga la app» de la portada y las fichas, aislado de FastAPI para probarlo.

Solo se pinta si hay APP_STORE_URL y/o PLAY_STORE_URL: mientras las apps no estén publicadas
la web sale exactamente igual que antes (ni un byte de más). La plataforma se decide en el
navegador por user agent — no en el servidor — para no partir la caché de la página por
User-Agent: iPhone/iPad ve el enlace de la App Store, Android el de Google Play, y el
escritorio nada. Se puede cerrar y no vuelve a salir en ese navegador (localStorage).
"""
from __future__ import annotations

import json
import re

_STORAGE_KEY = "corradi-app-banner-cerrado"


def _https(url: str) -> str:
    """Solo URLs https: cualquier otra cosa en el .env se ignora en vez de acabar en un href."""
    return url if url.startswith("https://") else ""


def is_enabled(app_store_url: str, play_store_url: str, app_store_id: str) -> bool:
    return bool(_https(app_store_url) or _https(play_store_url) or _valid_store_id(app_store_id))


def _valid_store_id(app_store_id: str) -> str:
    return app_store_id if re.fullmatch(r"\d{5,15}", app_store_id or "") else ""


def inject(content: str, app_store_url: str, play_store_url: str, app_store_id: str) -> str:
    ios, android, store_id = _https(app_store_url), _https(play_store_url), _valid_store_id(app_store_id)
    if store_id:
        meta = f'<meta name="apple-itunes-app" content="app-id={store_id}">'
        content = content.replace("</head>", meta + "\n</head>", 1)
    if not (ios or android):
        return content
    urls = json.dumps({"ios": ios, "android": android}).replace("</", "<\\/")
    # En Safari de iOS, si hay APP_STORE_ID, ya sale el Smart App Banner nativo: no se
    # duplica. Sí se enseña en Chrome/Firefox/Edge de iOS y en navegadores integrados
    # (Instagram, Facebook...), donde el nativo no aparece.
    native = "true" if store_id else "false"
    snippet = f"""<div id="app-banner" role="region" aria-label="Descarga la app de Corradi" style="position:fixed;left:12px;right:12px;bottom:12px;z-index:9999;display:none;align-items:center;gap:12px;max-width:520px;margin:0 auto;padding:12px 14px;border-radius:14px;background:#263528;color:#f7f0e2;font:600 14px/1.35 Manrope,system-ui,sans-serif;box-shadow:0 8px 28px #0003">
<img src="/assets/icon-192.png" alt="" width="36" height="36" style="flex:none;border-radius:9px">
<span style="flex:1">Avisos de convocatorias nuevas en la app de Corradi</span>
<a id="app-banner-link" href="#" rel="noopener" style="flex:none;padding:8px 14px;border-radius:999px;background:#ad573e;color:#fff;text-decoration:none">Descargar</a>
<button type="button" id="app-banner-close" aria-label="Cerrar" style="flex:none;border:0;background:none;color:inherit;font-size:20px;line-height:1;padding:4px;cursor:pointer">&times;</button>
</div>
<script>(function(){{var u={urls},k={json.dumps(_STORAGE_KEY)},ua=navigator.userAgent||"";
try{{if(localStorage.getItem(k))return}}catch(e){{}}
var ios=/iPhone|iPad|iPod/.test(ua)||(/Macintosh/.test(ua)&&navigator.maxTouchPoints>1),url=ios?u.ios:/Android/.test(ua)?u.android:"";
if(!url)return;
if(ios&&{native}&&/Safari/.test(ua)&&!/CriOS|FxiOS|EdgiOS|OPiOS|FBAN|FBAV|Instagram|Line\\//.test(ua))return;
var b=document.getElementById("app-banner");document.getElementById("app-banner-link").href=url;b.style.display="flex";
document.getElementById("app-banner-close").addEventListener("click",function(){{b.style.display="none";try{{localStorage.setItem(k,"1")}}catch(e){{}}}});
}})();</script>
"""
    return content.replace("</body>", snippet + "</body>", 1)
