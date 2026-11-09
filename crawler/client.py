from __future__ import annotations

import logging
import time
from typing import Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .auth import AuthManager
from .http import HttpEngine

log = logging.getLogger("crawler.client")


class CrawlError(RuntimeError):
    pass


class HttpError(CrawlError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    def __init__(self, config, auth: AuthManager, engine: HttpEngine):
        self.config = config
        self.auth = auth
        self.engine = engine
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        delay = self.config.crawl.request_delay
        if delay > 0:
            wait = delay - (time.monotonic() - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def _fetch(self, path: str, params: Optional[dict] = None):
        crawl = self.config.crawl
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = self.config.site.base_url.rstrip("/") + path
        attempts = 0
        relogins = 0
        max_attempts = 3
        max_relogins = 2
        while True:
            self._throttle()
            headers = self.auth.apply_auth({})
            try:
                resp = self.engine.request(
                    crawl.method, url, params=params, headers=headers,
                )
            except Exception as exc:
                attempts += 1
                if attempts >= max_attempts:
                    raise CrawlError(
                        f"Request failed after {max_attempts} attempts: {exc}"
                    ) from exc
                log.warning("Network error (attempt %d/%d): %s", attempts, max_attempts, exc)
                time.sleep(2 ** attempts)
                continue
            if resp.status_code in (200, 201):
                return resp
            if self.auth.needs_relogin(resp.status_code) and relogins < max_relogins:
                relogins += 1
                log.warning("HTTP %d -> re-login and retry", resp.status_code)
                self.auth.login_with_retries()
                continue
            if resp.status_code >= 500 or resp.status_code == 429:
                attempts += 1
                if attempts >= max_attempts:
                    raise HttpError(
                        resp.status_code,
                        f"HTTP {resp.status_code} after {max_attempts} attempts",
                    )
                log.warning("HTTP %d (attempt %d/%d), backing off", resp.status_code, attempts, max_attempts)
                time.sleep(2 ** attempts)
                continue
            raise HttpError(resp.status_code, f"HTTP {resp.status_code}: {resp.text[:300]!r}")

    def request_json(self, path: str, params: Optional[dict] = None) -> Any:
        resp = self._fetch(path, params)
        try:
            return resp.json()
        except ValueError as exc:
            raise CrawlError("Response is not valid JSON") from exc

    def request_html(self, path: str, params: Optional[dict] = None) -> BeautifulSoup:
        resp = self._fetch(path, params)
        return BeautifulSoup(resp.text, "html.parser")

    def absolutize(self, href: str) -> str:
        return urljoin(self.config.site.base_url, href)
