# Brambley Historical Weather Archive

Public historical weather data converted from the long-running Brambley weather workbook.

- Daily archive coverage: 2020-01-15 through 2026-08-31 (2,407 days).
- Monthly temperature series: 2007-01 through 2026-08 (236 months).
- Monthly rainfall series: 2020-01 through 2026-08 (80 months).
- Annual rainfall totals: 2020 through 2025.
- Source-record files preserve the workbook's Average/High/High Datetime/Low/Low Datetime records, split by year. Indoor measurements have been omitted.

## Units

Temperatures are °C, rainfall is mm, pressure is hPa, wind remains in knots, and solar irradiance is W/m².

## Historical solar data

The workbook contains daily average and maximum solar-radiation values. These are retained as observed W/m² values. Historical daily kWh/m² is not reconstructed because the workbook does not contain the full intraday irradiance series needed for defensible integration. Daily solar energy accumulation begins with the live five-minute archive.

## Rainfall average

`rainfall_average_2020_2025.csv` is the observed Brambley site average based on six complete calendar years. It is not a NOAA 30-year climate normal.
