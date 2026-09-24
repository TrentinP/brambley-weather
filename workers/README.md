# Brambley live weather endpoint

The Squarespace Weather Station currently gets its "current" observation from `data/current.json`, which is updated by GitHub Actions. GitHub scheduled workflows can be delayed by hours, so the archive can remain healthy while the public "live" panel is stale.

This Worker is the live path:

```
Squarespace browser -> Cloudflare Worker -> Ambient Weather
```

The existing GitHub collector remains the archive path:

```
Ambient Weather -> GitHub Actions -> data/observations, data/daily, current.json
```

The Worker keeps the Ambient API credentials off the public Squarespace page and edge-caches the current observation for 45 seconds.

## Deploy in Cloudflare

1. In Cloudflare, create a new Worker.
2. Replace the starter Worker code with `workers/live-weather.js`.
3. In **Settings -> Variables and Secrets**, add these as **Secrets**:
   - `AMBIENT_API_KEY`
   - `AMBIENT_APPLICATION_KEY`
   - `AMBIENT_DEVICE_MAC`
4. Add `ALLOWED_ORIGIN` as a normal variable containing the public Brambley site origin, for example `https://www.example.com`.
5. Deploy the Worker.
6. Open the Worker's `/current` URL. It should return JSON with `"status":"ok"` and `"source":"ambient-live"`.
7. Copy the deployed Worker URL. The Squarespace master code can then be changed to use this endpoint for the live panel while retaining GitHub data for daily and historical graphs.

## Security

Do not put the Ambient API key, application key, or station MAC address into Squarespace JavaScript. They belong only in Worker secrets.

## Failure behavior

When the live endpoint is wired into the Weather Station page, the frontend should fall back to the GitHub `data/current.json` record if the Worker is temporarily unavailable. That keeps the page useful during an upstream or Worker outage.
