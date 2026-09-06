#!/usr/bin/env python3
"""Turn the individual response files into one responses.csv.

Runs automatically in GitHub Actions whenever a new response arrives, and works
the same if you run it locally after downloading the repo:

    python3 collate.py

One row per respondent. Columns: email, timestamps, timing, then a1..a50 and
b1..b48 holding the raw 1-5 answers. Scoring is deliberately not done here --
SCORING-KEY.csv has what you need when you want it.
"""
import csv, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
N_A, N_B = 50, 48
cols = (["id", "received_at", "email", "elapsed_ms", "client_time", "tz", "country", "user_agent"]
        + [f"a{i}" for i in range(1, N_A + 1)] + [f"b{i}" for i in range(1, N_B + 1)])

rows = []
for f in sorted((HERE / "responses").glob("*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"skipping unreadable file: {f.name}")
        continue
    a = d.get("answers", {})
    row = {c: d.get(c) for c in cols[:8]}
    row.update({k: a.get(k, "") for k in cols[8:]})
    row["answered"] = sum(1 for k in cols[8:] if a.get(k) is not None)
    rows.append(row)

out = HERE / "responses.csv"
with out.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols + ["answered"])
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} responses -> {out.name}")
