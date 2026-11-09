from __future__ import annotations

import logging
import re
import time
from typing import Optional

from .config import AppConfig, Credentials
from .http import HttpEngine
from .jsonpath import get_path

log = logging.getLogger("crawler.auth")


class LoginError(RuntimeError):
    pass


class AuthManager:
    def __init__(self, config: AppConfig, creds: Optional[Credentials], engine: HttpEngine):
        self.config = config
        self.creds = creds
        self.engine = engine
        self.token: Optional[str] = None

    def login(self) -> None:
        cfg = self.config.login
        if self.creds is None:
            raise LoginError(
                "Login is enabled but no credentials found: fill credentials.yaml "
                "or set CRAWLER_USERNAME/CRAWLER_PASSWORD"
            )
        if cfg.login_type == "xf":
            self._login_xf()
        elif cfg.login_type in ("json", "form"):
            self._login_http()
        else:
            raise LoginError(f"Unknown login_type: {cfg.login_type}")
        self._verify_login()

    def _login_http(self) -> None:
        cfg = self.config.login
        url = self.config.site.base_url.rstrip("/") + cfg.endpoint
        payload = {
            cfg.username_field: self.creds.username,
            cfg.password_field: self.creds.password,
            **(cfg.extra_payload or {}),
        }
        headers = {"Content-Type": "application/json"}
        try:
            if cfg.payload_type == "form":
                resp = self.engine.request(
                    "POST", url, data=payload, headers=headers,
                )
            else:
                resp = self.engine.request(
                    "POST", url, json=payload, headers=headers,
                )
        except Exception as exc:
            raise LoginError(f"Login request failed: {exc}") from exc
        if resp.status_code != 200:
            raise LoginError(
                f"Login failed: HTTP {resp.status_code} {resp.text[:200]!r}"
            )
        if cfg.token_path:
            try:
                body = resp.json()
            except ValueError as exc:
                raise LoginError("Login response is not valid JSON") from exc
            token = get_path(body, cfg.token_path)
            if not token:
                raise LoginError(
                    f"Token not found at '{cfg.token_path}' in login response"
                )
            self.token = str(token)
            log.info("Login OK (token acquired)")
        else:
            log.info("Login OK (session cookies)")

    def _login_xf(self) -> None:
        cfg = self.config.login
        base = self.config.site.base_url.rstrip("/")
        if not cfg.login_page:
            raise LoginError("login.login_page is required for login_type=xf")
        try:
            resp = self.engine.request("GET", base + cfg.login_page, headers={})
        except Exception as exc:
            raise LoginError(f"Cannot open login page {cfg.login_page}: {exc}") from exc
        if resp.status_code != 200:
            raise LoginError(f"Login page HTTP {resp.status_code}")
        m = re.search(
            r'name="' + re.escape(cfg.csrf_field) + r'"[^>]*value="([^"]+)"', resp.text
        )
        if not m:
            raise LoginError(f"CSRF token '{cfg.csrf_field}' not found on login page")
        csrf = m.group(1)
        payload = {
            cfg.username_field: self.creds.username,
            cfg.password_field: self.creds.password,
            cfg.csrf_field: csrf,
            cfg.redirect_field: base + "/",
            "_xfWithData": "1",
            **(cfg.extra_payload or {}),
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": base + cfg.login_page,
            "Origin": base,
        }
        try:
            resp = self.engine.request(
                "POST", base + cfg.endpoint, data=payload, headers=headers,
            )
        except Exception as exc:
            raise LoginError(f"Login POST failed: {exc}") from exc
        log.info("Login POST done (HTTP %d)", resp.status_code)

    def _verify_login(self) -> None:
        cfg = self.config.login
        if not cfg.success_check_url:
            return
        base = self.config.site.base_url.rstrip("/")
        resp = self.engine.request("GET", base + cfg.success_check_url, headers={})
        text = resp.text
        if cfg.failure_check_marker and cfg.failure_check_marker in text:
            raise LoginError(
                f"Login rejected: marker {cfg.failure_check_marker!r} still present "
                "(wrong credentials?)"
            )
        if cfg.success_check_marker and cfg.success_check_marker not in text:
            raise LoginError(
                f"Login not confirmed: marker {cfg.success_check_marker!r} not found"
            )
        log.info("Login verified via %s", cfg.success_check_url)

    def login_with_retries(self) -> None:
        cfg = self.config.login
        delay = 1.0
        for attempt in range(1, cfg.max_retries + 1):
            try:
                self.login()
                return
            except LoginError as exc:
                log.warning(
                    "Login attempt %d/%d failed: %s",
                    attempt, cfg.max_retries, exc,
                )
                if attempt < cfg.max_retries:
                    time.sleep(delay)
                    delay *= cfg.retry_backoff
        raise LoginError(f"Login failed after {cfg.max_retries} attempts")

    def apply_auth(self, headers: dict) -> dict:
        if self.token and self.config.login.auth_header:
            prefix = self.config.login.token_prefix or ""
            headers[self.config.login.auth_header] = f"{prefix}{self.token}"
        return headers

    def needs_relogin(self, status_code: int) -> bool:
        return status_code in self.config.login.relogin_status_codes
