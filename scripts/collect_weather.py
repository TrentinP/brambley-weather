#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

API_ROOT = "https://rt.ambientweather.net/v1"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OBS_DIR = DATA / "observations"
DAILY_DIR = DATA / "daily"

MPH_TO_KNOTS = 0.8689762419
INHG_TO_HPA = 33.8638866667
IN_TO_MM = 25.4

OBS_FIELDS = [
    "timestamp_utc", "timestamp_local", "station_name",
    "temperature_c", "feels_like_c", "dew_point_c", "humidity_pct",
    "pressure_relative_hpa", "pressure_absolute_hpa",
    "wind_speed_kn", "wind_gust_kn", "max_daily_gust_kn",
    "wind_direction_deg", "wind_direction_compass",
    "rain_rate_mm_hr", "rain_daily_mm", "rain_event_mm",
    "rain_monthly_mm", "rain_yearly_mm",
    "solar_radiation_w_m2", "uv_index",
]

DAILY_FIELDS = [
    "date_local", "temperature_avg_c", "temperature_high_c", "temperature_low_c",
    "humidity_avg_pct", "pressure_avg_hpa", "wind_avg_kn", "peak_gust_kn",
    "rain_total_mm", "solar_peak_w_m2", "solar_energy_kwh_m2",
    "observation_count",
]


def number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except (TypeError, ValueError):
        pass
    return None


def f_to_c(value: Any) -> float | None:
    v = number(value)
    return None if v is None else (v - 32.0) * 5.0 / 9.0


def in_to_mm(value: Any) -> float | None:
    v = number(value)
    return None if v is None else v * IN_TO_MM


def inhg_to_hpa(value: Any) -> float | None:
    v = number(value)
    return None if v is None else v * INHG_TO_HPA


def mph_to_knots(value: Any) -> float | None:
    v = number(value)
    return None if v is None else v * MPH_TO_KNOTS


def compass(degrees: Any) -> str | None:
    d = number(degrees)
    if d is None:
        return None
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[int((d % 360) / 22.5 + 0.5) % 16]


def clean(value: Any, digits: int = 2) -> Any:
    return round(value, digits) if isinstance(value, float) else value


def get_devices(api_key: str, app_key: str) -> list[dict]:
    response = requests.get(
        f"{API_ROOT}/devices",
        params={"apiKey": api_key, "applicationKey": app_key},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("Ambient API returned an unexpected device response.")
    return payload


def choose_device(devices: list[dict], requested_mac: str | None) -> dict:
    if requested_mac:
        wanted = requested_mac.lower().replace("-", ":")
        for device in devices:
            mac = str(device.get("macAddress", "")).lower().replace("-", ":")
            if mac == wanted:
                return device
        raise RuntimeError("AMBIENT_DEVICE_MAC does not match any Ambient device.")
    if len(devices) == 1:
        return devices[0]
    if not devices:
        raise RuntimeError("No Ambient Weather devices were returned.")
    names = [d.get("info", {}).get("name") or d.get("macAddress") for d in devices]
    raise RuntimeError(
        "Multiple Ambient devices are present. Set AMBIENT_DEVICE_MAC. "
        f"Available devices: {names}"
    )


def parse_timestamp(raw: dict) -> tuple[datetime, str]:
    milliseconds = number(raw.get("dateutc"))
    if milliseconds is not None:
        utc_dt = datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc)
    else:
        text = raw.get("date")
        utc_dt = (
            datetime.fromisoformat(str(text).replace("Z", "+00:00")).astimezone(timezone.utc)
            if text else datetime.now(timezone.utc)
        )
    local_text = str(raw.get("date") or utc_dt.isoformat())
    return utc_dt, local_text


def normalize(device: dict) -> dict:
    raw = device.get("lastData") or {}
    utc_dt, local_text = parse_timestamp(raw)
    info = device.get("info") or {}

    record = {
        "timestamp_utc": utc_dt.isoformat().replace("+00:00", "Z"),
        "timestamp_local": local_text,
        "station_name": info.get("name") or info.get("location") or "Brambley",
        "temperature_c": f_to_c(raw.get("tempf")),
        "feels_like_c": f_to_c(raw.get("feelsLike")),
        "dew_point_c": f_to_c(raw.get("dewPoint")),
        "humidity_pct": number(raw.get("humidity")),
        "pressure_relative_hpa": inhg_to_hpa(raw.get("baromrelin")),
        "pressure_absolute_hpa": inhg_to_hpa(raw.get("baromabsin")),
        "wind_speed_kn": mph_to_knots(raw.get("windspeedmph")),
        "wind_gust_kn": mph_to_knots(raw.get("windgustmph")),
        "max_daily_gust_kn": mph_to_knots(raw.get("maxdailygust")),
        "wind_direction_deg": number(raw.get("winddir")),
        "wind_direction_compass": compass(raw.get("winddir")),
        "rain_rate_mm_hr": in_to_mm(raw.get("rainratein", raw.get("hourlyrainin"))),
        "rain_daily_mm": in_to_mm(raw.get("dailyrainin")),
        "rain_event_mm": in_to_mm(raw.get("eventrainin")),
        "rain_monthly_mm": in_to_mm(raw.get("monthlyrainin")),
        "rain_yearly_mm": in_to_mm(raw.get("yearlyrainin")),
        "solar_radiation_w_m2": number(raw.get("solarradiation")),
        "uv_index": number(raw.get("uv")),
    }
    return {k: clean(v) for k, v in record.items()}


