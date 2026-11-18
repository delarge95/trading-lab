"""HTTP helper: identifying User-Agent, throttling, retries and an on-disk cache."""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import requests

CACHE_DIR = Path(os.environ.get("TRADING_LAB_CACHE", "data/raw"))
_last_call: dict[str, float] = {}
MIN_INTERVAL = {"sec.gov": 0.15}  # SEC allows 10 req/s; stay well below


def sec_user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError(
            "SEC_USER_AGENT no definido. La SEC exige un contacto: "
            "export SEC_USER_AGENT='trading-lab tu_correo'"
        )
    return ua


def _host_key(url: str) -> str:
    host = url.split("/")[2]
    return "sec.gov" if host.endswith("sec.gov") else host


def get(url: str, *, headers: dict | None = None, cache: bool = False,
        timeout: int = 30, retries: int = 3) -> requests.Response:
    h = {"User-Agent": os.environ.get("HTTP_USER_AGENT", "Mozilla/5.0 trading-lab")}
    key = _host_key(url)
    if key == "sec.gov":
        h["User-Agent"] = sec_user_agent()
    if headers:
        h.update(headers)

    path = None
    if cache:
        path = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".bin")
        if path.exists():
            r = requests.Response()
            r.status_code = 200
            r._content = path.read_bytes()
            return r

    last_exc: Exception | None = None
    for attempt in range(retries):
        wait = MIN_INTERVAL.get(key, 0) - (time.time() - _last_call.get(key, 0))
        if wait > 0:
            time.sleep(wait)
        _last_call[key] = time.time()
        try:
            r = requests.get(url, headers=h, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
            return r
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} falló tras {retries} intentos: {last_exc}")
