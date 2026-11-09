from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class SiteConfig:
    name: str = "site"
    base_url: str = ""
    engine: str = "requests"
    impersonate: str = "chrome"


@dataclass
class LoginConfig:
    enabled: bool = False
    login_type: str = "json"
    endpoint: str = ""
    login_page: str = ""
    csrf_field: str = "_xfToken"
    csrf_selector: str = 'input[name="_xfToken"]'
    redirect_field: str = "_xfRedirect"
    payload_type: str = "json"
    username_field: str = "username"
    password_field: str = "password"
    extra_payload: dict = field(default_factory=dict)
    token_path: str = ""
    auth_header: str = ""
    token_prefix: str = "Bearer "
    relogin_status_codes: tuple = (401, 403)
    max_retries: int = 3
    retry_backoff: float = 2.0
    success_check_url: str = ""
    success_check_marker: str = ""
    failure_check_marker: str = ""


@dataclass
class CrawlConfig:
    endpoint: str = ""
    method: str = "GET"
    response_type: str = "json"
    page_param: str = "page"
    size_param: Optional[str] = None
    page_size: Optional[int] = None
    page_url_template: str = ""
    pagination: str = "template"
    next_page_selector: str = "a.pageNav-jump--next"
    start_page: int = 1
    max_pages: int = 0
    items_path: str = "data"
    items_selector: str = ""
    fields: dict = field(default_factory=dict)
    stop_when_empty: bool = True
    stop_status_codes: tuple = (404,)
    total_pages_path: Optional[str] = None
    served_page_selector: str = ""
    total_pages_selector: str = ""
    total_pages_attr: str = "max"
    params: dict = field(default_factory=dict)
    request_delay: float = 1.0
    timeout: float = 30.0
    verify_ssl: bool = True


@dataclass
class FieldConfig:
    selector: str = ""
    attr: str = "text"
    default: str = ""
    base_url: str = ""
    regex: str = ""


@dataclass
class OutputConfig:
    format: str = "jsonl"
    file: str = "output/items.jsonl"
    csv_columns: list = field(default_factory=list)
    checkpoint_file: str = "output/checkpoint.json"
    append_mode: bool = False
    daily_file: bool = False


@dataclass
class AppConfig:
    site: SiteConfig
    login: LoginConfig
    crawl: CrawlConfig
    output: OutputConfig


@dataclass
class Credentials:
    username: str
    password: str


def _build(cls, data: dict):
    allowed = set(cls.__dataclass_fields__)
    return cls(**{k: v for k, v in (data or {}).items() if k in allowed})


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    crawl = _build(CrawlConfig, raw.get("crawl"))
    fields = {}
    for name, spec in (crawl.fields or {}).items():
        if isinstance(spec, dict):
            fields[name] = _build(FieldConfig, spec)
        else:
            fields[name] = FieldConfig(attr=str(spec))
    crawl.fields = fields
    login = _build(LoginConfig, raw.get("login"))
    if isinstance(login.relogin_status_codes, int):
        login.relogin_status_codes = (login.relogin_status_codes,)
    crawl_c = crawl
    if isinstance(crawl_c.stop_status_codes, int):
        crawl_c.stop_status_codes = (crawl_c.stop_status_codes,)
    return AppConfig(
        site=_build(SiteConfig, raw.get("site")),
        login=login,
        crawl=crawl_c,
        output=_build(OutputConfig, raw.get("output")),
    )


def load_credentials(path: str) -> Optional[Credentials]:
    username = os.environ.get("CRAWLER_USERNAME", "")
    password = os.environ.get("CRAWLER_PASSWORD", "")
    if not (username and password):
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        username = username or str(raw.get("username", ""))
        password = password or str(raw.get("password", ""))
    if not username or not password:
        return None
    return Credentials(username=username, password=password)
