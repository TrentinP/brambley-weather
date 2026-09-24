/**
 * Brambley live weather proxy
 *
 * Cloudflare Worker that keeps Ambient Weather credentials server-side and returns
 * only the fields needed by the public Brambley Weather Station page.
 *
 * Required Worker secrets:
 *   AMBIENT_API_KEY
 *   AMBIENT_APPLICATION_KEY
 *   AMBIENT_DEVICE_MAC
 *
 * Optional Worker variable:
 *   ALLOWED_ORIGIN   e.g. https://www.brambley.com
 */

const API_ROOT = "https://rt.ambientweather.net/v1";
const MPH_TO_KNOTS = 0.8689762419;
const INHG_TO_HPA = 33.8638866667;
const IN_TO_MM = 25.4;

function number(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function clean(value, digits = 2) {
  return typeof value === "number" && Number.isFinite(value)
    ? Number(value.toFixed(digits))
    : value;
}

function fToC(v) {
  const n = number(v);
  return n === null ? null : (n - 32) * 5 / 9;
}

function inToMm(v) {
  const n = number(v);
  return n === null ? null : n * IN_TO_MM;
}

function inHgToHpa(v) {
  const n = number(v);
  return n === null ? null : n * INHG_TO_HPA;
}

function mphToKnots(v) {
  const n = number(v);
  return n === null ? null : n * MPH_TO_KNOTS;
}

function compass(degrees) {
  const d = number(degrees);
  if (d === null) return null;
  const names = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  return names[Math.floor(((d % 360) / 22.5) + 0.5) % 16];
}

function corsHeaders(request, env) {
  const requestOrigin = request.headers.get("Origin") || "";
  const allowed = env.ALLOWED_ORIGIN || "*";
  const origin = allowed === "*" ? "*" : (requestOrigin === allowed ? allowed : allowed);
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}

function json(body, status, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...headers,
    },
  });
}

export default {
  async fetch(request, env, ctx) {
    const cors = corsHeaders(request, env);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "GET") {
      return json({ status: "error", message: "Method not allowed" }, 405, cors);
    }

    const url = new URL(request.url);
    if (url.pathname !== "/" && url.pathname !== "/current") {
      return json({ status: "error", message: "Not found" }, 404, cors);
    }

    for (const key of ["AMBIENT_API_KEY", "AMBIENT_APPLICATION_KEY", "AMBIENT_DEVICE_MAC"]) {
      if (!env[key]) {
        return json({ status: "error", message: "Worker is not fully configured" }, 500, cors);
      }
    }

    // Keep the public endpoint effectively live while avoiding one Ambient API call
    // for every browser page view. A 45-second edge cache is enough for this use.
    const cache = caches.default;
    const cacheKey = new Request(new URL("/current", request.url).toString(), { method: "GET" });
    const cached = await cache.match(cacheKey);
    if (cached) {
      const response = new Response(cached.body, cached);
      Object.entries(cors).forEach(([k, v]) => response.headers.set(k, v));
      return response;
    }

    const mac = env.AMBIENT_DEVICE_MAC;
    const endpoint = new URL(`${API_ROOT}/devices/${encodeURIComponent(mac)}`);
    endpoint.searchParams.set("apiKey", env.AMBIENT_API_KEY);
    endpoint.searchParams.set("applicationKey", env.AMBIENT_APPLICATION_KEY);
    endpoint.searchParams.set("limit", "1");

    let upstream;
    try {
      upstream = await fetch(endpoint.toString(), {
        headers: { "Accept": "application/json" },
      });
    } catch (error) {
      return json({ status: "error", message: "Ambient Weather request failed" }, 502, cors);
    }

    if (!upstream.ok) {
      return json(
        { status: "error", message: "Ambient Weather returned an error", upstream_status: upstream.status },
        502,
        cors
      );
    }

    const payload = await upstream.json();
    const raw = Array.isArray(payload) ? payload[0] : null;
    if (!raw) {
      return json({ status: "error", message: "No current observation returned" }, 502, cors);
    }

    const ms = number(raw.dateutc);
    const observedUtc = ms !== null
      ? new Date(ms).toISOString()
      : (raw.date ? new Date(raw.date).toISOString() : new Date().toISOString());

    const body = {
      status: "ok",
      source: "ambient-live",
      observed_at_utc: observedUtc,
      measurements: {
        temperature_c: clean(fToC(raw.tempf)),
        feels_like_c: clean(fToC(raw.feelsLike)),
        dew_point_c: clean(fToC(raw.dewPoint)),
        humidity_pct: clean(number(raw.humidity)),
        pressure_relative_hpa: clean(inHgToHpa(raw.baromrelin)),
        pressure_absolute_hpa: clean(inHgToHpa(raw.baromabsin)),
        wind_speed_kn: clean(mphToKnots(raw.windspeedmph)),
        wind_gust_kn: clean(mphToKnots(raw.windgustmph)),
        max_daily_gust_kn: clean(mphToKnots(raw.maxdailygust)),
        wind_direction_deg: clean(number(raw.winddir)),
        wind_direction_compass: compass(raw.winddir),
        rain_rate_mm_hr: clean(inToMm(raw.rainratein ?? raw.hourlyrainin)),
        rain_daily_mm: clean(inToMm(raw.dailyrainin)),
        rain_event_mm: clean(inToMm(raw.eventrainin)),
        rain_monthly_mm: clean(inToMm(raw.monthlyrainin)),
        rain_total_mm: clean(inToMm(raw.totalrainin)),
        solar_radiation_w_m2: clean(number(raw.solarradiation)),
        uv_index: clean(number(raw.uv)),
      },
    };

    const response = json(body, 200, {
      ...cors,
      "Cache-Control": "public, max-age=20, s-maxage=45, stale-while-revalidate=60",
    });

    ctx.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  }
};
