"""Shared utilities for data fetching scripts.

Provides retry logic with exponential backoff for HTTP requests.
"""

from __future__ import annotations

import time

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
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                url,
                headers=headers or {},
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(
                    f"⚠ Request failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                print(f"  Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                print(f"✗ All {max_retries} attempts failed")
    
    raise last_exception  # type: ignore
