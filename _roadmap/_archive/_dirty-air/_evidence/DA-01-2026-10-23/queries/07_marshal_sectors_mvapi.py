"""DA-01 step 7 (as run). Marshal-sector availability for 2018-2020 races.

FastF1's Session.get_circuit_info() could not be used: its first step, the F1
livetiming SessionInfo request, returns HTTP 401 from this machine (checked
2026-10-23), so session_info never loads. get_circuit_info() itself is a thin
wrapper over the MultiViewer circuit API (fastf1.mvapi), GET
https://api.multiviewer.app/api/v1/circuits/{circuitKey}/{year}, so this
probe calls that endpoint directly - the same source FastF1 would use.

Steps: fetch the circuit index; for each circuit key and each year 2018-2025
fetch the circuit JSON (saved under <scratch>/dl/, untrusted data, parsed
with json only); count corners, marshalLights, marshalSectors and check each
marshal sector carries trackPosition x/y. Then map each bronze race slug
2018-2020 to a circuit key (hand map below, by circuit) and report coverage.

Usage: python -I 07_marshal_sectors_mvapi.py <scratch_dir> <race_slugs.csv>
  race_slugs.csv: race_year,race_id,race_slug (from 07b_race_slugs query)
Writes <scratch>/out/07_marshal_sectors_by_circuit_year.csv and
       <scratch>/out/07_marshal_sectors_by_race_2018_2020.csv
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

scratch, slugs_csv = sys.argv[1], sys.argv[2]
dl = os.path.join(scratch, "dl")
os.makedirs(dl, exist_ok=True)
BASE = "https://api.multiviewer.app/api/v1/circuits"
UA = {"User-Agent": "off-the-pace DA-01 availability probe"}


def get(url, path):
    if os.path.exists(path):
        return 200, open(path, "rb").read()
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        return e.code, b""
    with open(path, "wb") as fh:
        fh.write(body)
    time.sleep(0.2)
    return code, body


code, body = get(BASE, os.path.join(dl, "circuits_index.json"))
index = json.loads(body)

# Bronze race slug -> MultiViewer circuit name (as it appears in the index).
SLUG_TO_CIRCUIT = {
    "australian_grand_prix": "Melbourne", "bahrain_grand_prix": "Sakhir",
    "sakhir_grand_prix": "Sakhir Outer Track", "chinese_grand_prix": "Shanghai",
    "azerbaijan_grand_prix": "Baku", "spanish_grand_prix": "Catalunya",
    "monaco_grand_prix": "Monte Carlo", "canadian_grand_prix": "Montreal",
    "french_grand_prix": "Paul Ricard", "austrian_grand_prix": "Spielberg",
    "styrian_grand_prix": "Spielberg", "british_grand_prix": "Silverstone",
    "70th_anniversary_grand_prix": "Silverstone", "german_grand_prix": "Hockenheim",
    "hungarian_grand_prix": "Hungaroring", "belgian_grand_prix": "Spa-Francorchamps",
    "italian_grand_prix": "Monza", "tuscan_grand_prix": "Mugello",
    "singapore_grand_prix": "Singapore", "russian_grand_prix": "Sochi",
    "japanese_grand_prix": "Suzuka", "united_states_grand_prix": "Austin",
    "mexican_grand_prix": "Mexico City", "brazilian_grand_prix": "Interlagos",
    "abu_dhabi_grand_prix": "Yas Marina Circuit", "eifel_grand_prix": "Nürburgring",
    "portuguese_grand_prix": "Algarve International Circuit", "emilia_romagna_grand_prix": "Imola",
    "turkish_grand_prix": "Istanbul",
}
name_to_key = {v["name"]: int(k) for k, v in index.items()}

rows = []
for key_s, meta in sorted(index.items(), key=lambda kv: int(kv[0])):
    for year in range(2018, 2026):
        code, body = get(f"{BASE}/{key_s}/{year}", os.path.join(dl, f"c{key_s}_{year}.json"))
        rec = {"circuit_key": int(key_s), "name": meta["name"], "year": year, "http": code,
               "index_lists_year": year in meta.get("years", []),
               "corners": "", "marshal_lights": "", "marshal_sectors": "", "ms_all_have_xy": ""}
        if code == 200 and body:
            try:
                d = json.loads(body)
                ms = d.get("marshalSectors") or []
                rec["corners"] = len(d.get("corners") or [])
                rec["marshal_lights"] = len(d.get("marshalLights") or [])
                rec["marshal_sectors"] = len(ms)
                rec["ms_all_have_xy"] = bool(ms) and all(
                    isinstance(m.get("trackPosition"), dict) and "x" in m["trackPosition"] and "y" in m["trackPosition"]
                    for m in ms)
            except ValueError:
                rec["http"] = f"{code} (not json)"
        rows.append(rec)

out1 = os.path.join(scratch, "out", "07_marshal_sectors_by_circuit_year.csv")
with open(out1, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

by = {(r["circuit_key"], r["year"]): r for r in rows}
race_rows = []
for r in csv.DictReader(open(slugs_csv)):
    y = int(r["race_year"])
    if y > 2020:
        continue
    cname = SLUG_TO_CIRCUIT.get(r["race_slug"])
    key = name_to_key.get(cname)
    hit = by.get((key, y)) if key is not None else None
    race_rows.append({
        "race_year": y, "race_id": r["race_id"], "race_slug": r["race_slug"],
        "circuit": cname, "circuit_key": key,
        "http": hit["http"] if hit else "unmapped",
        "marshal_sectors": hit["marshal_sectors"] if hit else "",
        "ms_all_have_xy": hit["ms_all_have_xy"] if hit else "",
    })
out2 = os.path.join(scratch, "out", "07_marshal_sectors_by_race_2018_2020.csv")
with open(out2, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(race_rows[0].keys()))
    w.writeheader()
    w.writerows(race_rows)
for rr in race_rows:
    print(rr)
print("wrote", out1, out2)
