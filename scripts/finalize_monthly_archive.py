#!/usr/bin/env python3
from __future__ import annotations

import calendar
import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DAILY_DIR = DATA / "daily"
HIST_DIR = DATA / "historical"
HIST_DAILY_DIR = HIST_DIR / "daily"
BRAMBLEY_TZ = ZoneInfo("America/Los_Angeles")
MIN_VALID_TEMP_DAYS = 20

HIST_DAILY_FIELDS = [
    "date", "avg_c", "high_c", "low_c", "rain_mm", "gust_kn",
    "pressure_hpa", "humidity_pct", "uv_max", "solar_avg_w_m2",
    "solar_max_w_m2", "solar_energy_kwh_m2", "wind_avg_kn",
    "observation_count",
]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def value(row: dict, *keys: str) -> str:
    for key in keys:
        v = row.get(key)
        if v not in (None, ""):
            return str(v)
    return ""


def number(v: str | None) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_historical(row: dict) -> dict:
    return {
        "date": value(row, "date", "date_local"),
        "avg_c": value(row, "avg_c", "temperature_avg_c"),
        "high_c": value(row, "high_c", "temperature_high_c"),
        "low_c": value(row, "low_c", "temperature_low_c"),
        "rain_mm": value(row, "rain_mm", "rain_total_mm"),
        "gust_kn": value(row, "gust_kn", "peak_gust_kn"),
        "pressure_hpa": value(row, "pressure_hpa", "pressure_avg_hpa"),
        "humidity_pct": value(row, "humidity_pct", "humidity_avg_pct"),
        "uv_max": value(row, "uv_max"),
        "solar_avg_w_m2": value(row, "solar_avg_w_m2"),
        "solar_max_w_m2": value(row, "solar_max_w_m2", "solar_peak_w_m2"),
        "solar_energy_kwh_m2": value(row, "solar_energy_kwh_m2"),
        "wind_avg_kn": value(row, "wind_avg_kn"),
        "observation_count": value(row, "observation_count"),
    }


def merge_nonblank(base: dict, incoming: dict) -> dict:
    out = dict(base)
    for key, val in incoming.items():
        if val not in (None, ""):
            out[key] = val
    return out


def fmt(v: float, digits: int = 2) -> str:
    text = f"{v:.{digits}f}"
    return text.rstrip("0").rstrip(".")


def upsert_month(path: Path, fieldnames: list[str], month: str, values: dict) -> None:
    rows = read_csv(path)
    found = False
    for row in rows:
        if row.get("month") == month:
            row.update(values)
            found = True
            break
    if not found:
        rows.append({"month": month, **values})
    rows.sort(key=lambda r: r.get("month", ""))
    write_csv(path, fieldnames, rows)


def finalize_month(month_path: Path) -> bool:
    ym = month_path.stem
    year, month_num = map(int, ym.split("-"))
    hist_path = HIST_DAILY_DIR / f"{year}.csv"

    merged: dict[str, dict] = {}
    for row in read_csv(hist_path):
        n = normalize_historical(row)
        if n["date"]:
            merged[n["date"]] = n

    for row in read_csv(month_path):
        n = normalize_historical(row)
        if n["date"]:
            merged[n["date"]] = merge_nonblank(merged.get(n["date"], {}), n)

    month_rows = [r for d, r in sorted(merged.items()) if d.startswith(ym + "-")]
    if not month_rows:
        return False

    write_csv(hist_path, HIST_DAILY_FIELDS, [merged[d] for d in sorted(merged)])

    highs = [v for r in month_rows if (v := number(r.get("high_c"))) is not None]
    lows = [v for r in month_rows if (v := number(r.get("low_c"))) is not None]

    if len(highs) >= MIN_VALID_TEMP_DAYS and len(lows) >= MIN_VALID_TEMP_DAYS:
        upsert_month(
            HIST_DIR / "monthly_temperature_2007_2026.csv",
            ["month", "max_c", "avg_high_c", "min_c", "avg_low_c"],
            ym,
            {
                "max_c": fmt(max(highs)),
                "avg_high_c": fmt(sum(highs) / len(highs)),
                "min_c": fmt(min(lows)),
                "avg_low_c": fmt(sum(lows) / len(lows)),
            },
        )
    else:
        print(f"{ym}: temperature not finalized ({len(highs)} valid high days, {len(lows)} valid low days)")

    rains = [number(r.get("rain_mm")) for r in month_rows]
    expected_days = calendar.monthrange(year, month_num)[1]
    if len(month_rows) == expected_days and all(v is not None for v in rains):
        upsert_month(
            HIST_DIR / "monthly_rainfall_2020_2026.csv",
            ["month", "monthly_rain_mm", "workbook_delta_mm"],
            ym,
            {
                "monthly_rain_mm": fmt(sum(v for v in rains if v is not None), 3),
                "workbook_delta_mm": "",
            },
        )
    else:
        valid_rain = sum(v is not None for v in rains)
        print(f"{ym}: rainfall not finalized ({len(month_rows)}/{expected_days} days, {valid_rain} valid rainfall days)")

    print(f"{ym}: archived {len(month_rows)} daily records")
    return True


def main() -> int:
    current_month = datetime.now(BRAMBLEY_TZ).strftime("%Y-%m")
    completed = [
        p for p in sorted(DAILY_DIR.glob("????-??.csv"))
        if p.stem < current_month
    ]
    changed = 0
    for path in completed:
        changed += int(finalize_month(path))
    print(f"Finalized {changed} completed month(s) through {current_month}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
