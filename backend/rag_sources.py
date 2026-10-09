from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


SOURCES_FILE = Path(__file__).with_name("rag_sources.json")


def load_sources() -> list[dict]:
    if not SOURCES_FILE.exists():
        raise FileNotFoundError(f"Missing source registry: {SOURCES_FILE}")

    with SOURCES_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("rag_sources.json must contain a list")

    return data


def get_enabled_sources() -> list[dict]:
    return [
        source
        for source in load_sources()
        if source.get("enabled") is True
    ]


def validate_source(source_name: str, source_url: str | None) -> dict:
    matches = [
        source
        for source in get_enabled_sources()
        if source.get("source_name", "").lower() == source_name.lower()
    ]

    if not matches:
        raise ValueError(
            f"Source is not registered or enabled: {source_name}"
        )

    source = matches[0]

    if source_url:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""

        base = urlparse(source["base_url"])
        allowed_hostname = base.hostname or ""

        if hostname != allowed_hostname and not hostname.endswith(
            f".{allowed_hostname}"
        ):
            raise ValueError(
                f"URL is outside the approved source domain: {source_url}"
            )

    return source