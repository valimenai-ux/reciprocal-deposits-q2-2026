#!/usr/bin/env python3
"""Step 8 - write README.md from the processed tables (sources, open items, verification)."""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROCESSED, REPO, read_csv  # noqa: E402

STATUS = {"found": "parsed", "found_not_retrievable": "published, not retrievable by an automated client",
          "not_found": "not filed / not found", "not_required": "not required"}


def main() -> None:
    sources = read_csv(PROCESSED / "sources.csv")
    items = read_csv(PROCESSED / "open_items.csv")
    summary = read_csv(PROCESSED / "summary.csv")
    with_cr = [r for r in summary if r.get("reciprocal_deposits_musd") not in ("", None)]
    total = sum(float(r["reciprocal_deposits_musd"]) for r in with_cr) / 1000
    top = sorted(with_cr, key=lambda r: -float(r["reciprocal_deposits_musd"]))[:3]
    vlog = (PROCESSED / "verification_log.md").read_text(encoding="utf-8") if (PROCESSED / "verification_log.md").exists() else ""
    v_lines = [l for l in vlog.splitlines() if l.startswith(("Result:", "Fresh CDR", "Headless", "External resource", "120 holding", "240 extracted")) or re.match(r"^\d+ (holding-company|extracted)", l)]

    src_rows = []
    for s in sources:
        link = f"[{s['disclosure_url'][:70]}...]({s['disclosure_url']})" if s.get("disclosure_url") and len(s["disclosure_url"]) > 73 else (f"[{s['disclosure_url']}]({s['disclosure_url']})" if s.get("disclosure_url") else "")
        landing = f"[landing page]({s['landing_page_url']})" if s.get("landing_page_url") else ""
        src_rows.append(f"| {s['firm']} | {STATUS.get(s['status'], s['status'])} | {s.get('pdf_file') or ''} | {link or landing} |")

    readme = f"""# Reciprocal deposits at large US banks, Q2 2026

Sizing of reciprocal deposit usage across the US holding companies that publish NSFR
disclosures (Category I-III, plus Category IV firms with >= $50bn of weighted short-term
wholesale funding), as of the 6/30/2026 Call Report, with each firm's NSFR
"sweep / brokered reciprocal / retail brokered" line (US template row 7) shown as context.
Audience: a liquidity manager. Everything needed to read the results is committed; nothing
has to be run on the reading side.

**Headline.** Across the {len(with_cr)} holding companies with insured bank subsidiaries, reciprocal
deposits (Schedule RC-E, Memorandum item 1.g, summed over insured subsidiaries) totalled
**${total:,.1f}bn** at 6/30/2026. Largest users by dollar amount: {", ".join(f"{r['hc_name']} ${float(r['reciprocal_deposits_musd'])/1000:,.1f}bn" for r in top)}.

## Open the outputs

| File | What it is |
|---|---|
| `output/reciprocal_deposits_q2_2026.html` | One self-contained page: headline, sortable table (one row per holding company), two bar charts, notes. Inline CSS/JS and hand-drawn SVG only; no CDN, fonts or network calls. Double-click it; it opens from the file system and prints on A4 landscape. |
| `output/reciprocal_deposits_q2_2026.xlsx` | The same data as plain values (no formulas, no external links). Sheets: Summary, Bank detail, NSFR detail, Sources, Notes. |
| `data/processed/*.csv` | The tidy tables behind both outputs (see below). |

The HTML was opened in headless Chromium with every non-`file://` request blocked: it
rendered completely with zero network requests and zero console errors
(`data/processed/verification/dashboard_render.png`).

## What is in the table

Per holding company: (1) reciprocal deposits, RC-E M.1.g, sum of insured bank subsidiaries;
(2) reciprocal / total deposits (deposits include foreign offices for FFIEC 031 filers);
(3) brokered reciprocal deposits, RC-O item 9, and as % of reciprocal; (4) total brokered
deposits, RC-E M.1.b, and as % of deposits; (5) NSFR row 7 unweighted total, Q2 2026
quarterly average, and as % of total retail funding (unweighted); (6) ranks on 1 and 2.
RBC US Group Holdings / City National Bank is highlighted.

The NSFR line is a **bundle** of sweep deposits, brokered reciprocal deposits and brokered
deposits from retail customers. It is labelled "NSFR sweep/reciprocal/brokered (row 7)"
everywhere and is never a reciprocal-deposit number. Call Report items are point-in-time;
NSFR amounts are quarterly averages at the consolidated holding company.

## Repository layout

```
data/reference/holding_companies.csv     the 25 holding companies, brief category vs verified category, FDIC top-holder RSSD
data/reference/nsfr_parse_overrides.json per-firm parsing hints (DWS USA only)
data/raw/call_reports/                   FFIEC CDR bulk file as served (zip), filtered subsets of RC, RC-E, RC-O, POR, manifest
data/raw/fdic/                           FDIC BankFind institutions pull (all active insured institutions) + API data dictionaries
data/raw/mdrm/                           Federal Reserve MDRM dictionary extract for the codes used (names, confidentiality windows)
data/raw/nsfr/                           every NSFR disclosure PDF that could be downloaded, <slug>_nsfr_2026q2.pdf
data/raw/reference/                      primary documents cited in the notes (FDIC interim final rule, FR PRA notice, FFIEC instructions, Public Law 119-101, Fed category listing)
data/processed/entities.csv              39 insured subsidiaries of 24 holding companies (DWS USA has none), RSSD IDs and FDIC certs
data/processed/field_map.csv             MDRM code used for every Call Report field, taken from the bulk file's dictionary rows
data/processed/bank_detail.csv           bank-level items, USD thousands as filed
data/processed/summary.csv               holding-company metrics (USD millions) and ranks
data/processed/sources.csv               NSFR disclosure per firm: status, URL, landing page, file, SHA-256, URLs checked
data/processed/nsfr_detail.csv           row 7 by maturity bucket + weighted, total retail funding, total ASF, NSFR, per firm and quarter, with PDF page numbers and extraction method
data/processed/nsfr_text_mentions.csv    every sentence containing "reciprocal" in the PDFs, with page numbers
data/processed/notes.csv                 the notes shown in the dashboard and workbook
data/processed/open_items.csv            gaps and judgment calls (also listed below)
data/processed/verification_log.md       output of scripts/07_verify.py
scripts/                                 the pipeline (01-08), see "Rebuilding"
```

## Data sources

* **Call Reports, 6/30/2026** - FFIEC Central Data Repository, Public Data Distribution, bulk
  download "Call Reports -- Single Period", 06/30/2026, tab-delimited
  (<https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx>). The zip is committed as served
  (`FFIEC CDR Call Bulk All Schedules 06302026.zip`, FFIEC extract "as of 2026-10-15");
  the MDRM codes in `field_map.csv` come from the file's own dictionary rows
  (RC-E M.1.g = RCONJH83, RC-E M.1.b = RCON2365, RC-O 9 = RCONG803, RC-O 9.a = RCONL190,
  RC 13.a = RCON2200, RC 13.b = RCFN2200, RC 12 = RCFD2170 / RCON2170) and were checked
  against the Federal Reserve MDRM dictionary (<https://www.federalreserve.gov/apps/mdrm/>).
  The FDIC BankFind financials API (<https://api.fdic.gov/banks/financials>) is the scripted
  fallback and the independent cross-check; it has no reciprocal-deposit field.
* **Entity structure** - FDIC BankFind Suite institutions API
  (<https://api.fdic.gov/banks/institutions>, docs <https://api.fdic.gov/banks/docs/>):
  every active insured institution whose regulatory top holder (`RSSDHCR`) is one of the
  holding companies (for foreign-owned firms, the foreign parent). The FFIEC NIC was not
  used because it serves a CAPTCHA challenge to automated clients (see Open items).
* **NSFR public disclosures, Q1-Q2 2026** - each firm's investor-relations site; one row per firm:

| Firm | Status | File in data/raw/nsfr | Source |
|---|---|---|---|
{chr(10).join(src_rows)}

The exact URLs tried for the firms whose disclosure could not be retrieved are in
`data/processed/sources.csv` (column `urls_checked`).

## Rebuilding (not needed to read the outputs)

Python 3.11+, `pip install -r requirements.txt`, plus `curl`, `pdftotext` (poppler) and,
for the three image-only disclosures, `tesseract`. Run from the repository root:

```
python3 -I scripts/01_fetch_fdic_institutions.py      # FDIC institutions pull -> entities.csv
python3 -I scripts/02_fetch_call_reports.py           # CDR bulk download -> field_map.csv, bank_detail.csv  (--source fdic = fallback)
python3 -I scripts/03_fetch_nsfr.py                   # download the PDFs listed in sources.csv
python3 -I scripts/04_extract_nsfr.py                 # parse the PDFs -> nsfr_detail_extracted.csv, nsfr_text_mentions.csv
python3 -I scripts/05_build_tables.py                 # nsfr_detail.csv, summary.csv (+ rollup assertion)
python3 -I scripts/06_build_outputs.py                # HTML + XLSX
python3 -I scripts/07_verify.py                       # fresh re-pull, FDIC cross-check, PDF page checks, offline render (needs playwright + node)
python3 -I scripts/08_write_readme.py                 # this file
```

`sources.csv` is the curated input for steps 03-04. To add a disclosure that was blocked
for automated clients, download it in a browser to `data/raw/nsfr/<slug>_nsfr_2026q2.pdf`,
set its `status` to `found` and `pdf_file` accordingly, and re-run steps 03-08.

## Verification (scripts/07_verify.py, full log in data/processed/verification_log.md)

{chr(10).join("* " + l for l in v_lines)}
* Every NSFR figure carries its PDF file name and page number in `nsfr_detail.csv`; five
  random figures are printed with their page text in the log, and the image-only pages
  (Morgan Stanley, HSBC North America, DWS USA) were compared with the rendered page images.

## Open items and judgment calls

{chr(10).join(f"{i+1}. **{o['item']}.** {o['detail']}" for i, o in enumerate(items))}
"""
    (REPO / "README.md").write_text(readme, encoding="utf-8")
    print(f"wrote README.md ({len(readme):,} chars)")


if __name__ == "__main__":
    main()
