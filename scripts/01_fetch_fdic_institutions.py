#!/usr/bin/env python3
"""Step 1 - entity list from the FDIC BankFind Suite institutions API.

Pulls every ACTIVE insured institution with its RSSD ID (FED_RSSD) and the RSSD ID
and name of its regulatory top holder (RSSDHCR / NAMEHCR), saves the raw JSON and the
API data dictionaries under data/raw/fdic/, then keeps the institutions whose top
holder is one of the holding companies in data/reference/holding_companies.csv and
writes data/processed/entities.csv.

The FFIEC NIC was the intended structure source but answers automated clients with a
CAPTCHA challenge, so FDIC BankFind is used instead (see README, Open items).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RAW, PROCESSED, curl, fdic_get, holding_companies, log, write_csv  # noqa: E402

FIELDS = ("CERT,NAME,FED_RSSD,RSSDHCR,NAMEHCR,STALPHCR,CITYHCR,ACTIVE,BKCLASS,CHARTER,CHRTAGNT,"
          "REGAGNT,INSAGNT1,INSFDIC,INSDIF,INSSAIF,CALLFORM,FORM31,STALP,CITY,ASSET,DEP,DEPDOM,"
          "REPDTE,EFFDATE,RUNDATE,PROCDATE,PARCERT,ULTCERT,WEBADDR,SPECGRPN,TRUST,MUTUAL,SUBCHAPS,"
          "OFFICES,NEWCERT,PRIORNAME1")

BKCLASS = {"N": "National bank (OCC)", "SM": "State member bank (Fed)", "NM": "State nonmember bank (FDIC)",
           "SB": "Savings bank", "SA": "Savings association", "OI": "Insured US branch of foreign bank"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-download", action="store_true", help="reuse the newest raw JSON already saved")
    ap.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"), help="stamp for the raw file name")
    args = ap.parse_args()

    raw_dir = RAW / "fdic"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_json = raw_dir / f"fdic_institutions_active_{args.date}.json"

    if not args.skip_download:
        log("Downloading FDIC API data dictionaries ...")
        for name in ("institution_properties.yaml", "risview_properties.yaml", "swagger.yaml"):
            curl(f"https://api.fdic.gov/banks/docs/{name}", raw_dir / f"fdic_api_{name}")
        log("Downloading all ACTIVE insured institutions ...")
        fdic_get("institutions", {"filters": "ACTIVE:1", "fields": FIELDS, "limit": 10000}, raw_json)
    else:
        cands = sorted(raw_dir.glob("fdic_institutions_active_*.json"))
        if not cands:
            sys.exit("no raw institutions file found; run without --skip-download")
        raw_json = cands[-1]

    with open(raw_json, encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = [r["data"] for r in payload["data"]]
    log(f"{len(rows)} active institutions in {raw_json.name} (index {payload['meta']['index']['name']})")

    hcs = holding_companies()
    by_holder = {h["fdic_top_holder_rssd"]: h for h in hcs if h["fdic_top_holder_rssd"]}

    out = []
    for r in rows:
        h = by_holder.get(str(r.get("RSSDHCR") or ""))
        if not h:
            continue
        out.append({
            "hc_slug": h["hc_slug"],
            "hc_name": h["hc_name"],
            "bank_name": " ".join(str(r["NAME"]).split()),
            "rssd_id": str(r["FED_RSSD"]),
            "fdic_cert": str(r["CERT"]),
            "bank_class": r.get("BKCLASS", ""),
            "bank_class_desc": BKCLASS.get(r.get("BKCLASS", ""), r.get("BKCLASS", "")),
            "charter_agent": r.get("CHRTAGNT", ""),
            "primary_regulator": r.get("REGAGNT", ""),
            "fdic_call_form": r.get("CALLFORM", ""),
            "city": r.get("CITY", ""),
            "state": r.get("STALP", ""),
            "fdic_total_assets_k": r.get("ASSET"),
            "fdic_total_deposits_k": r.get("DEP"),
            "fdic_report_date": r.get("REPDTE", ""),
            "fdic_top_holder_rssd": str(r.get("RSSDHCR")),
            "fdic_top_holder_name": r.get("NAMEHCR", ""),
            "fdic_run_date": r.get("RUNDATE", ""),
            "structure_source": f"FDIC BankFind institutions API ({raw_json.name})",
        })
    order = {h["hc_slug"]: i for i, h in enumerate(hcs)}
    out.sort(key=lambda x: (order[x["hc_slug"]], -(int(x["fdic_total_assets_k"] or 0))))
    write_csv(PROCESSED / "entities.csv", out)
    log(f"wrote {PROCESSED / 'entities.csv'}: {len(out)} insured subsidiaries across "
        f"{len({x['hc_slug'] for x in out})} holding companies")
    missing = [h["hc_name"] for h in hcs if h["hc_slug"] not in {x["hc_slug"] for x in out}]
    log(f"holding companies with no insured subsidiary in FDIC data: {missing}")


if __name__ == "__main__":
    main()
