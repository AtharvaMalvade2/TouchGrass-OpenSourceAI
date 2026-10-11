"""Turn frost dates + this week's forecast into concrete "do this outside now" actions.

Everything here is deterministic. The language model only explains these facts; it never invents dates.
"""
import datetime as dt

from climate import season_date, season_day

W = 7  # days per week

# Windows are in weeks relative to a reference date:
#   "lf50" = median last spring frost, "lf90" = date after which 9 years in 10 are frost-free.
# fall=True means the crop can also be sown late in the season to harvest before / through frost.
# trop = (min, max) monthly mean °C a crop is happy in, used where it never frosts.
CROPS = [
    # warm-season, frost-tender
    {"name": "Tomato", "emoji": "🍅", "indoor": (-8, -6), "out": ("Transplant", 0, 5, "lf90"), "soil": 16, "dtm": 75, "trop": (18, 30)},
    {"name": "Chilli / pepper", "emoji": "🌶️", "indoor": (-10, -8), "out": ("Transplant", 1, 5, "lf90"), "soil": 18, "dtm": 80, "trop": (20, 32)},
    {"name": "Eggplant / brinjal", "emoji": "🍆", "indoor": (-9, -7), "out": ("Transplant", 1, 5, "lf90"), "soil": 18, "dtm": 80, "trop": (22, 32)},
    {"name": "Basil", "emoji": "🌿", "indoor": (-6, -4), "out": ("Transplant", 1, 6, "lf90"), "soil": 18, "dtm": 50, "trop": (20, 32)},
    {"name": "Cucumber", "emoji": "🥒", "out": ("Direct sow", 1, 7, "lf90"), "soil": 16, "dtm": 55, "trop": (20, 32)},
    {"name": "Zucchini / squash", "emoji": "🥬", "out": ("Direct sow", 1, 6, "lf90"), "soil": 16, "dtm": 50, "trop": (18, 32)},
    {"name": "Bush beans", "emoji": "🫘", "out": ("Direct sow", 0, 8, "lf90"), "soil": 16, "dtm": 55, "fall": True, "trop": (18, 30)},
    {"name": "Sweet corn", "emoji": "🌽", "out": ("Direct sow", 1, 5, "lf90"), "soil": 16, "dtm": 80, "trop": (20, 32)},
    {"name": "Okra", "emoji": "🌱", "out": ("Direct sow", 2, 6, "lf90"), "soil": 20, "dtm": 60, "trop": (24, 34)},
    {"name": "Pumpkin", "emoji": "🎃", "out": ("Direct sow", 1, 4, "lf90"), "soil": 16, "dtm": 100, "trop": (20, 32)},
    {"name": "Amaranth", "emoji": "🌾", "out": ("Direct sow", 1, 6, "lf90"), "soil": 18, "dtm": 40, "trop": (22, 34)},
    {"name": "Marigold", "emoji": "🌼", "indoor": (-6, -4), "out": ("Transplant", 0, 6, "lf90"), "soil": 15, "dtm": 60, "trop": (18, 32)},
    {"name": "Sunflower", "emoji": "🌻", "out": ("Direct sow", 0, 6, "lf90"), "soil": 10, "dtm": 80, "trop": (18, 32)},
    # cool-season, frost-hardy
    {"name": "Peas", "emoji": "🫛", "out": ("Direct sow", -6, -2, "lf50"), "soil": 5, "dtm": 60, "fall": True, "trop": (12, 22)},
    {"name": "Spinach", "emoji": "🥬", "out": ("Direct sow", -6, -2, "lf50"), "soil": 5, "dtm": 40, "fall": True, "trop": (10, 22)},
    {"name": "Lettuce", "emoji": "🥗", "indoor": (-6, -4), "out": ("Direct sow", -4, 2, "lf50"), "soil": 5, "dtm": 45, "fall": True, "trop": (12, 24)},
    {"name": "Radish", "emoji": "🔴", "out": ("Direct sow", -5, 1, "lf50"), "soil": 5, "dtm": 25, "fall": True, "trop": (10, 26)},
    {"name": "Carrot", "emoji": "🥕", "out": ("Direct sow", -3, 3, "lf50"), "soil": 7, "dtm": 70, "fall": True, "trop": (12, 26)},
    {"name": "Beetroot", "emoji": "🟣", "out": ("Direct sow", -3, 3, "lf50"), "soil": 7, "dtm": 55, "fall": True, "trop": (12, 26)},
    {"name": "Kale", "emoji": "🥬", "indoor": (-8, -6), "out": ("Transplant", -4, 0, "lf50"), "soil": 7, "dtm": 55, "fall": True, "trop": (10, 24)},
    {"name": "Broccoli", "emoji": "🥦", "indoor": (-8, -6), "out": ("Transplant", -2, 1, "lf50"), "soil": 7, "dtm": 70, "fall": True, "trop": (12, 24)},
    {"name": "Cabbage", "emoji": "🥬", "indoor": (-8, -6), "out": ("Transplant", -4, 0, "lf50"), "soil": 7, "dtm": 70, "fall": True, "trop": (10, 24)},
    {"name": "Onion", "emoji": "🧅", "indoor": (-12, -10), "out": ("Transplant", -4, -2, "lf50"), "soil": 7, "dtm": 100, "trop": (13, 26)},
    {"name": "Potato", "emoji": "🥔", "out": ("Plant seed potatoes", -3, 1, "lf50"), "soil": 7, "dtm": 90, "trop": (15, 25)},
    {"name": "Coriander / cilantro", "emoji": "🌿", "out": ("Direct sow", -2, 2, "lf50"), "soil": 10, "dtm": 45, "fall": True, "trop": (12, 26)},
    {"name": "Fenugreek / methi", "emoji": "🌿", "out": ("Direct sow", -2, 3, "lf50"), "soil": 10, "dtm": 30, "fall": True, "trop": (12, 26)},
    {"name": "Mustard greens", "emoji": "🥬", "out": ("Direct sow", -4, 1, "lf50"), "soil": 7, "dtm": 40, "fall": True, "trop": (12, 25)},
    # fall-only plantings, relative to the median first fall frost
    {"name": "Garlic", "emoji": "🧄", "autumn": ("Plant cloves", -2, 4), "trop": (12, 22), "soil": 0, "dtm": 240},
    {"name": "Winter rye cover crop", "emoji": "🌾", "autumn": ("Sow cover crop", -6, 2), "soil": 0, "dtm": 0},
]


