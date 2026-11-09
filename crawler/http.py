from __future__ import annotations

import requests

from .config import AppConfig

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class HttpEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self.session = self._make_session()

    def _make_session(self):
        site = self.config.site
        if site.engine == "curl_cffi":
            try:
                from curl_cffi import requests as curl_requests
            except ImportError as exc:
                raise RuntimeError(
                    "engine=curl_cffi requires: pip install curl_cffi"
                ) from exc
            return curl_requests.Session(impersonate=site.impersonate or "chrome")
        return requests.Session()

    def request(self, method: str, url: str, **kwargs):
        crawl = self.config.crawl
        kwargs.setdefault("timeout", crawl.timeout)
        kwargs.setdefault("verify", crawl.verify_ssl)
        if self.config.site.engine == "curl_cffi":
            merged = dict(BROWSER_HEADERS)
            merged.update(kwargs.get("headers") or {})
            kwargs["headers"] = merged
        return self.session.request(method, url, **kwargs)
