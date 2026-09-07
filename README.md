# Brambley Weather

Weather-data collector and public archive backend for the Brambley Observatory.

## Public measurement standard

- Temperature: °C
- Rainfall: mm
- Pressure: hPa
- Wind: knots
- Solar irradiance: W/m²
- Solar energy: kWh/m²
- Humidity: %
- UV: UV Index
- Wind direction: degrees and compass point

## How it works

A GitHub Actions workflow runs every five minutes and:

1. Calls the Ambient Weather REST API.
2. Selects the configured weather station.
3. Converts Ambient's imperial fields into the Brambley public units.
4. Writes the latest observation to `data/current.json`.
5. Appends new observations to a monthly CSV file in `data/observations/`.
6. Rebuilds daily summary records in `data/daily/`.
7. Integrates solar irradiance observations to estimate daily solar energy in kWh/m².

The collector deliberately preserves only normalized public fields in the repository. Ambient API credentials remain in GitHub Actions secrets.

## Required GitHub secrets

Create these repository secrets:

- `AMBIENT_API_KEY`
- `AMBIENT_APPLICATION_KEY`

Optional:

- `AMBIENT_DEVICE_MAC`

If `AMBIENT_DEVICE_MAC` is omitted and the Ambient account contains exactly one station, the collector uses that station automatically. If multiple stations are present, set the MAC-address secret to select Brambley explicitly.

## Manual testing

The workflow can also be run manually from the Actions tab.

## Historical data

The normalized historical Brambley archive created from the legacy spreadsheet can later be imported with `scripts/import_historical.py`.

## Solar-data caveat

The station's solar sensor provides useful site-specific observational data, but this project does not represent it as a calibrated utility-grade pyranometer or a formal photovoltaic site assessment.
