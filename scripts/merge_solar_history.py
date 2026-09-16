#!/usr/bin/env python3
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORY = DATA / "historical" / "solar_daily.json"
RESOURCE = DATA / "solar-resource.json"
MIN_DAYS = 20


def main():
    if not HISTORY.exists() or not RESOURCE.exists():
        return
    hist = json.loads(HISTORY.read_text(encoding="utf-8"))
    payload = json.loads(RESOURCE.read_text(encoding="utf-8"))

    merged = {}
    start = date.fromisoformat(hist["start_date"])
    for i, value in enumerate(hist.get("values", [])):
        if value is not None:
            d = (start + timedelta(days=i)).isoformat()
            merged[d] = {"date": d, "kwh_m2": round(float(value), 3), "complete": True, "source": "historical_export"}

    # Live collector becomes authoritative after the historical export ends.
    hist_end = start + timedelta(days=max(len(hist.get("values", [])) - 1, 0))
    for item in payload.get("daily", []):
        d = item.get("date")
        v = item.get("kwh_m2")
        if not d or v is None:
            continue
        if date.fromisoformat(d) > hist_end:
            merged[d] = {"date": d, "kwh_m2": round(float(v), 3), "complete": bool(item.get("complete")), "source": "live_station"}

    daily = [merged[k] for k in sorted(merged)]
    by_month = {m: [] for m in range(1, 13)}
    for item in daily:
        if item["complete"]:
            by_month[int(item["date"][5:7])].append(item["kwh_m2"])

    names = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    climatology = []
    eligible = []
    for m in range(1, 13):
        vals = by_month[m]
        avg = round(sum(vals) / len(vals), 3) if vals else None
        item = {"month": m, "month_name": names[m-1], "average_daily_kwh_m2": avg, "days_observed": len(vals), "eligible": len(vals) >= MIN_DAYS}
        climatology.append(item)
        if item["eligible"] and avg is not None:
            eligible.append(item)

    payload["daily"] = daily
    payload["monthly_climatology"] = climatology
    payload["seasonal_records"] = {
        "minimum_complete_days_per_month": MIN_DAYS,
        "ready": len(eligible) >= 2,
        "highest": max(eligible, key=lambda x: x["average_daily_kwh_m2"]) if len(eligible) >= 2 else None,
        "lowest": min(eligible, key=lambda x: x["average_daily_kwh_m2"]) if len(eligible) >= 2 else None,
    }
    payload["historical_record_start"] = hist["start_date"]
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    RESOURCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {len(daily)} daily solar-energy observations")


if __name__ == "__main__":
    main()
