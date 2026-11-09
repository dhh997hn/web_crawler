from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import Tag

from .auth import AuthManager
from .client import ApiClient, CrawlError, HttpError
from .config import AppConfig, Credentials, FieldConfig
from .http import HttpEngine
from .jsonpath import get_path
from .storage import Checkpoint, RecordWriter

log = logging.getLogger("crawler.crawler")


class Crawler:
    def __init__(self, config: AppConfig, creds: Optional[Credentials]):
        self.config = config
        self.creds = creds

    def _page_path(self, page: int) -> str:
        crawl = self.config.crawl
        if crawl.page_url_template:
            if page <= 1:
                return crawl.endpoint
            suffix = crawl.page_url_template.format(page=page)
            return crawl.endpoint.rstrip("/") + "/" + suffix
        return crawl.endpoint

    def _page_params(self, page: int) -> dict:
        crawl = self.config.crawl
        params = dict(crawl.params or {})
        if not crawl.page_url_template:
            params[crawl.page_param] = page
            if crawl.size_param and crawl.page_size:
                params[crawl.size_param] = crawl.page_size
        return params

    def _extract_field(self, item: Tag, fc: FieldConfig):
        el = item.select_one(fc.selector) if fc.selector else item
        if el is None:
            return fc.default
        if fc.attr == "text":
            value = el.get_text(strip=True)
        elif fc.attr == "html":
            value = el.decode_contents().strip()
        else:
            value = el.get(fc.attr)
            if value is None:
                return fc.default
        if fc.regex:
            m = re.search(fc.regex, str(value))
            if not m:
                return fc.default
            value = m.group(1) if m.groups() else m.group(0)
        if fc.base_url and value:
            value = self._client.absolutize(str(value))
        return value

    def _extract_items(self, parsed) -> list:
        crawl = self.config.crawl
        if crawl.response_type != "html":
            items = get_path(parsed, crawl.items_path)
            return items if items is not None else []
        nodes = parsed.select(crawl.items_selector)
        items = []
        for node in nodes:
            record = {}
            for name, fc in (crawl.fields or {}).items():
                record[name] = self._extract_field(node, fc)
            items.append(record)
        return items

    def _served_page(self, soup, fallback: int) -> int:
        selector = self.config.crawl.served_page_selector
        if not selector:
            return fallback
        el = soup.select_one(selector)
        if el is None:
            return fallback
        try:
            return int(el.get_text(strip=True))
        except ValueError:
            return fallback

    def _is_clamped(self, soup, requested: int) -> bool:
        if requested <= 1 or not self.config.crawl.served_page_selector:
            return False
        el = soup.select_one(self.config.crawl.served_page_selector)
        if el is None:
            return False
        try:
            served = int(el.get_text(strip=True))
        except ValueError:
            return False
        if served == requested:
            return False
        log.info(
            "Requested page %d but site served page %s (out-of-range) -> done",
            requested, served,
        )
        return True

    def _reached_total_pages(self, soup, page: int) -> bool:
        crawl = self.config.crawl
        if not crawl.total_pages_selector:
            return False
        el = soup.select_one(crawl.total_pages_selector)
        if el is None:
            return False
        raw = (
            el.get_text(strip=True)
            if crawl.total_pages_attr == "text"
            else el.get(crawl.total_pages_attr)
        )
        try:
            total = int(raw)
        except (TypeError, ValueError):
            return False
        if total and page >= total:
            log.info("Reached last page (%d/%d) -> done", page, total)
            return True
        return False

    def _next_link(self, soup) -> Optional[str]:
        selector = self.config.crawl.next_page_selector
        if not selector:
            return None
        el = soup.select_one(selector)
        if el is None:
            return None
        href = el.get("href")
        return self._client.absolutize(href) if href else None

    def _finish(self, checkpoint: Checkpoint, last_page: int, total_items: int) -> None:
        checkpoint.save(last_page=last_page, total_items=total_items, finished=True)

    def run(self, resume: bool = True, max_pages: int = 0) -> dict:
        crawl = self.config.crawl
        engine = HttpEngine(self.config)
        auth = AuthManager(self.config, self.creds, engine)
        if self.config.login.enabled:
            auth.login_with_retries()
        client = ApiClient(self.config, auth, engine)
        self._client = client

        checkpoint = Checkpoint(self.config.output.checkpoint_file)
        append_mode = self.config.output.append_mode
        state = checkpoint.load() if resume else dict(checkpoint.data)
        fresh_start = False
        if resume and state.get("finished"):
            if append_mode:
                log.info("append_mode: starting a new crawl run, appending to output")
                fresh_start = True
            else:
                log.info(
                    "Crawl already finished at page %s; use --no-resume to re-crawl",
                    state.get("last_page"),
                )
                return {"pages": 0, "items": 0, "last_page": state.get("last_page")}

        if fresh_start:
            last_saved_page = crawl.start_page - 1
            total_items = 0
            checkpoint.save(last_page=last_saved_page, total_items=0, finished=False)
        elif resume and state.get("last_page"):
            last_saved_page = int(state["last_page"])
            total_items = int(state.get("total_items", 0))
            log.info("Resuming after page %d (%d items already saved)", last_saved_page, total_items)
        else:
            last_saved_page = crawl.start_page - 1
            total_items = 0
            checkpoint.save(last_page=last_saved_page, total_items=0, finished=False)

        writer = RecordWriter(self.config.output, truncate=(not resume) and not append_mode)
        limit = max_pages if max_pages > 0 else crawl.max_pages
        next_link_mode = crawl.response_type == "html" and crawl.pagination == "next_link"
        expected_page = last_saved_page + 1
        next_url: Optional[str] = None
        first_fetch = True
        pages_done = 0
        safety = 0
        try:
            while True:
                safety += 1
                if limit and pages_done >= limit:
                    log.info("Reached max pages limit (%d), stopping", limit)
                    break
                if safety > 100000:
                    raise CrawlError("Safety limit exceeded: too many iterations")
                if next_link_mode:
                    path = crawl.endpoint if first_fetch else next_url
                    if not path:
                        log.info("No next page link -> done")
                        self._finish(checkpoint, last_saved_page, total_items)
                        break
                    params = dict(crawl.params or {}) if first_fetch else None
                else:
                    path = self._page_path(expected_page)
                    params = self._page_params(expected_page)
                first_fetch = False
                resp = None
                try:
                    if crawl.response_type == "html":
                        soup = client.request_html(path, params)
                        if self._is_clamped(soup, expected_page):
                            self._finish(checkpoint, last_saved_page, total_items)
                            break
                        served = self._served_page(soup, expected_page)
                        items = self._extract_items(soup)
                    else:
                        resp = client.request_json(path, params)
                        served = expected_page
                        items = self._extract_items(resp)
                except HttpError as exc:
                    if exc.status_code in crawl.stop_status_codes:
                        log.info(
                            "HTTP %d at page %d -> treated as end of crawl",
                            exc.status_code, expected_page,
                        )
                        self._finish(checkpoint, last_saved_page, total_items)
                        break
                    raise
                if not isinstance(items, list):
                    raise CrawlError(
                        f"Extracted items are not a list "
                        f"(items_path={crawl.items_path!r}, items_selector={crawl.items_selector!r})"
                    )
                write_page = served if next_link_mode else expected_page
                skip_write = next_link_mode and write_page <= last_saved_page
                count = 0
                if skip_write:
                    log.info("Page %d already saved (resume re-walk), skipping", write_page)
                else:
                    count = writer.write(items)
                    total_items += count
                    pages_done += 1
                    last_saved_page = write_page
                    checkpoint.save(last_page=last_saved_page, total_items=total_items, finished=False)
                    log.info("Page %d: %d items (total %d)", write_page, count, total_items)
                    if crawl.stop_when_empty and count == 0:
                        log.info("Empty page reached -> done")
                        self._finish(checkpoint, last_saved_page, total_items)
                        break
                if next_link_mode:
                    next_url = self._next_link(soup)
                    expected_page = served + 1
                else:
                    if crawl.response_type == "json" and crawl.total_pages_path and resp is not None:
                        total_pages = get_path(resp, crawl.total_pages_path)
                        if total_pages and served >= int(total_pages):
                            log.info("Reached last page (%d/%s) -> done", served, total_pages)
                            self._finish(checkpoint, last_saved_page, total_items)
                            break
                    elif self._reached_total_pages(soup, served):
                        self._finish(checkpoint, last_saved_page, total_items)
                        break
                    expected_page = served + 1
        except KeyboardInterrupt:
            log.info("Interrupted, progress saved to %s", checkpoint.path)
        finally:
            writer.close()
        return {
            "pages": pages_done,
            "items": total_items,
            "last_page": checkpoint.data.get("last_page"),
        }
