# Brambley Weather Data Schema

## `current.json`

Latest normalized station observation for the website.

## `observations/YYYY-MM.csv`

Five-minute station observations. Public canonical units are SI except wind, which is intentionally retained in knots.

## `daily/YYYY-MM.csv`

Daily summaries rebuilt automatically from observations.

`solar_energy_kwh_m2` is calculated by trapezoidal integration of measured solar irradiance. Gaps longer than 20 minutes are not bridged, preventing a single stale observation from being treated as continuous sunshine.

## Solar and light

`solar_radiation_w_m2` is retained as measured by the station.

Lux is intentionally not fabricated from W/m². A universal conversion is not physically valid because illuminance depends on the spectral distribution of the light. If the connected Ambient station exposes a genuine lux field, that field can be added after the first API response identifies it.