def _in_window(today_doy, start, end):
    """True if today falls in [start, end] (day-of-season numbers that may spill past a year boundary)."""
    return any(start <= today_doy + shift <= end for shift in (-365, 0, 365))


def _fmt(d):
    return f"{d:%b} {d.day}"


def _windows_for(crop, c):
    """All (action, start_doy, end_doy) windows for a crop in a frosty climate."""
    refs = {"lf50": c["last_frost_50"], "lf90": c["last_frost_90"]}
    out = []
    if "indoor" in crop:
        a, b = crop["indoor"]
        out.append(("Sow indoors", c["last_frost_50"] + a * W, c["last_frost_50"] + b * W))
    if "out" in crop:
        action, a, b, ref = crop["out"]
        start, end = refs[ref] + a * W, refs[ref] + b * W
        # Never plant tender crops so late they can't mature before the first fall frost.
        if ref == "lf90":
            end = min(end, c["first_frost_10"] - crop["dtm"])
        if end >= start:
            out.append((action, start, end))
    if crop.get("fall"):
        hardy = crop.get("trop", (0, 99))[0] < 16   # cool-season crops shrug off light frost
        latest = (c["first_frost_50"] + W if hardy else c["first_frost_10"]) - crop["dtm"]
        earliest = latest - 4 * W
        spring_end = out[-1][2] if out else 0
        if latest > spring_end + 2 * W:
            out.append(("Sow for fall harvest", max(earliest, spring_end + W), latest))
    if "autumn" in crop:
        action, a, b = crop["autumn"]
        out.append((action, c["first_frost_50"] + a * W, c["first_frost_50"] + b * W))
    return out


def _season_dates(c, season_year):
    to_date = lambda doy: season_date(season_year, doy, c["south"])
    return {
        "last_frost_50": to_date(c["last_frost_50"]),
        "last_frost_90": to_date(c["last_frost_90"]),
        "first_frost_50": to_date(c["first_frost_50"]),
        "first_frost_10": to_date(c["first_frost_10"]),
    }


