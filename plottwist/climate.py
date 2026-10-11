"""Frost dates and climate normals from 30 years of daily weather (Open-Meteo, no API key).

Results are cached to disk so a location only needs the internet once.
"""
import datetime as dt
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

FIRST_YEAR, LAST_YEAR = 1996, 2025
FROST_C = 0.0          # daily minimum air temperature at 2 m that counts as a frost
SOUTH_SHIFT = 182      # days to shift southern-hemisphere dates so "spring" lands in Jan-Jul
MID_SEASON_DOY = 197   # ~mid July (in shifted terms): splits spring frosts from fall frosts


def _get_json(url, params, timeout=60, retries=2):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": "PlotTwist/1.0"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            # 30 years of history is a "heavy" request for the free API; back off and retry.
            if e.code != 429 or attempt == retries:
                raise
            time.sleep(20 * (attempt + 1))


def geocode(query):
    data = _get_json(GEOCODE_URL, {"name": query, "count": 5, "language": "en", "format": "json"}, timeout=15)
    return [
        {
            "name": r["name"],
            "region": ", ".join(x for x in (r.get("admin1"), r.get("country")) if x),
            "lat": r["latitude"],
            "lon": r["longitude"],
        }
        for r in data.get("results", [])
    ]


def _cache_path(lat, lon):
    return CACHE_DIR / f"climate_{lat:.2f}_{lon:.2f}.json"


def _fetch_history(lat, lon):
    data = _get_json(ARCHIVE_URL, {
        "latitude": lat, "longitude": lon,
        "start_date": f"{FIRST_YEAR}-01-01", "end_date": f"{LAST_YEAR}-12-31",
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
        "timezone": "auto",
    }, timeout=120)
    return data["daily"]


def _percentile(values, p):
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _summarise(daily, south):
    last_spring, first_fall = {}, {}
    month_tmin = {m: [] for m in range(1, 13)}
    month_tmax = {m: [] for m in range(1, 13)}
    month_rain = {}  # (year, month) -> total

    for day, tmin, tmax, rain in zip(daily["time"], daily["temperature_2m_min"],
                                     daily["temperature_2m_max"], daily["precipitation_sum"]):
        if tmin is None or tmax is None:
            continue
        d = dt.date.fromisoformat(day)
        month_tmin[d.month].append(tmin)
        month_tmax[d.month].append(tmax)
        month_rain[(d.year, d.month)] = month_rain.get((d.year, d.month), 0.0) + (rain or 0.0)

        s = d + dt.timedelta(days=SOUTH_SHIFT) if south else d
        year, doy = s.year, s.timetuple().tm_yday
        last_spring.setdefault(year, None)
        first_fall.setdefault(year, None)
        if tmin <= FROST_C:
            if doy < MID_SEASON_DOY:
                last_spring[year] = doy
            elif first_fall[year] is None:
                first_fall[year] = doy

    # Only use season-years fully covered by the data.
    years = [y for y in last_spring if (FIRST_YEAR + (1 if south else 0)) <= y <= LAST_YEAR]
    spring = [last_spring[y] for y in years]
    fall = [first_fall[y] for y in years]
    frost_years = sum(1 for v in spring if v is not None) + sum(1 for v in fall if v is not None)
    frost_share = frost_years / (2 * len(years)) if years else 0

    monthly = []
    for m in range(1, 13):
        rains = [v for (y, mm), v in month_rain.items() if mm == m]
        monthly.append({
            "month": m,
            "tmin": round(statistics.mean(month_tmin[m]), 1),
            "tmax": round(statistics.mean(month_tmax[m]), 1),
            "rain_mm": round(statistics.mean(rains)) if rains else 0,
        })

    result = {"south": south, "years": len(years), "frost_share": round(frost_share, 2), "monthly": monthly}
    if frost_share < 0.2:
        result["frost_free"] = True
        return result

    # A year with no spring frost counts as "frost ended on day 0"; no fall frost as "day 366".
    spring_vals = [v if v is not None else 0 for v in spring]
    fall_vals = [v if v is not None else 366 for v in fall]
    result.update({
        "frost_free": False,
        # Day-of-season numbers; converted to real dates per request.
        "last_frost_50": round(_percentile(spring_vals, 0.5)),
        "last_frost_90": round(_percentile(spring_vals, 0.9)),   # only 1 year in 10 frosts later
        "first_frost_50": round(_percentile(fall_vals, 0.5)),
        "first_frost_10": round(_percentile(fall_vals, 0.1)),   # only 1 year in 10 frosts earlier
        "frost_free_days_50": round(_percentile(fall_vals, 0.5) - _percentile(spring_vals, 0.5)),
    })
    return result


def climate(lat, lon):
    path = _cache_path(lat, lon)
    if path.exists():
        return json.loads(path.read_text())
    summary = _summarise(_fetch_history(lat, lon), south=lat < 0)
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(summary))
    return summary


def season_day(date, south):
    """(season_year, day_of_season) for a calendar date. For the south, the season starts ~July 1."""
    s = date + dt.timedelta(days=SOUTH_SHIFT) if south else date
    return s.year, s.timetuple().tm_yday


def season_date(season_year, doy, south):
    """Inverse of season_day: the calendar date of a day-of-season number."""
    d = dt.date(season_year, 1, 1) + dt.timedelta(days=doy - 1)
    return d - dt.timedelta(days=SOUTH_SHIFT) if south else d


def forecast(lat, lon):
    """Next 7 days of min/max temperature and rain, plus today's soil temperature. None when offline."""
    try:
        data = _get_json(FORECAST_URL, {
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
            "hourly": "soil_temperature_6cm",
            "forecast_days": 7, "timezone": "auto",
        }, timeout=15)
    except OSError:
        return None
    daily = data["daily"]
    soil = [v for v in data["hourly"]["soil_temperature_6cm"][:24] if v is not None]
    return {
        "days": [
            {"date": d, "tmin": lo, "tmax": hi, "rain_mm": r}
            for d, lo, hi, r in zip(daily["time"], daily["temperature_2m_min"],
                                    daily["temperature_2m_max"], daily["precipitation_sum"])
        ],
        "soil_c": round(statistics.mean(soil), 1) if soil else None,
    }
