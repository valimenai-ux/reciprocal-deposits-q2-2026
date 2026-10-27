"""Shared configuration and helpers for the reciprocal-deposit pipeline.

Every script adds its own directory to sys.path and imports this module, so
the scripts can be run with ``python3 -I`` (isolated mode) from any cwd.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
REFERENCE = DATA / "reference"
OUTPUT = REPO / "output"

REPORT_DATE = "2026-06-30"          # call report "as of" date
REPORT_DATE_CDR = "06/30/2026"      # label used in the CDR bulk-download form
REPORT_DATE_COMPACT = "06302026"    # suffix used in the CDR bulk file names
REPORT_DATE_FDIC = "20260630"       # REPDTE value in the FDIC BankFind API

FDIC_API = "https://api.fdic.gov/banks"
CDR_BULK_URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"

CURL_UA = "reciprocal-deposits-q2-2026 pipeline (curl)"


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def holding_companies() -> list[dict]:
    return read_csv(REFERENCE / "holding_companies.csv")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def curl(url: str, out: Path, *, extra: list[str] | None = None, timeout: int = 600) -> None:
    """Download ``url`` to ``out`` with curl (which honours HTTPS_PROXY and the CA bundle)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["curl", "-sS", "-L", "--fail", "--max-time", str(timeout), "-o", str(out), url]
    if extra:
        cmd[1:1] = extra
    r = subprocess.run(cmd)
    if r.returncode != 0:              # some hosts reset HTTP/2 streams; retry once over HTTP/1.1
        subprocess.run(cmd[:1] + ["--http1.1"] + cmd[1:], check=True)


def fdic_get(endpoint: str, params: dict, out: Path) -> dict:
    """GET an FDIC BankFind Suite API endpoint, save the raw JSON to ``out`` and return it."""
    from urllib.parse import urlencode
    url = f"{FDIC_API}/{endpoint}?" + urlencode({**params, "format": "json"})
    curl(url, out)
    with open(out, encoding="utf-8") as fh:
        return json.load(fh)


def to_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
