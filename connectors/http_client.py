"""Retrying HTTP client. The only place HTTP retries live.

Rules, all in one place so every connector behaves the same way:

* 429 (and 503 with ``Retry-After``) — wait the header value, capped
  at ``backoff_max`` seconds. The header wins over the backoff.
* Other 5xx and transport errors — exponential backoff with full
  jitter: ``sleep(uniform(0, min(backoff_max, base * 2**attempt)))``.
* 401/403 — :class:`ConnectorAuthError` immediately, no retry: retrying
  bad credentials only burns rate-limit budget.
* Other 4xx — :class:`ConnectorError` immediately, no retry.
* After ``max_retries`` retries the last error is raised.

The ``requests.Session`` is injected (constructor argument), so tests
can pass a fake session and unit tests never touch the network. The
``sleep`` and ``jitter`` callables are also injected, so retry timing
is deterministic in tests.
"""

import random
import time

import requests

from .errors import ConnectorAuthError, ConnectorError

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class RetryingHttpClient:
    def __init__(
        self,
        session=None,
        *,
        max_retries=3,
        backoff_base=0.5,
        backoff_max=30.0,
        timeout=10.0,
        sleep=None,
        jitter=None,
    ):
        self.session = session or requests.Session()
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.timeout = timeout
        self._sleep = sleep or time.sleep
        self._jitter = jitter or random.uniform
        self._headers = {}

    def set_headers(self, headers):
        self._headers.update(headers)

    @property
    def headers(self):
        return dict(self._headers)

    def _retry_after_seconds(self, response):
        raw = response.headers.get("Retry-After") if response.headers else None
        if raw is None:
            return None
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return None

    def _wait(self, attempt, response=None):
        retry_after = (
            self._retry_after_seconds(response) if response is not None else None
        )
        if retry_after is not None:
            delay = min(retry_after, self.backoff_max)
            self._sleep(delay)
            return delay
        cap = min(self.backoff_max, self.backoff_base * (2**attempt))
        delay = self._jitter(0, cap)
        self._sleep(delay)
        return delay

    def get(self, url, params=None):
        """GET with retries. Returns the response on 2xx, else raises."""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url, params=params, headers=self._headers, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_error = ConnectorError(f"Request failed: {exc}")
                if attempt == self.max_retries:
                    raise last_error from exc
                self._wait(attempt)
                continue
            status = response.status_code
            if 200 <= status < 300:
                return response
            if status in (401, 403):
                raise ConnectorAuthError(
                    f"Authentication failed (HTTP {status}) for {url}"
                )
            if status in RETRYABLE_STATUSES:
                last_error = ConnectorError(
                    f"Upstream returned HTTP {status} for {url}"
                )
                if attempt == self.max_retries:
                    raise last_error
                self._wait(attempt, response)
                continue
            raise ConnectorError(f"Upstream returned HTTP {status} for {url}")
        raise last_error  # pragma: no cover - loop always raises first
