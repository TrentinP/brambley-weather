#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORICAL = DATA / "historical" / "monthly_solar_resource_2020_2026.csv"
RESOURCE = DATA / "solar-resource.json"
MIN_MONTH_DAYS = 20

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def main() -> int:
    if not HISTORICAL.exists() or not RESOURCE.exists():
        raise SystemExit("Historical solar file or solar-resource.json is missing")

    with HISTORICAL.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    monthly_history = []
    weighted = defaultdict(lambda: {"energy_days": 0.0, "days": 0})

    for row in rows:
        month = row["month"]
        avg = float(row["average_daily_kwh_m2"])
        days = int(row["days_observed"])
        complete = row.get("complete_month", "").lower() == "true"
        monthly_history.append({
            "month": month,
            "average_daily_kwh_m2": round(avg, 3),
            "days_observed": days,
            "complete": complete,
        })
        if complete and days >= MIN_MONTH_DAYS:
            calendar_month = int(month[5:7])
            weighted[calendar_month]["energy_days"] += avg * days
            weighted[calendar_month]["days"] += days

    climatology = []
    eligible = []
    for month in range(1, 13):
        total_days = weighted[month]["days"]
        avg = (
            round(weighted[month]["energy_days"] / total_days, 3)
            if total_days else None
        )
        item = {
            "month": month,
            "month_name": MONTH_NAMES[month - 1],
            "average_daily_kwh_m2": avg,
            "days_observed": total_days,
            "eligible": total_days >= MIN_MONTH_DAYS,
        }
        climatology.append(item)
        if item["eligible"] and avg is not None:
            eligible.append(item)

    highest = max(eligible, key=lambda x: x["average_daily_kwh_m2"])
    lowest = min(eligible, key=lambda x: x["average_daily_kwh_m2"])

    payload = json.loads(RESOURCE.read_text(encoding="utf-8"))
    payload["historical_monthly"] = monthly_history
    payload["monthly_climatology"] = climatology
    payload["seasonal_records"] = {
        "minimum_complete_days_per_month": MIN_MONTH_DAYS,
        "ready": True,
        "highest": highest,
        "lowest": lowest,
        "method": "Weighted average of complete month-level daily solar-energy records from 2020 onward.",
    }
    payload["historical_method"] = (
        "Historical daily energy is derived from Ambient Weather daily mean solar radiation: "
        "mean W/m² × 24 h ÷ 1000. Month points are averages of those daily energy values."
    )
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    RESOURCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Added {len(monthly_history)} historical solar month records")
    print(f"Highest calendar month: {highest['month_name']} {highest['average_daily_kwh_m2']} kWh/m²/day")
    print(f"Lowest calendar month: {lowest['month_name']} {lowest['average_daily_kwh_m2']} kWh/m²/day")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
