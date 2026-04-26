from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
import re
from typing import Any


CACHE_SCHEMA_VERSION = 1
INDEX_FILE_NAME = "index.json"


@dataclass
class CacheEntry:
    cache_id: str
    label: str
    query: str
    source_kind: str
    preset: str
    bbox: list[float] | None
    app_version: str
    created_at: str
    feature_count: int
    structure_count: int
    payload_path: str


def cache_root(user_data_dir: str) -> str:
    return os.path.join(user_data_dir, "osm_cache")


def _index_path(user_data_dir: str) -> str:
    return os.path.join(cache_root(user_data_dir), INDEX_FILE_NAME)


def _ensure_root(user_data_dir: str) -> str:
    root = cache_root(user_data_dir)
    os.makedirs(root, exist_ok=True)
    return root


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower())
    return value.strip("-")[:64] or "map"


def _cache_id(query: str, bbox: list[float] | None, preset: str, source_kind: str) -> str:
    raw = json.dumps(
        {
            "query": str(query).strip().lower(),
            "bbox": bbox or [],
            "preset": str(preset).strip().lower(),
            "source_kind": str(source_kind).strip().lower(),
        },
        sort_keys=True,
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def list_entries(user_data_dir: str) -> list[CacheEntry]:
    path = _index_path(user_data_dir)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    entries: list[CacheEntry] = []
    for item in raw.get("entries", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(CacheEntry(**item))
        except TypeError:
            continue
    entries.sort(key=lambda entry: entry.created_at, reverse=True)
    return entries


def _write_entries(user_data_dir: str, entries: list[CacheEntry]) -> None:
    _ensure_root(user_data_dir)
    serializable = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "entries": [entry.__dict__ for entry in entries],
    }
    with open(_index_path(user_data_dir), "w", encoding="utf-8") as handle:
        json.dump(serializable, handle, indent=2)


def find_entry(
    user_data_dir: str,
    *,
    query: str = "",
    bbox: list[float] | None = None,
    preset: str = "",
    source_kind: str = "search",
) -> CacheEntry | None:
    cache_id = _cache_id(query, bbox, preset, source_kind)
    for entry in list_entries(user_data_dir):
        if entry.cache_id == cache_id:
            return entry
    return None


def store_payload(
    user_data_dir: str,
    *,
    label: str,
    query: str,
    bbox: list[float] | None,
    preset: str,
    source_kind: str,
    app_version: str,
    payload: dict[str, Any],
) -> CacheEntry:
    root = _ensure_root(user_data_dir)
    cache_id = _cache_id(query, bbox, preset, source_kind)
    file_name = f"{_slug(label)}-{cache_id}.json"
    payload_path = os.path.join(root, file_name)
    with open(payload_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    feature_count = len(payload.get("roads", [])) if isinstance(payload.get("roads", []), list) else 0
    structure_count = len(payload.get("structures", [])) if isinstance(payload.get("structures", []), list) else 0
    entry = CacheEntry(
        cache_id=cache_id,
        label=label,
        query=query,
        source_kind=source_kind,
        preset=preset,
        bbox=bbox,
        app_version=app_version,
        created_at=datetime.now().isoformat(timespec="seconds"),
        feature_count=feature_count,
        structure_count=structure_count,
        payload_path=payload_path,
    )
    entries = [existing for existing in list_entries(user_data_dir) if existing.cache_id != cache_id]
    entries.insert(0, entry)
    _write_entries(user_data_dir, entries)
    return entry


def load_payload(entry: CacheEntry) -> dict[str, Any]:
    with open(entry.payload_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Cached payload is not a JSON object.")
    return data


def remove_entry(user_data_dir: str, cache_id: str) -> None:
    remaining: list[CacheEntry] = []
    for entry in list_entries(user_data_dir):
        if entry.cache_id == cache_id:
            try:
                os.remove(entry.payload_path)
            except OSError:
                pass
            continue
        remaining.append(entry)
    _write_entries(user_data_dir, remaining)

