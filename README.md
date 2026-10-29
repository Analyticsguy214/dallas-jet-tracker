# Dallas Jet Tracker

Business-jet traffic at Dallas Love Field (DAL), Addison (ADS) and DFW, built from free community ADS-B data.

**Live site:** https://analyticsguy214.github.io/dallas-jet-tracker/

## How it works
- `scripts/track_jets.py` runs every 15 minutes via GitHub Actions
- Pulls aircraft within 30 nm of Dallas from airplanes.live (fallback: adsb.fi)
- Filters to ~65 business-jet types (Gulfstream, Citation, Challenger, Global, Phenom, Learjet, Falcon, etc.)
- Counts a "visit" when a jet is on the ground or below 2,000 ft within 3 nm of an airport, once per jet per airport per day
- `index.html` shows a live map, daily visits by airport, top jet types, and event-day comparisons

## Add events
Edit `data/events.json`:
```json
[
  { "date": "2026-11-26", "name": "Cowboys Thanksgiving game" },
  { "date": "2026-11-21", "name": "SMU home football" }
]
```
Event days get shaded on the chart and compared to the 30-day average.

## Privacy
- Aggregate counts only; no tail numbers or callsigns published
- Aircraft in the FAA PIA/LADD privacy programs are excluded
- Daily dedupe IDs are salted by date, so individual jets can't be followed across days

## Limitations
- ADS-B coverage near the ground depends on volunteer receivers, so counts are a lower bound
- 15-minute snapshots can miss quick turnarounds
- Type-code filter can't separate private vs. charter vs. fractional (NetJets, Flexjet) flights

## Data credits
[airplanes.live](https://airplanes.live) and [adsb.fi](https://adsb.fi), non-commercial use.
