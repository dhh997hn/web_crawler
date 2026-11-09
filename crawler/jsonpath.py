from __future__ import annotations

from typing import Any, Optional


def get_path(data: Any, path: str) -> Optional[Any]:
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return None
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current