def plan_frosty(c, today, soil_c):
    season_year, today_doy = season_day(today, c["south"])
    now, soon = [], []
    for crop in CROPS:
        for action, start, end in _windows_for(crop, c):
            # Pick the copy of the window (this season / next / previous) closest to today.
            shift = min((-365, 0, 365), key=lambda s: abs((start + end) / 2 - (today_doy + s)))
            s_date = season_date(season_year, start - shift, c["south"])
            e_date = season_date(season_year, end - shift, c["south"])
            item = {
                "crop": crop["name"], "emoji": crop["emoji"], "action": action,
                "window": f"{_fmt(s_date)} – {_fmt(e_date)}",
                "closes_in_days": (e_date - today).days,
            }
            if action != "Sow indoors" and soil_c is not None and soil_c < crop.get("soil", 0):
                item["warning"] = f"Soil is {soil_c}°C; {crop['name'].lower()} wants {crop['soil']}°C+. Wait or warm the bed."
            if _in_window(today_doy, start, end):
                now.append(item)
            elif 0 < (s_date - today).days <= 21:
                item["opens_in_days"] = (s_date - today).days
                soon.append(item)
    now.sort(key=lambda x: x["closes_in_days"])
    soon.sort(key=lambda x: x["opens_in_days"])
    dates = {k: _fmt(v) for k, v in _season_dates(c, season_year).items()}
    return now, soon, dates


def plan_frost_free(c, today):
    """No reliable frost: choose crops whose temperature range fits the next ~3 months."""
    months = c["monthly"]
    mean = lambda m: (months[(m - 1) % 12]["tmin"] + months[(m - 1) % 12]["tmax"]) / 2
    now, soon = [], []
    for crop in CROPS:
        if "trop" not in crop:
            continue
        lo, hi = crop["trop"]
        span = max(1, round(crop["dtm"] / 30))
        fits = lambda start: all(lo <= mean(start + k) <= hi for k in range(span))
        action = "Sow in trays" if "indoor" in crop or crop.get("out", ("",))[0] == "Transplant" else "Sow outside"
        if crop.get("autumn"):
            action = crop["autumn"][0]
            # Spring and autumn can have the same temperature; garlic only goes in while it's cooling down.
            cooling = lambda m: mean(m + 1) < mean(m)
            fits = lambda start, f=fits: f(start) and cooling(start)
        item = {"crop": crop["name"], "emoji": crop["emoji"], "action": action}
        if fits(today.month):
            # How snugly the coming months sit in the crop's comfort zone (0 = dead centre).
            centre = (lo + hi) / 2
            item["fit"] = round(sum(abs(mean(today.month + k) - centre) for k in range(span)) / span / (hi - lo), 2)
            temps = [round(mean(today.month + k)) for k in range(span)]
            item["why"] = (f"Next {span} month{'s' * (span > 1)} average {min(temps)}–{max(temps)}°C, "
                           f"inside its {lo}–{hi}°C comfort zone")
            if action == "Sow in trays":
                item["why"] += "; transplant in 3–4 weeks"
            now.append(item)
        elif fits(today.month + 1):
            item["opens_in_days"] = (dt.date(today.year + (today.month == 12), today.month % 12 + 1, 1) - today).days
            soon.append(item)
    now.sort(key=lambda x: x["fit"])
    return now, soon


def build_plan(c, fc, today, place):
    soil_c = fc["soil_c"] if fc else None
    facts = {
        "place": place,
        "today": today.isoformat(),
        "hemisphere": "southern" if c["south"] else "northern",
        "years_of_data": c["years"],
        "soil_temp_c": soil_c,
        "monthly_normals": c["monthly"],
    }
    if c.get("frost_free"):
        now, soon = plan_frost_free(c, today)
        facts["frost_free"] = True
        m = c["monthly"][today.month - 1]
        facts["this_month_normal"] = m
        if m["rain_mm"] > 250:
            facts["heavy_rain_month"] = True
    else:
        now, soon, dates = plan_frosty(c, today, soil_c)
        facts.update({"frost_free": False, "frost_dates": dates, "frost_free_days": c["frost_free_days_50"]})
        facts["frost_dates_raw"] = {k: c[k] for k in ("last_frost_50", "last_frost_90", "first_frost_50", "first_frost_10")}
        facts["frost_dates_raw"]["today"] = season_day(today, c["south"])[1]

    if fc:
        days = fc["days"]
        facts["forecast"] = days
        cold = [d for d in days if d["tmin"] is not None and d["tmin"] <= 1.0]
        if cold:
            facts["frost_alert"] = [d["date"] for d in cold]
        facts["rain_next_7_days_mm"] = round(sum(d["rain_mm"] or 0 for d in days), 1)
    else:
        facts["offline"] = True

    facts["plant_now"] = now
    facts["coming_up"] = soon
    return facts
