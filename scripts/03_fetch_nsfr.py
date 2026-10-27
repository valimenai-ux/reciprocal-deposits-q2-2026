#!/usr/bin/env python3
"""Step 3 - download the NSFR disclosure PDFs listed in data/processed/sources.csv.

sources.csv is the curated list of each holding company's Q1-Q2 2026 NSFR public
disclosure (URL found on the firm's investor-relations site; see README for how the
list was built and verified). Every row with status "found" is downloaded with curl to
data/raw/nsfr/<pdf_file>; the sha256 of the saved file is written back to sources.csv
(or checked against the recorded value when one exists).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROCESSED, RAW, curl, log, read_csv, sha256_file, write_csv  # noqa: E402

import pdfplumber  # noqa: E402

RAW_NSFR = RAW / "nsfr"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated slugs")
    ap.add_argument("--force", action="store_true", help="re-download even if the file exists")
    args = ap.parse_args()
    rows = read_csv(PROCESSED / "sources.csv")
    failed: list[str] = []
    for r in rows:
        if r["status"] != "found" or not r.get("disclosure_url"):
            continue
        if args.only and r["hc_slug"] not in args.only.split(","):
            continue
        out = RAW_NSFR / r["pdf_file"]
        if args.force or not out.exists():
            log(f"downloading {r['hc_slug']}: {r['disclosure_url']}")
            try:
                curl(r["disclosure_url"], out)
            except subprocess.CalledProcessError as e:
                out.unlink(missing_ok=True)
                r["download_status"] = f"download failed (curl exit {e.returncode})"
                log(f"  FAILED for {r['hc_slug']}: curl exit {e.returncode} - the host did not serve the file to an automated client")
                failed.append(r["hc_slug"])
                continue
        r["download_status"] = "downloaded"
        digest = sha256_file(out)
        with open(out, "rb") as fh:
            head = fh.read(5)
        if head != b"%PDF-":
            raise SystemExit(f"{out} is not a PDF (starts with {head!r}); check the URL for {r['hc_slug']}")
        with pdfplumber.open(out) as pdf:
            n = len(pdf.pages)
        if r.get("sha256") and r["sha256"] != digest:
            log(f"WARNING: sha256 changed for {r['hc_slug']}: recorded {r['sha256'][:12]}..., downloaded {digest[:12]}...")
        r["sha256"] = digest
        r["pages"] = str(n)
        log(f"  {out.name}: {out.stat().st_size:,} bytes, {n} pages, sha256 {digest[:12]}...")
    cols = list(rows[0].keys())
    for c in ("pages", "download_status"):
        if c not in cols:
            cols.append(c)
    write_csv(PROCESSED / "sources.csv", rows, cols)
    log(f"done; failed downloads: {failed or 'none'}")


if __name__ == "__main__":
    main()
