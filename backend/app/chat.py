"""
Copiloto de Drift: chat sencillo con Groq (API compatible con OpenAI).
La clave (GROQ_API_KEY) vive solo en el servidor; el navegador nunca la ve.
"""

import json
import os

import requests

GROQ_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1") + "/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def _load_dotenv():
    """Lee GROQ_* de un .env en la raíz del proyecto (sin depender de python-dotenv)."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_dotenv()

SYSTEM_PROMPT = """Eres el Copiloto de Drift, un visor web de imágenes reales de la misión SPHEREx (NASA/IPAC IRSA).
Ayudas a entender lo que el usuario ve: modos Parpadeo, Deslizador, Diferencia y Suma; candidatos a objetos en movimiento; curvas de luz; espectros (0,75–5,0 µm); catálogos Gaia y WISE.
Reglas:
- Usa el "Estado actual de la vista" para responder. Si un dato no está ahí, di que no lo sabes con los datos actuales; no inventes cifras.
- Los detectados son "candidatos preliminares para revisión humana": nunca digas "descubrimos" ni "confirmado".
- Responde en el idioma de la pregunta, en máximo ~120 palabras, claro y sin jerga innecesaria.
- Si preguntan algo ajeno a astronomía o a Drift, redirige amablemente."""


def available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def ask(messages: list, context: dict) -> str:
    """messages: [{role: user|assistant, content: str}, ...] — devuelve el texto de la respuesta."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Falta GROQ_API_KEY en el servidor.")
    system = SYSTEM_PROMPT + "\n\nEstado actual de la vista:\n" + json.dumps(context, ensure_ascii=False)[:4000]
    clean = [{"role": m["role"], "content": str(m["content"])[:2000]}
             for m in messages[-12:] if m.get("role") in ("user", "assistant")]
    r = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": GROQ_MODEL, "messages": [{"role": "system", "content": system}] + clean,
              "temperature": 0.3, "max_tokens": 1200, "reasoning_effort": "low"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
