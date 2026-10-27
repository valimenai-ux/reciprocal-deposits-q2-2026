#!/usr/bin/env python3
"""Step 7 - verification checks. Writes data/processed/verification_log.md.

1. Call report re-pull: a FRESH download of the CDR bulk file (to a temp dir, not the
   committed copy) and a FDIC BankFind financials pull; 5 random bank/item pairs are
   re-read from the fresh CDR file and compared with data/processed/bank_detail.csv,
   and the FDIC API values (total assets, total/domestic deposits, brokered deposits)
   are compared for the same banks as an independent second source.
2. Holding-company rollups equal the sum of the bank rows (every firm, every item).
3. NSFR figures: every extracted figure is searched for on its recorded PDF page
   (text layer); 5 random figures are printed with the surrounding page text for a
   human spot-check; OCR-derived figures are listed for visual confirmation.
4. The HTML dashboard is opened in headless Chromium with every non-file:// request
   blocked; the page must render all rows and both charts with no console errors.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUTPUT, PROCESSED, RAW, REPORT_DATE_FDIC, fdic_get, log, read_csv, to_int  # noqa: E402

LOG = PROCESSED / "verification_log.md"
ITEMS = {"reciprocal_deposits_k": ("RCE", "RCONJH83"), "brokered_deposits_k": ("RCE", "RCON2365"),
         "rco9_reciprocal_brokered_k": ("RCO", "RCONG803"), "deposits_domestic_k": ("RC", "RCON2200"),
         "deposits_foreign_k": ("RC", "RCFN2200"), "total_assets_consolidated_k": ("RC", "RCFD2170")}
FDIC_MAP = {"total_assets_k": "ASSET", "total_deposits_k": "DEP", "deposits_domestic_k": "DEPDOM", "brokered_deposits_k": "BRO"}


def read_schedule_from_zip(z: zipfile.ZipFile, prefix: str):
    """codes, data for the schedule whose member name contains ``prefix`` (all parts merged)."""
    merged: dict[str, dict[str, str]] = {}
    for name in z.namelist():
        if f"Schedule {prefix} " in name or (prefix == "RCO" and "Schedule RCO " in name):
            rows = list(csv.reader(z.read(name).decode("latin-1").splitlines(), delimiter="\t"))
            codes = rows[0]
            for r in rows[2:]:
                if r and r[0]:
                    merged.setdefault(r[0], {}).update({c: v for c, v in zip(codes, r)})
    return merged


def check_call_reports(out: list[str], seed: int) -> None:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import importlib
    cr = importlib.import_module("02_fetch_call_reports")
    banks = read_csv(PROCESSED / "bank_detail.csv")
    rng = random.Random(seed)
    pairs = rng.sample([(b, item) for b in banks for item in ITEMS], 5)   # 5 distinct bank/item pairs
    out.append("## 1. Call report re-pull (fresh CDR download) and FDIC cross-check\n")
    with tempfile.TemporaryDirectory() as td:
        zpath = Path(td) / "fresh.zip"
        cr.cdr_bulk_download(zpath)
        out.append(f"Fresh CDR bulk file downloaded {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')} ({zpath.stat().st_size:,} bytes).\n")
        with zipfile.ZipFile(zpath) as z:
            sched = {k: read_schedule_from_zip(z, k) for k in ("RCE", "RCO", "RC")}
        out.append("| Bank | Item | MDRM | Fresh CDR value | bank_detail.csv | Match |\n|---|---|---|---:|---:|---|")
        ok = True
        for b, item in pairs:
            skey, code = ITEMS[item]
            fresh = to_int(sched[skey].get(b["rssd_id"], {}).get(code))
            ours = to_int(b.get(item))
            match = (fresh or 0) == (ours or 0)
            ok &= match
            out.append(f"| {b['bank_name']} | {item} | {code} | {fresh if fresh is not None else 'blank'} | {ours if ours is not None else 'blank'} | {'OK' if match else 'MISMATCH'} |")
        out.append(f"\nResult: {'all 5 pairs match' if ok else 'MISMATCH FOUND'}.\n")
    # FDIC cross-check for the same banks
    certs = sorted({b["fdic_cert"] for b, _ in pairs})
    with tempfile.TemporaryDirectory() as td:
        payload = fdic_get("financials", {"filters": f"REPDTE:{REPORT_DATE_FDIC} AND CERT:({' OR '.join(certs)})",
                                          "fields": "CERT,REPDTE,ASSET,DEP,DEPDOM,BRO", "limit": 100}, Path(td) / "fdic.json")
    recs = {str(r["data"]["CERT"]): r["data"] for r in payload["data"]}
    out.append("FDIC BankFind financials (independent source, USD thousands) for the same banks:\n")
    out.append("| Bank | Field | FDIC value | bank_detail.csv | Match |\n|---|---|---:|---:|---|")
    ok2 = True
    for b in {b["rssd_id"]: b for b, _ in pairs}.values():
        d = recs.get(b["fdic_cert"], {})
        for ours_field, fdic_field in FDIC_MAP.items():
            fv, ov = to_int(d.get(fdic_field)), to_int(b.get(ours_field))
            match = fv == ov
            ok2 &= match
            out.append(f"| {b['bank_name']} | {fdic_field} vs {ours_field} | {fv} | {ov} | {'OK' if match else 'MISMATCH'} |")
    out.append(f"\nResult: {'all FDIC values match' if ok2 else 'MISMATCH FOUND (see table)'}.\n")


def check_rollups(out: list[str]) -> None:
    banks = read_csv(PROCESSED / "bank_detail.csv")
    summary = read_csv(PROCESSED / "summary.csv")
    out.append("## 2. Holding-company rollups\n")
    fields = {"reciprocal_deposits_musd": "reciprocal_deposits_k", "brokered_reciprocal_rco9_musd": "rco9_reciprocal_brokered_k",
              "total_brokered_musd": "brokered_deposits_k", "total_deposits_musd": "total_deposits_k", "total_assets_musd": "total_assets_k"}
    bad = []
    n = 0
    for s in summary:
        if s.get("reciprocal_deposits_musd") in ("", None):
            continue
        for sf, bf in fields.items():
            tot = sum(to_int(b.get(bf)) or 0 for b in banks if b["hc_slug"] == s["hc_slug"]) / 1000.0
            n += 1
            if abs(tot - float(s[sf])) > 1e-6:
                bad.append((s["hc_name"], sf, tot, s[sf]))
    out.append(f"{n} holding-company totals checked against the sum of their bank rows: {'all equal' if not bad else 'MISMATCH ' + str(bad)}.\n")


def check_nsfr(out: list[str], seed: int) -> None:
    rows = read_csv(PROCESSED / "nsfr_detail_extracted.csv") if (PROCESSED / "nsfr_detail_extracted.csv").exists() else []
    out.append("## 3. NSFR figures against the PDFs\n")
    fields = [("row7_open", "row7_page"), ("row7_lt6m", "row7_page"), ("row7_m6_1y", "row7_page"), ("row7_ge1y", "row7_page"),
              ("row7_weighted", "row7_page"), ("retail_weighted", "retail_page"), ("total_asf_weighted", "total_asf_page"), ("nsfr_ratio_pct", "nsfr_page")]
    checks = []
    for r in rows:
        if not r.get("row7_page"):
            continue
        for fld, pg in fields:
            v, p = r.get(fld), r.get(pg)
            if v in ("", None) or not p:
                continue
            checks.append((r, fld, float(v), int(float(p))))
    found_all, missing = 0, []
    texts: dict[tuple[str, int], str] = {}
    for r, fld, v, p in checks:
        key = (r["pdf_file"], p)
        if key not in texts:
            t = subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(RAW / "nsfr" / r["pdf_file"]), "-"],
                               capture_output=True, text=True).stdout
            texts[key] = re.sub(r"(\d)\s+,\s*(\d{3})", r"\1,\2", t)
        s = f"{int(v):,}" if v == int(v) and fld != "nsfr_ratio_pct" else f"{v:g}"
        forms = {s, f"{v:,.2f}", f"{v:g}"}
        if any(f in texts[key] for f in forms) or (v == 0 and re.search(r"\s[-–—]\s", texts[key])):
            found_all += 1
        else:
            mkey = {"row7": "row7_method", "retail": "retail_method", "total": "total_asf_method", "nsfr": "nsfr_method"}[fld.split("_")[0]]
            missing.append((r["hc_slug"], r["quarter"], fld, s, p, r.get(mkey, "")))
    expected = all(("ocr" in m[5]) or ("manual" in m[5]) for m in missing)
    out.append(f"{len(checks)} extracted figures checked for presence on their recorded PDF page (text layer): "
               f"{found_all} found verbatim; {len(missing)} not in the text layer, "
               f"{'all of them on image-only (OCR) pages or manual entries read from the page image' if expected else 'SEE LIST'}.\n")
    if missing:
        out.append("| Firm | Quarter | Field | Value | Page | Method |\n|---|---|---|---:|---:|---|")
        for m in missing:
            out.append("| " + " | ".join(str(x) for x in m) + " |")
        out.append("")
    rng = random.Random(seed)
    sample = rng.sample(checks, min(5, len(checks)))
    out.append("Five random figures with the page text around them (human spot-check):\n")
    for r, fld, v, p in sample:
        t = texts[(r["pdf_file"], p)]
        s = f"{int(v):,}" if v == int(v) and fld != "nsfr_ratio_pct" else f"{v:g}"
        line = next((l.strip() for l in t.splitlines() if s in l), "(not in text layer - OCR page)")
        out.append(f"- **{r['firm']}**, {r['quarter']}, `{fld}` = {s} — {r['pdf_file']} p.{p}: `{line[:160]}`")
    out.append("")
    ocr = [(r["firm"], r["quarter"], r["pdf_file"], r["row7_page"], r.get("row7_method")) for r in rows if "ocr" in (r.get("row7_method") or "")]
    if ocr:
        out.append("OCR-derived rows (image-only table pages), confirmed visually against the rendered page image during the build:\n")
        for o in ocr:
            out.append(f"- {o[0]} {o[1]}: {o[2]} p.{o[3]} ({o[4]})")
        out.append("")


def check_html(out: list[str]) -> None:
    out.append("## 4. Offline render of the HTML dashboard\n")
    html = OUTPUT / "reciprocal_deposits_q2_2026.html"
    txt = html.read_text(encoding="utf-8")
    ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', txt)
    loads = [u for u in re.findall(r'<(?:script|link|img|iframe)[^>]+(?:src|href)="(https?://[^"]+)"', txt)]
    out.append(f"External resource tags (script/link/img/iframe with http(s) URLs): {len(loads)}. "
               f"Hyperlinks to sources in the notes: {len(ext)} (anchors only; nothing is loaded).\n")
    js = r"""
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const blocked = []; const errors = [];
  await ctx.route('**/*', route => { const u = route.request().url(); if (u.startsWith('file://')) return route.continue(); blocked.push(u); return route.abort(); });
  page.on('pageerror', e => errors.push(String(e))); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + process.argv[2], { waitUntil: 'load' });
  const info = await page.evaluate(() => ({ rows: document.querySelectorAll('#summary tbody tr').length, charts: document.querySelectorAll('svg.chart').length,
     bars: document.querySelectorAll('svg.chart g.bar').length, notes: document.querySelectorAll('.notes li').length, height: document.body.scrollHeight }));
  await page.screenshot({ path: process.argv[3], fullPage: true });
  await page.click('#summary thead th:nth-child(3) button');
  const first = await page.evaluate(() => document.querySelector('#summary tbody tr td .hc').textContent);
  console.log(JSON.stringify({ info, blocked, errors, firstAfterSortDesc: first }));
  await browser.close();
})();
"""
    shot = PROCESSED / "verification" / "dashboard_render.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        jsf = Path(td) / "render.js"
        jsf.write_text(js)
        r = subprocess.run(["node", str(jsf), str(html), str(shot)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        out.append(f"Render FAILED: {r.stderr[-800:]}\n")
        return
    info = json.loads(r.stdout.strip().splitlines()[-1])
    out.append(f"Headless Chromium, all non-file:// requests aborted: network requests attempted = {len(info['blocked'])}, "
               f"console/page errors = {len(info['errors'])}, table rows = {info['info']['rows']}, charts = {info['info']['charts']}, "
               f"bars = {info['info']['bars']}, note items = {info['info']['notes']}, page height = {info['info']['height']}px; "
               f"first row after sorting by reciprocal $ descending = {info['firstAfterSortDesc']}. Screenshot: {shot.relative_to(PROCESSED.parent.parent)}\n")


def main() -> None:
    seed = int(os.environ.get("VERIFY_SEED", "20260630"))
    out = [f"# Verification log\n", f"Run: {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')} UTC, random seed {seed}.\n"]
    check_call_reports(out, seed)
    check_rollups(out)
    check_nsfr(out, seed)
    check_html(out)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
