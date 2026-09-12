"""Shared HTTP helper with retry/backoff for rate limits (429) and transient
server errors (5xx). Every network-calling source module goes through this so
retry behaviour lives in exactly one place."""
import time
import requests


def get_with_retry(url, params=None, headers=None, max_retries=3, timeout=15):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            print(f"    request error ({exc}); retrying...")
            time.sleep(1.5 * (attempt + 1))
            continue

        if resp.status_code == 200:
            return resp
        if resp.status_code in (403, 429) and attempt < max_retries - 1:
            wait = 3 * (2 ** attempt)
            print(f"    rate-limited ({resp.status_code}) on {url.split('?')[0]}, waiting {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code >= 500 and attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
            continue

        print(f"    request failed: {resp.status_code} for {url.split('?')[0]}")
        return None
    return None
