"""Snapshot business-jet traffic around Dallas airports (runs every 15 min via GitHub Actions).

Data: airplanes.live (primary) and adsb.fi (fallback), free community ADS-B feeds.
Privacy: aggregate counts only. No tail numbers or callsigns are published, aircraft in the
FAA's privacy programs (PIA/LADD) are skipped, and daily dedupe IDs are salted per day.
"""
import hashlib, json, math, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CENTER = (32.92, -96.92)
RADIUS_NM = 30
SOURCES = [
    "https://api.airplanes.live/v2/point/{lat}/{lon}/{r}",
    "https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/{r}",
]
AIRPORTS = {
    "DAL": {"name": "Dallas Love Field", "lat": 32.8471, "lon": -96.8518, "elev": 487},
    "ADS": {"name": "Addison", "lat": 32.9686, "lon": -96.8364, "elev": 644},
    "DFW": {"name": "DFW International", "lat": 32.8998, "lon": -97.0403, "elev": 607},
}
VISIT_RADIUS_NM = 3
VISIT_MAX_AGL_FT = 2000

BIZJETS = {
    "GLF4": "Gulfstream G-IV", "GLF5": "Gulfstream G550", "GLF6": "Gulfstream G650",
    "GA5C": "Gulfstream G500", "GA6C": "Gulfstream G600", "GA7C": "Gulfstream G700",
    "GA8C": "Gulfstream G800", "G280": "Gulfstream G280", "GALX": "Gulfstream G200",
    "G150": "Gulfstream G150", "ASTR": "Gulfstream G100/Astra",
    "C510": "Citation Mustang", "C525": "Citation CJ", "C25A": "Citation CJ2",
    "C25B": "Citation CJ3", "C25C": "Citation CJ4", "C25M": "Citation M2",
    "C550": "Citation II/Bravo", "C560": "Citation V/Encore", "C56X": "Citation Excel/XLS",
    "C650": "Citation III/VII", "C680": "Citation Sovereign", "C68A": "Citation Latitude",
    "C700": "Citation Longitude", "C750": "Citation X",
    "CL30": "Challenger 300", "CL35": "Challenger 350", "CL60": "Challenger 600/650",
    "GLEX": "Global Express", "GL5T": "Global 5000/5500", "GL6T": "Global 6000/6500",
    "GL7T": "Global 7500",
    "E50P": "Phenom 100", "E55P": "Phenom 300", "E545": "Praetor 500", "E550": "Praetor 600",
    "E35L": "Legacy 600/650",
    "LJ31": "Learjet 31", "LJ35": "Learjet 35", "LJ40": "Learjet 40", "LJ45": "Learjet 45",
    "LJ60": "Learjet 60", "LJ75": "Learjet 75",
    "FA10": "Falcon 10", "FA20": "Falcon 20", "FA50": "Falcon 50", "F900": "Falcon 900",
    "F2TH": "Falcon 2000", "FA7X": "Falcon 7X", "FA8X": "Falcon 8X", "FA6X": "Falcon 6X",
    "H25B": "Hawker 800", "H25C": "Hawker 1000", "HA4T": "Hawker 4000", "BE40": "Hawker 400",
    "PRM1": "Premier I", "WW24": "Westwind",
    "PC24": "Pilatus PC-24", "HDJT": "HondaJet", "SF50": "Cirrus Vision Jet", "EA50": "Eclipse 500",
}
PRIVACY_FLAGS = 4 | 8  # readsb dbFlags: 4 = PIA, 8 = LADD

DATA = Path(__file__).resolve().parent.parent / "data"
TZ = ZoneInfo("America/Chicago")


def nm_between(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 3440.065 * 2 * math.asin(math.sqrt(a))


def fetch_aircraft():
    last_err = None
    for url in SOURCES:
        u = url.format(lat=CENTER[0], lon=CENTER[1], r=RADIUS_NM)
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "dallas-jet-tracker (student project)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.load(r)
            ac = body.get("ac") or body.get("aircraft") or []
            return ac, u.split("/")[2]
        except Exception as e:
            last_err = e
            print(f"{u}: {e}")
    raise SystemExit(f"All sources failed: {last_err}")


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, indent=1, sort_keys=True))


def main():
    DATA.mkdir(exist_ok=True)
    now = datetime.now(TZ)
    today = now.date().isoformat()
    aircraft, source = fetch_aircraft()

    state = load("state.json", {})
    if state.get("date") != today:
        state = {"date": today, "seen": {code: [] for code in AIRPORTS}}
    daily = load("daily.json", {})
    day = daily.setdefault(today, {"DAL": 0, "ADS": 0, "DFW": 0, "types": {}})

    live = []
    for a in aircraft:
        t = a.get("t")
        if t not in BIZJETS or a.get("lat") is None or a.get("lon") is None:
            continue
        if (a.get("dbFlags") or 0) & PRIVACY_FLAGS:
            continue
        alt = a.get("alt_baro")
        on_ground = alt == "ground"
        near = None
        for code, ap in AIRPORTS.items():
            if nm_between(a["lat"], a["lon"], ap["lat"], ap["lon"]) > VISIT_RADIUS_NM:
                continue
            if on_ground or (isinstance(alt, (int, float)) and alt - ap["elev"] <= VISIT_MAX_AGL_FT):
                near = code
                break
        if near and a.get("hex"):
            vid = hashlib.sha256(f"{today}:{a['hex']}".encode()).hexdigest()[:12]
            if vid not in state["seen"][near]:
                state["seen"][near].append(vid)
                day[near] += 1
                day["types"][t] = day["types"].get(t, 0) + 1
        live.append({
            "lat": round(a["lat"], 3), "lon": round(a["lon"], 3), "type": t,
            "alt": "ground" if on_ground else alt, "gs": a.get("gs"),
            "track": a.get("track"), "nearAirport": near,
        })

    save("state.json", state)
    save("daily.json", daily)
    save("live.json", {
        "updated": now.isoformat(timespec="minutes"), "source": source,
        "aircraft": live, "airports": AIRPORTS, "typeNames": BIZJETS,
    })
    print(f"{now:%H:%M} via {source}: {len(live)} bizjets in area, today {day}")


if __name__ == "__main__":
    main()
