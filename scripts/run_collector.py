#!/usr/bin/env python3
"""Run the weather collector with conservative Ambient API request pacing."""
from __future__ import annotations

import runpy
import time

import requests

_original_get = requests.get
_last_request_at = 0.0
MIN_REQUEST_INTERVAL_SECONDS = 1.5
MAX_429_RETRIES = 4


def paced_get(*args, **kwargs):
    """Space API calls and retry HTTP 429 responses with backoff."""
    global _last_request_at

    for attempt in range(MAX_429_RETRIES + 1):
        elapsed = time.monotonic() - _last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)

        response = _original_get(*args, **kwargs)
        _last_request_at = time.monotonic()

        if response.status_code != 429:
            return response

        if attempt == MAX_429_RETRIES:
            return response

        retry_after = response.headers.get("Retry-After")
        try:
            wait = float(retry_after) if retry_after else 5.0 * (attempt + 1)
        except (TypeError, ValueError):
            wait = 5.0 * (attempt + 1)
        print(f"Ambient API rate limit reached; retrying in {wait:.1f} seconds...")
        time.sleep(wait)

    return response


requests.get = paced_get
runpy.run_path("scripts/collect_weather.py", run_name="__main__")
