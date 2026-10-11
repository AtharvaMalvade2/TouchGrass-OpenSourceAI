# 🌱 Plot Twist

**What to plant this week, worked out from 30 years of your local weather, with a garden card written by an open-weight model running on your own laptop.**

Built for the [Hacktoberfest Open-Source AI Challenge, Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

- **Frost dates as odds, not one date.** 30 years (1996–2025) of daily minimum temperatures for your exact spot give you the last spring frost in *half* of years and in *9 out of 10* years, and the same for the first fall frost.
- **This week's soil and frost.** The 7-day forecast and today's soil temperature at 6 cm. If the soil is too cold for a crop, it tells you to wait.
- **Works where it never frosts.** In places like Pune or Melbourne it switches to temperature and rainfall seasons and ranks crops by how well the next months suit them.
- **Southern hemisphere aware.** Seasons flip automatically.
- **A printable card.** Gemma 3 (4B) turns the numbers into a short checklist via Ollama. Print it, close the laptop, go outside.

## Run it

You need Python 3.10+ and [Ollama](https://ollama.com). No pip installs: it uses only the standard library.

```bash
ollama pull gemma3:4b
git clone https://github.com/AtharvaMalvade2/TouchGrass-OpenSourceAI.git
cd TouchGrass-OpenSourceAI
cd plottwist
python server.py
# open http://127.0.0.1:8000
```

Want a different model? `PLOTTWIST_MODEL=llama3.2:3b python server.py`. Any Ollama chat model works.

## How it works

```
 your town ──► Open-Meteo geocoding
             └► Open-Meteo archive: 30 yrs of daily min/max/rain ──► climate.py
                    frost dates (50% / 90%), monthly normals            (cached to disk)
             └► Open-Meteo forecast: 7 days + soil temp
                                   │
                              planner.py  (deterministic: crop windows relative to frost dates,
                                   │        soil-temperature checks, frost-free fallback)
                                   ▼
                     facts JSON ──► coach.py ──► Ollama /api/chat (gemma3:4b, local)
                                                     └► streamed weekly card
```

The model never decides dates. All dates and crop windows come from `plottwist/planner.py`, and the model only turns those facts into plain words. A small model on a laptop CPU handles that reliably.

After a place's first lookup, its climate is cached in `cache/`. With no internet you still get the frost calendar, the crop list and the Gemma card; only this week's forecast is missing.

## Limits

- Weather comes from a ~10 km reanalysis grid. A frost hollow at the bottom of your garden will be colder than the grid cell, which is why the app shows the cautious "9 in 10 years" date next to the median.
- A frost counts as ≤ 0 °C air temperature at 2 m. Ground frost can happen a few degrees above that.
- Crop windows are general guidance for about 30 common crops, not variety-specific.

## Credits

Weather data: [Open-Meteo](https://open-meteo.com) (CC BY 4.0). Model: [Gemma 3](https://ai.google.dev/gemma) via [Ollama](https://ollama.com).
