"""Open Food Facts barcode lookup (free, community data). Fail-soft: any network or data problem returns None.

Set BUBBLES_ENABLE_OPENFOODFACTS=false to turn the lookup off. Only the barcode is sent, never anything about the user.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any, Callable

import food_db

URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=code,product_name,generic_name,nutriments"
TIMEOUT_S = 4.0


def enabled() -> bool:
    return os.environ.get("BUBBLES_ENABLE_OPENFOODFACTS", "true").strip().lower() not in {"0", "false", "no"}


def valid_barcode(code: str) -> bool:
    return bool(re.fullmatch(r"[0-9]{8,14}", code or ""))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):   # a product lookup never needs to leave the fixed host
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)
_CACHE: dict[str, Any] = {}


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Bubbles-health-companion/1.0 (open-source prototype)"})
    with _OPENER.open(req, timeout=TIMEOUT_S) as resp:   # noqa: S310 - fixed https host
        return json.loads(resp.read(200_000).decode("utf-8", "replace"))


def lookup(code: str, fetch: Callable[[str], dict] | None = None) -> dict[str, Any] | None:
    """A food row for the barcode or None."""
    if not enabled() or not valid_barcode(code):
        return None
    if fetch is None and code in _CACHE:
        data = _CACHE[code]
    else:
        try:
            data = (fetch or _fetch)(URL.format(code=code))
        except Exception:  # noqa: BLE001
            return None
        if fetch is None:
            if len(_CACHE) > 500:
                _CACHE.clear()
            _CACHE[code] = data
    if not isinstance(data, dict) or data.get("status") not in (1, "1", True) or not isinstance(data.get("product"), dict):
        return None
    return food_db.from_open_food_facts({**data["product"], "code": code})
