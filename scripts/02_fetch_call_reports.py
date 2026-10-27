#!/usr/bin/env python3
"""Step 2 - bank-level Call Report items as of 2026-06-30.

Primary source: FFIEC CDR Public Data Distribution, bulk download
"Call Reports -- Single Period" (tab-delimited, all schedules). The download page is
an ASP.NET form, so this script drives it with curl in three posts (select product ->
select period and TSV format -> Download). The zip is saved byte-for-byte under
data/raw/call_reports/, and a filtered subset (dictionary rows + the banks in
data/processed/entities.csv) of the schedules used is written next to it so the
figures can be inspected without unzipping.

Fallback (``--source fdic``): the FDIC BankFind Suite financials API. It exposes total
assets, total/domestic deposits and brokered deposits but NOT the reciprocal items
(RC-E M.1.g, RC-O 9/9.a), which are then left blank.

Outputs: data/processed/field_map.csv, data/processed/bank_detail.csv
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (CDR_BULK_URL, CURL_UA, PROCESSED, RAW, REPORT_DATE, REPORT_DATE_CDR,  # noqa: E402
                    REPORT_DATE_COMPACT, REPORT_DATE_FDIC, fdic_get, log, read_csv, sha256_file,
                    to_int, write_csv)

RAW_CR = RAW / "call_reports"
ZIP_NAME = f"FFIEC_CDR_Call_Bulk_All_Schedules_{REPORT_DATE_COMPACT}.zip"

# Schedules we need from the bulk file (file name prefixes inside the zip).
SCHEDULES = {
    "POR": f"FFIEC CDR Call Bulk POR {REPORT_DATE_COMPACT}.txt",
    "RC": f"FFIEC CDR Call Schedule RC {REPORT_DATE_COMPACT}.txt",
    "RCE": f"FFIEC CDR Call Schedule RCE {REPORT_DATE_COMPACT}.txt",
    "RCO_1": f"FFIEC CDR Call Schedule RCO {REPORT_DATE_COMPACT}(1 of 2).txt",
    "RCO_2": f"FFIEC CDR Call Schedule RCO {REPORT_DATE_COMPACT}(2 of 2).txt",
}

# Items to pull. (field, schedule key, form item, MDRM code, applies-to, note)
ITEMS = [
    ("reciprocal_deposits_k", "RCE", "Schedule RC-E, Memorandum item 1.g - Total reciprocal deposits (as of the report date)", "RCONJH83", "031/041/051", ""),
    ("brokered_deposits_k", "RCE", "Schedule RC-E, Memorandum item 1.b - Total brokered deposits", "RCON2365", "031/041/051", ""),
    ("rco9_reciprocal_brokered_k", "RCO", "Schedule RC-O, item 9 - Reciprocal brokered deposits (included in Schedule RC-E, Memorandum item 1.b)", "RCONG803", "031/041/051", "becomes confidential from the 9/30/2026 report date (see notes)"),
    ("rco9a_fully_insured_reciprocal_brokered_k", "RCO", "Schedule RC-O, item 9.a - Fully insured reciprocal brokered deposits (included in Schedule RC-O, item 9)", "RCONL190", "031/041/051", "becomes confidential from the 9/30/2026 report date (see notes)"),
    ("deposits_domestic_k", "RC", "Schedule RC, item 13.a - Deposits in domestic offices (total)", "RCON2200", "031/041/051", ""),
    ("deposits_foreign_k", "RC", "Schedule RC, item 13.b - Deposits in foreign offices, Edge and Agreement subsidiaries, and IBFs (total)", "RCFN2200", "031 only", "blank/zero for FFIEC 041 and 051 filers"),
    ("total_assets_consolidated_k", "RC", "Schedule RC, item 12 - Total assets (consolidated, FFIEC 031)", "RCFD2170", "031 only", ""),
    ("total_assets_domestic_k", "RC", "Schedule RC, item 12 - Total assets (FFIEC 041/051)", "RCON2170", "041/051", ""),
]


def hidden_fields(page: str) -> dict:
    return {m.group(1): html.unescape(m.group(2))
            for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}


def curl_post(url: str, cookies: Path, data: dict, out: Path, headers_out: Path | None = None) -> None:
    body = urlencode(data).encode()
    cmd = ["curl", "-sS", "--fail", "--max-time", "900", "-A", CURL_UA, "-c", str(cookies), "-b", str(cookies),
           "-e", url, "-H", "Content-Type: application/x-www-form-urlencoded", "--data-binary", "@-", "-o", str(out)]
    if headers_out:
        cmd += ["-D", str(headers_out)]
    cmd.append(url)
    subprocess.run(cmd, input=body, check=True)


def cdr_bulk_download(out_zip: Path, period_label: str = REPORT_DATE_CDR) -> dict:
    """Drive the CDR 'Download Bulk Data' form and save the single-period zip."""
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        cookies, p0, p1, p2, hdr = td / "cookies", td / "p0.html", td / "p1.html", td / "p2.html", td / "hdr"
        subprocess.run(["curl", "-sS", "--fail", "--max-time", "120", "-A", CURL_UA, "-c", str(cookies), "-b", str(cookies),
                        "-o", str(p0), CDR_BULK_URL], check=True)
        page = p0.read_text(encoding="utf-8", errors="replace")
        # 1) select the product (autopostback populates the period list)
        data = hidden_fields(page)
        data.update({"__EVENTTARGET": "ctl00$MainContentHolder$ListBox1", "__EVENTARGUMENT": "",
                     "ctl00$MainContentHolder$ListBox1": "ReportingSeriesSinglePeriod"})
        curl_post(CDR_BULK_URL, cookies, data, p1)
        page = p1.read_text(encoding="utf-8", errors="replace")
        sel = re.search(r'<select name="ctl00\$MainContentHolder\$DatesDropDownList"[^>]*>(.*?)</select>', page, re.S)
        options = dict((lbl.strip(), val) for val, lbl in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', sel.group(1), re.S))
        if period_label not in options:
            raise SystemExit(f"period {period_label} not offered by CDR; available: {list(options)[:8]} ...")
        period_value = options[period_label]
        # 2) select the period and TSV format (radio autopostback)
        data = hidden_fields(page)
        data.update({"__EVENTTARGET": "ctl00$MainContentHolder$TSVRadioButton", "__EVENTARGUMENT": "",
                     "ctl00$MainContentHolder$ListBox1": "ReportingSeriesSinglePeriod",
                     "ctl00$MainContentHolder$DatesDropDownList": period_value,
                     "ctl00$MainContentHolder$FormatType": "TSVRadioButton"})
        curl_post(CDR_BULK_URL, cookies, data, p2)
        page = p2.read_text(encoding="utf-8", errors="replace")
        # 3) press Download
        data = hidden_fields(page)
        data.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "",
                     "ctl00$MainContentHolder$ListBox1": "ReportingSeriesSinglePeriod",
                     "ctl00$MainContentHolder$DatesDropDownList": period_value,
                     "ctl00$MainContentHolder$FormatType": "TSVRadioButton",
                     "ctl00$MainContentHolder$TabStrip1$Download_0": "Download"})
        curl_post(CDR_BULK_URL, cookies, data, out_zip, hdr)
        headers = hdr.read_text(errors="replace")
    m = re.search(r'filename="([^"]+)"', headers)
    if not zipfile.is_zipfile(out_zip):
        raise SystemExit("CDR did not return a zip file; the form flow may have changed")
    return {"server_filename": m.group(1) if m else "", "period_value": period_value}


def locate(sched: dict, skey: str, code: str) -> tuple[str, list, list, dict]:
    """Return (file_key, codes, descs, data) of the schedule file holding ``code``.

    Large schedules are split by CDR into several files ("(1 of 2)", "(2 of 2)"), so a
    key like "RCO" is resolved against every part."""
    for key in sorted(sched):
        if key == skey or key.startswith(skey + "_"):
            codes, descs, data = sched[key]
            if code in codes:
                return key, codes, descs, data
    raise SystemExit(f"MDRM code {code} not found in any {skey} file of the bulk download")


def read_schedule(path: Path) -> tuple[list[str], list[str], dict[str, list[str]]]:
    with open(path, encoding="latin-1", newline="") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    codes, descs = rows[0], rows[1]
    return codes, descs, {r[0]: r for r in rows[2:] if r and r[0]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["cdr", "fdic"], default="cdr")
    ap.add_argument("--skip-download", action="store_true", help="reuse the zip already in data/raw/call_reports/")
    args = ap.parse_args()

    entities = read_csv(PROCESSED / "entities.csv")
    ids = [e["rssd_id"] for e in entities]

    if args.source == "fdic":
        return build_from_fdic(entities)

    out_zip = RAW_CR / ZIP_NAME
    if not args.skip_download or not out_zip.exists():
        log("Downloading the CDR bulk file (Call Reports -- Single Period, %s) ..." % REPORT_DATE_CDR)
        info = cdr_bulk_download(out_zip)
        log(f"saved {out_zip.name} ({out_zip.stat().st_size:,} bytes; server name {info['server_filename']!r})")
    manifest = {"zip": out_zip.name, "sha256": sha256_file(out_zip), "size_bytes": out_zip.stat().st_size,
                "source_url": CDR_BULK_URL, "product": "Call Reports -- Single Period", "period": REPORT_DATE_CDR,
                "format": "TSV"}

    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(out_zip) as z:
        names = z.namelist()
        manifest["zip_members"] = names
        readme = next((n for n in names if n.lower() == "readme.txt"), None)
        if readme:
            (RAW_CR / "Readme.txt").write_bytes(z.read(readme))
        sched: dict[str, tuple] = {}
        subset_dir = RAW_CR / "subset"
        subset_dir.mkdir(parents=True, exist_ok=True)
        for key, fname in SCHEDULES.items():
            if fname not in names:
                raise SystemExit(f"{fname} not in zip; members: {names[:5]} ...")
            z.extract(fname, td)
            codes, descs, data = read_schedule(Path(td) / fname)
            sched[key] = (codes, descs, data)
            # filtered subset: dictionary rows + our banks, same column layout
            with open(subset_dir / fname.replace(" ", "_"), "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, delimiter="\t", lineterminator="\n")
                w.writerow(codes); w.writerow(descs)
                for i in ids:
                    if i in data:
                        w.writerow(data[i])
    with open(RAW_CR / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    # field map straight from the bulk-file dictionary rows
    field_map = []
    for field, skey, item, code, applies, note in ITEMS:
        fkey, codes, descs, _ = locate(sched, skey, code)
        field_map.append({"field": field, "call_report_item": item, "mdrm_code": code,
                          "bulk_file_description": descs[codes.index(code)], "bulk_file": SCHEDULES[fkey],
                          "applies_to": applies, "units": "USD thousands as reported", "note": note})
    # derived fields
    field_map += [
        {"field": "total_deposits_k", "call_report_item": "Derived: Schedule RC item 13.a + 13.b (foreign offices only for FFIEC 031 filers)",
         "mdrm_code": "RCON2200 + RCFN2200", "bulk_file_description": "", "bulk_file": SCHEDULES["RC"], "applies_to": "031/041/051",
         "units": "USD thousands", "note": "total deposits including foreign offices"},
        {"field": "total_assets_k", "call_report_item": "Derived: Schedule RC item 12 (RCFD2170 for FFIEC 031 filers, else RCON2170)",
         "mdrm_code": "RCFD2170 | RCON2170", "bulk_file_description": "", "bulk_file": SCHEDULES["RC"], "applies_to": "031/041/051",
         "units": "USD thousands", "note": ""},
        {"field": "filing_form", "call_report_item": "Bulk POR file - Financial Institution Filing Type", "mdrm_code": "n/a",
         "bulk_file_description": "Financial Institution Filing Type", "bulk_file": SCHEDULES["POR"], "applies_to": "", "units": "", "note": "031, 041 or 051"},
    ]
    write_csv(PROCESSED / "field_map.csv", field_map)

    por_codes, _, por = sched["POR"]
    pi = {c: i for i, c in enumerate(por_codes)}
    out = []
    for e in entities:
        i = e["rssd_id"]
        row = {"hc_slug": e["hc_slug"], "hc_name": e["hc_name"], "bank_name": e["bank_name"], "rssd_id": i,
               "fdic_cert": e["fdic_cert"], "report_date": REPORT_DATE}
        p = por.get(i)
        row["filing_form"] = p[pi["Financial Institution Filing Type"]] if p else ""
        row["cdr_submission_updated"] = p[pi["Last Date/Time Submission Updated On"]] if p else ""
        for field, skey, _, code, _, _ in ITEMS:
            _, codes, _, data = locate(sched, skey, code)
            r = data.get(i)
            row[field] = to_int(r[codes.index(code)]) if r else None
        dom, fgn = row["deposits_domestic_k"] or 0, row["deposits_foreign_k"] or 0
        row["total_deposits_k"] = dom + (fgn if row["filing_form"] == "031" else 0)
        row["total_assets_k"] = row["total_assets_consolidated_k"] if row["total_assets_consolidated_k"] is not None else row["total_assets_domestic_k"]
        row["source"] = "FFIEC CDR bulk " + REPORT_DATE_CDR
        out.append(row)
    write_csv(PROCESSED / "bank_detail.csv", out)
    log(f"wrote {PROCESSED / 'bank_detail.csv'} ({len(out)} banks) and field_map.csv")


def build_from_fdic(entities: list[dict]) -> None:
    """Fallback: FDIC BankFind financials (no reciprocal items available)."""
    certs = ",".join(e["fdic_cert"] for e in entities)
    raw = RAW_CR / f"fdic_financials_{REPORT_DATE_FDIC}.json"
    payload = fdic_get("financials", {"filters": f"REPDTE:{REPORT_DATE_FDIC} AND CERT:({certs.replace(',', ' OR ')})",
                                      "fields": "CERT,REPDTE,ASSET,DEP,DEPDOM,DEPFOR,BRO,BROINS", "limit": 1000}, raw)
    recs = {str(r["data"]["CERT"]): r["data"] for r in payload["data"]}
    out = []
    for e in entities:
        d = recs.get(e["fdic_cert"], {})
        out.append({"hc_slug": e["hc_slug"], "hc_name": e["hc_name"], "bank_name": e["bank_name"], "rssd_id": e["rssd_id"],
                    "fdic_cert": e["fdic_cert"], "report_date": REPORT_DATE, "filing_form": "", "cdr_submission_updated": "",
                    "reciprocal_deposits_k": None, "brokered_deposits_k": d.get("BRO"), "rco9_reciprocal_brokered_k": None,
                    "rco9a_fully_insured_reciprocal_brokered_k": None, "deposits_domestic_k": d.get("DEPDOM"),
                    "deposits_foreign_k": d.get("DEPFOR"), "total_assets_consolidated_k": None, "total_assets_domestic_k": None,
                    "total_deposits_k": d.get("DEP"), "total_assets_k": d.get("ASSET"), "source": "FDIC BankFind financials API (fallback; reciprocal items not available)"})
    write_csv(PROCESSED / "bank_detail.csv", out)
    write_csv(PROCESSED / "field_map.csv", [
        {"field": "brokered_deposits_k", "call_report_item": "RC-E M.1.b", "mdrm_code": "FDIC BRO", "bulk_file_description": "BROKERED DEP", "bulk_file": raw.name, "applies_to": "", "units": "USD thousands", "note": "FDIC API field"},
        {"field": "total_deposits_k", "call_report_item": "RC 13.a+13.b", "mdrm_code": "FDIC DEP", "bulk_file_description": "Total deposits", "bulk_file": raw.name, "applies_to": "", "units": "USD thousands", "note": ""},
        {"field": "deposits_domestic_k", "call_report_item": "RC 13.a", "mdrm_code": "FDIC DEPDOM", "bulk_file_description": "Deposits held in domestic offices", "bulk_file": raw.name, "applies_to": "", "units": "USD thousands", "note": ""},
        {"field": "total_assets_k", "call_report_item": "RC 12", "mdrm_code": "FDIC ASSET", "bulk_file_description": "Total assets", "bulk_file": raw.name, "applies_to": "", "units": "USD thousands", "note": ""},
        {"field": "reciprocal_deposits_k", "call_report_item": "RC-E M.1.g", "mdrm_code": "not available", "bulk_file_description": "", "bulk_file": "", "applies_to": "", "units": "", "note": "FDIC financials API has no reciprocal-deposit field"},
    ])
    log("wrote bank_detail.csv from the FDIC fallback (reciprocal items blank)")


if __name__ == "__main__":
    main()