def append_observation(record: dict) -> Path:
    utc_dt = datetime.fromisoformat(record["timestamp_utc"].replace("Z", "+00:00"))
    path = OBS_DIR / f"{utc_dt:%Y-%m}.csv"
    OBS_DIR.mkdir(parents=True, exist_ok=True)

    existing = set()
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                existing.add(row.get("timestamp_utc"))

    if record["timestamp_utc"] in existing:
        return path

    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OBS_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({k: record.get(k) for k in OBS_FIELDS})
    return path


def parse_float(row: dict, key: str) -> float | None:
    return number(row.get(key))


def rebuild_daily(monthly_csv: Path) -> Path:
    with monthly_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        local_stamp = row.get("timestamp_local") or ""
        date_local = local_stamp[:10] if len(local_stamp) >= 10 and local_stamp[4:5] == "-" else row["timestamp_utc"][:10]
        grouped.setdefault(date_local, []).append(row)

    daily_rows = []
    for day, observations in sorted(grouped.items()):
        temps = [v for r in observations if (v := parse_float(r, "temperature_c")) is not None]
        humid = [v for r in observations if (v := parse_float(r, "humidity_pct")) is not None]
        press = [v for r in observations if (v := parse_float(r, "pressure_relative_hpa")) is not None]
        winds = [v for r in observations if (v := parse_float(r, "wind_speed_kn")) is not None]
        gusts = [v for r in observations if (v := parse_float(r, "wind_gust_kn")) is not None]
        daily_rain = [v for r in observations if (v := parse_float(r, "rain_daily_mm")) is not None]

        solar = []
        for row in observations:
            irradiance = parse_float(row, "solar_radiation_w_m2")
            if irradiance is None:
                continue
            stamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
            solar.append((stamp, irradiance))
        solar.sort()

        solar_kwh = 0.0
        for (t0, s0), (t1, s1) in zip(solar, solar[1:]):
            dt_h = (t1 - t0).total_seconds() / 3600.0
            if 0 < dt_h <= 20.0 / 60.0:
                solar_kwh += ((s0 + s1) / 2.0) * dt_h / 1000.0

        daily_rows.append({
            "date_local": day,
            "temperature_avg_c": round(sum(temps) / len(temps), 2) if temps else None,
            "temperature_high_c": round(max(temps), 2) if temps else None,
            "temperature_low_c": round(min(temps), 2) if temps else None,
            "humidity_avg_pct": round(sum(humid) / len(humid), 1) if humid else None,
            "pressure_avg_hpa": round(sum(press) / len(press), 1) if press else None,
            "wind_avg_kn": round(sum(winds) / len(winds), 2) if winds else None,
            "peak_gust_kn": round(max(gusts), 2) if gusts else None,
            "rain_total_mm": round(max(daily_rain), 2) if daily_rain else None,
            "solar_peak_w_m2": round(max((s for _, s in solar), default=0), 1) if solar else None,
            "solar_energy_kwh_m2": round(solar_kwh, 3) if solar else None,
            "observation_count": len(observations),
        })

    output = DAILY_DIR / f"{monthly_csv.stem}.csv"
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DAILY_FIELDS)
        writer.writeheader()
        writer.writerows(daily_rows)
    return output


def write_current(record: dict, device: dict) -> None:
    raw = device.get("lastData") or {}
    current = {
        "status": "ok",
        "station": record["station_name"],
        "observed_at_utc": record["timestamp_utc"],
        "observed_at_local": record["timestamp_local"],
        "measurements": {
            k: v for k, v in record.items()
            if k not in ("timestamp_utc", "timestamp_local", "station_name")
        },
        "units": {
            "temperature_c": "°C", "feels_like_c": "°C", "dew_point_c": "°C",
            "humidity_pct": "%", "pressure_relative_hpa": "hPa",
            "pressure_absolute_hpa": "hPa", "wind_speed_kn": "kn",
            "wind_gust_kn": "kn", "max_daily_gust_kn": "kn",
            "wind_direction_deg": "°", "rain_rate_mm_hr": "mm/h",
            "rain_daily_mm": "mm", "rain_event_mm": "mm", "rain_monthly_mm": "mm",
            "rain_yearly_mm": "mm", "solar_radiation_w_m2": "W/m²",
            "uv_index": "UV index"
        },
        "source_fields_available": sorted(raw.keys()),
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "current.json").write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    api_key = os.environ.get("AMBIENT_API_KEY")
    app_key = os.environ.get("AMBIENT_APPLICATION_KEY")
    requested_mac = os.environ.get("AMBIENT_DEVICE_MAC")

    if not api_key or not app_key:
        print("AMBIENT_API_KEY and AMBIENT_APPLICATION_KEY are required.", file=sys.stderr)
        return 2

    devices = get_devices(api_key, app_key)
    device = choose_device(devices, requested_mac)
    record = normalize(device)

    write_current(record, device)
    monthly = append_observation(record)
    daily = rebuild_daily(monthly)

    print(f"Collected {record['timestamp_utc']} from {record['station_name']}")
    print(f"Updated {monthly.relative_to(ROOT)}")
    print(f"Updated {daily.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
