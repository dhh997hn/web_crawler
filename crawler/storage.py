from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path
from typing import Any

from .config import OutputConfig
from .jsonpath import get_path

log = logging.getLogger("crawler.storage")


class Checkpoint:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict = {
            "last_page": 0,
            "total_items": 0,
            "finished": False,
            "updated_at": None,
        }

    def load(self) -> dict:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                log.warning("Cannot read checkpoint %s (%s), starting fresh", self.path, exc)
        return self.data

    def save(self, last_page: int, total_items: int, finished: bool = False) -> None:
        self.data = {
            "last_page": last_page,
            "total_items": total_items,
            "finished": finished,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


class RecordWriter:
    def __init__(self, output: OutputConfig, truncate: bool = False):
        self.output = output
        self.path = self._resolve_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: Any = None
        self._csv: Any = None
        log.info("Output file: %s", self.path)
        self._open(truncate)

    def _resolve_path(self) -> Path:
        p = Path(self.output.file)
        if not self.output.daily_file:
            return p
        stamp = time.strftime("%d-%m-%Y")
        return p.with_name(f"{p.stem}.{stamp}{p.suffix}")

    def _open(self, truncate: bool = False) -> None:
        mode = "w" if truncate else "a"
        if self.output.format == "csv":
            self._fh = open(self.path, mode, newline="", encoding="utf-8-sig")
            self._csv = csv.writer(self._fh)
            if self.path.stat().st_size == 0:
                self._csv.writerow(self.output.csv_columns)
        else:
            self._fh = open(self.path, mode, encoding="utf-8")

    def write(self, items: list) -> int:
        count = 0
        for item in items:
            if self.output.format == "csv":
                row = [self._to_str(get_path(item, col)) for col in self.output.csv_columns]
                self._csv.writerow(row)
            else:
                self._fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
            count += 1
        if self._fh:
            self._fh.flush()
        return count

    def _to_str(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)

    def close(self) -> None:
        if self._fh:
            self._fh.close()
