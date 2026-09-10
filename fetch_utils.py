"""Shared utilities for data fetching scripts.

Provides retry logic with exponential backoff for HTTP requests.
"""

from __future__ import annotations

import time
from urllib.parse import urlsplit, urlunsplit

import requests


def request_with_retry(
    url: str,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: int = 15,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> requests.Response:
    """
    Make an HTTP GET request with exponential backoff retry logic.
    
    Args:
        url: URL to fetch
        headers: Request headers (optional)
        params: Query parameters (optional)
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)
    
    Returns:
        Response object if successful
    
    Raises:
        requests.RequestException: If all retries are exhausted
    
    Example:
        >>> from fetch_utils import request_with_retry
        >>> resp = request_with_retry(
        ...     "https://api.example.com/data",
        ...     headers={"X-Auth-Token": "abc123"},
        ...     params={"limit": 10}
        ... )
        >>> data = resp.json()
    """
    last_exception = None
    parsed = urlsplit(url)
    hosts = (
        ("football-data.co.uk", "www.football-data.co.uk")
        if parsed.hostname in {"football-data.co.uk", "www.football-data.co.uk"}
        else (parsed.hostname,)
    )

    for host in hosts:
        candidate = urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
        for attempt in range(max_retries):
            try:
                resp = requests.get(
                    candidate,
                    headers=headers or {"Accept": "text/csv,text/plain;q=0.9,*/*;q=0.1"},
                    params=params,
                    timeout=timeout,
                )
                resp.raise_for_status()
                preview = resp.text[:160].lower()
                if "<html" in preview or "<!doctype" in preview:
                    raise requests.exceptions.InvalidSchema(
                        f"HTML response from {candidate}: {resp.text[:160]!r}"
                    )
                return resp
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError,
                requests.exceptions.InvalidSchema,
            ) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    response = getattr(e, "response", None)
                    retry_after = response.headers.get("Retry-After") if response else None
                    try:
                        wait_time = min(float(retry_after), 5.0) if retry_after else backoff_factor ** attempt
                    except ValueError:
                        wait_time = backoff_factor ** attempt
                    print(f"⚠ Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"  Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    print(f"✗ All {max_retries} attempts failed for {candidate}")

    raise last_exception  # type: ignore
