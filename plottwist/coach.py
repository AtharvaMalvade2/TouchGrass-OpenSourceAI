"""Talks to a local open-weight model through Ollama. Nothing leaves the machine."""
import json
import os
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("PLOTTWIST_MODEL", "gemma3:4b")

SYSTEM = """You are a down-to-earth garden coach writing a weekly card someone will take outside.
Use ONLY the JSON facts you are given. Never invent dates, temperatures or crops that are not in the facts.
Write in this exact shape, under 200 words, plain markdown:

**This week in <place>:** two sentences on frost risk, soil temperature and rain, citing numbers from the facts.

**Outside this week**
- 4 to 6 checklist items. Start each with a verb. Name the crop and the action from plant_now.
  If a crop has a soil warning, say to wait. If frost_alert exists, the first item is protecting tender plants.

**Go look:** one small observation to make with your hands or eyes in the garden today
(e.g. squeeze a handful of soil, check under leaves, look for the first yellow leaves).

Do not add any other sections."""


def health():
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=3) as r:
            models = [m["name"] for m in json.load(r).get("models", [])]
    except OSError:
        return {"ollama": False, "model": MODEL, "model_ready": False}
    return {"ollama": True, "model": MODEL, "model_ready": any(m.startswith(MODEL) for m in models)}


def _slim(facts):
    """The model doesn't need 12 months of normals or raw numbers to write the card."""
    keep = {k: v for k, v in facts.items() if k not in ("monthly_normals", "frost_dates_raw")}
    if "forecast" in keep:
        keep["forecast"] = [{"date": d["date"], "min": d["tmin"], "max": d["tmax"], "rain": d["rain_mm"]}
                            for d in keep["forecast"]]
    keep["plant_now"] = keep["plant_now"][:10]
    keep["coming_up"] = keep["coming_up"][:5]
    return keep


def stream_brief(facts):
    """Yield text chunks of the weekly card as the model writes them."""
    body = json.dumps({
        "model": MODEL,
        "stream": True,
        "options": {"temperature": 0.4, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(_slim(facts), ensure_ascii=False)},
        ],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        for line in resp:
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("error"):
                raise RuntimeError(msg["error"])
            chunk = msg.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if msg.get("done"):
                break
