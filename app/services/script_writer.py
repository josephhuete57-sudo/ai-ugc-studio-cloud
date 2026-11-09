"""Guiones UGC en español: plantillas UGC + proveedor LLM opcional (nunca simulado)."""
from __future__ import annotations

import re

from app.core.config import settings

HOOKS = [
    "¿Te ha pasado que {problema}? A mí me pasaba cada día… hasta que descubrí esto.",
    "POV: por fin encontré algo que funciona con {producto}.",
    "Nadie me cree cuando digo que {producto} cambió mi rutina, pero mira esto.",
    "Deja de gastar dinero en lo mismo. Prueba {producto} y me lo agradeces.",
]

BENEFICIOS = [
    "Es súper fácil de usar, sin complicaciones, y los resultados se notan desde la primera semana.",
    "Lo recomiendo porque me ahorró tiempo y dinero, y llegó rapidísimo.",
    "Además es de muy buena calidad por su precio. A mí me convenció.",
]

CTAS = [
    "Pídelo hoy y llévatelo con descuento. Te dejo el enlace aquí abajo.",
    "Escríbele ahora mismo, el cupón vuela. Yo ya pedí el mío.",
    "Dale a comprar antes de que se agote. Si no te convence, tienes garantía.",
]

_WORDS_PER_SECOND = 2.5  # ritmo conversacional español ≈ 150 ppm


def estimate_duration(text: str) -> dict:
    words = len(re.findall(r"\S+", text or ""))
    seconds = round(words / _WORDS_PER_SECOND) if words else 0
    return {"words": words, "seconds": seconds}


def build_templates(product: str, campaign: str, tone: str = "conversacional") -> list[dict]:
    product = (product or "este producto").strip() or "este producto"
    problema = "buscas algo que realmente funcione"
    if campaign:
        problema = f"buscas lo que promete {campaign.strip()}"
    variants = []
    for i in range(3):
        hook = HOOKS[i % len(HOOKS)].format(producto=product, problema=problema)
        ben = BENEFICIOS[i % len(BENEFICIOS)]
        cta = CTAS[i % len(CTAS)]
        script = f"{hook} {ben} {cta}"
        est = estimate_duration(script)
        variants.append({
            "titulo": f"Variante {i + 1} ({tone})",
            "guion": script,
            "hook": hook,
            "cta": cta,
            "duracion_segundos": est["seconds"],
            "used_llm": False,
        })
    return variants


def _try_llm(product: str, campaign: str, tone: str) -> list[dict] | None:
    """Llama a un proveedor OpenAI-compatible si hay clave. None si no hay clave o falla."""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        import requests

        prompt = (
            "Eres un guionista UGC en español. Escribe 3 variantes de anuncio corto "
            f"(producto: {product}; campaña: {campaign}; tono: {tone}). "
            "Cada variante: hook de 3 segundos, 2 frases de beneficio y llamada a la acción. "
            "Devuelve SOLO JSON: [{\"titulo\":..,\"guion\":..,\"hook\":..,\"cta\":..}]"
        )
        r = requests.post(
            f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": settings.OPENAI_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.8},
            timeout=60,
        )
        if not r.ok:
            return None
        content = r.json()["choices"][0]["message"]["content"]
        import json as _json
        data = _json.loads(re.sub(r"^```json|```$", "", content.strip()))
        out = []
        for item in (data or [])[:3]:
            script = item.get("guion", "")
            out.append({
                "titulo": item.get("titulo", "Variante LLM"),
                "guion": script,
                "hook": item.get("hook", ""),
                "cta": item.get("cta", ""),
                "duracion_segundos": estimate_duration(script)["seconds"],
                "used_llm": True,
            })
        return out or None
    except Exception:
        return None  # No se simula: si falla, se usan plantillas y se indica used_llm=False.


def generate_scripts(product: str, campaign: str, tone: str = "conversacional") -> dict:
    if not (product or "").strip():
        raise ValueError("Indica el producto o servicio para generar guiones.")
    llm = _try_llm(product.strip(), (campaign or "").strip(), tone or "conversacional")
    variants = llm if llm else build_templates(product, campaign, tone)
    return {
        "variantes": variants,
        "provider": "LLM (OpenAI-compatible)" if llm else "Plantillas UGC locales",
        "nota": ("Generado con tu proveedor LLM." if llm else
                 "Sin API LLM configurada: guiones por plantilla editable. "
                 "Configura OPENAI_API_KEY en .env para usar un LLM real."),
    }
