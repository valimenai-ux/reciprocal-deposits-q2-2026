# Verification log

Run: 2026-10-27T23:13:01+00:00 UTC, random seed 20260630.

## 1. Call report re-pull (fresh CDR download) and FDIC cross-check

Fresh CDR bulk file downloaded 2026-10-27T23:13:03+00:00 (5,981,366 bytes).

| Bank | Item | MDRM | Fresh CDR value | bank_detail.csv | Match |
|---|---|---|---:|---:|---|
| State Street Bank and Trust Company | deposits_domestic_k | RCON2200 | 242086000 | 242086000 | OK |
| PNC Bank, National Association | rco9_reciprocal_brokered_k | RCONG803 | 0 | 0 | OK |
| HSBC Bank USA, National Association | deposits_domestic_k | RCON2200 | 134778621 | 134778621 | OK |
| American Express National Bank | reciprocal_deposits_k | RCONJH83 | 0 | 0 | OK |
| HSBC Trust Company (Delaware), National Association | brokered_deposits_k | RCON2365 | 0 | 0 | OK |

Result: all 5 pairs match.

FDIC BankFind financials (independent source, USD thousands) for the same banks:

| Bank | Field | FDIC value | bank_detail.csv | Match |
|---|---|---:|---:|---|
| State Street Bank and Trust Company | ASSET vs total_assets_k | 412620000 | 412620000 | OK |
| State Street Bank and Trust Company | DEP vs total_deposits_k | 326247000 | 326247000 | OK |
| State Street Bank and Trust Company | DEPDOM vs deposits_domestic_k | 242086000 | 242086000 | OK |
| State Street Bank and Trust Company | BRO vs brokered_deposits_k | 14835000 | 14835000 | OK |
| PNC Bank, National Association | ASSET vs total_assets_k | 609771726 | 609771726 | OK |
| PNC Bank, National Association | DEP vs total_deposits_k | 457798362 | 457798362 | OK |
| PNC Bank, National Association | DEPDOM vs deposits_domestic_k | 457090936 | 457090936 | OK |
| PNC Bank, National Association | BRO vs brokered_deposits_k | 2056844 | 2056844 | OK |
| HSBC Bank USA, National Association | ASSET vs total_assets_k | 173101278 | 173101278 | OK |
| HSBC Bank USA, National Association | DEP vs total_deposits_k | 141192598 | 141192598 | OK |
| HSBC Bank USA, National Association | DEPDOM vs deposits_domestic_k | 134778621 | 134778621 | OK |
| HSBC Bank USA, National Association | BRO vs brokered_deposits_k | 21886456 | 21886456 | OK |
| American Express National Bank | ASSET vs total_assets_k | 213946192 | 213946192 | OK |
| American Express National Bank | DEP vs total_deposits_k | 171554868 | 171554868 | OK |
| American Express National Bank | DEPDOM vs deposits_domestic_k | 171554868 | 171554868 | OK |
| American Express National Bank | BRO vs brokered_deposits_k | 23580530 | 23580530 | OK |
| HSBC Trust Company (Delaware), National Association | ASSET vs total_assets_k | 57157 | 57157 | OK |
| HSBC Trust Company (Delaware), National Association | DEP vs total_deposits_k | 500 | 500 | OK |
| HSBC Trust Company (Delaware), National Association | DEPDOM vs deposits_domestic_k | 500 | 500 | OK |
| HSBC Trust Company (Delaware), National Association | BRO vs brokered_deposits_k | 0 | 0 | OK |

Result: all FDIC values match.

## 2. Holding-company rollups

120 holding-company totals checked against the sum of their bank rows: all equal.

## 3. NSFR figures against the PDFs

240 extracted figures checked for presence on their recorded PDF page (text layer): 206 found verbatim; 34 not in the text layer, all of them on image-only (OCR) pages or manual entries read from the page image.

| Firm | Quarter | Field | Value | Page | Method |
|---|---|---|---:|---:|---|
| morgan_stanley | 2026Q2 | row7_open | 138,275 | 5 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q2 | row7_lt6m | 21,713 | 5 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q2 | row7_m6_1y | 16,554 | 5 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q2 | row7_ge1y | 63,073 | 5 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q2 | row7_weighted | 183,475 | 5 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q2 | retail_weighted | 325,451 | 5 | ocr (1/3 variants agree) CHECK |
| morgan_stanley | 2026Q2 | total_asf_weighted | 787,900 | 5 | ocr (4/4 variants agree) |
| morgan_stanley | 2026Q2 | nsfr_ratio_pct | 116 | 5 | ocr (3/3 variants agree) |
| morgan_stanley | 2026Q1 | row7_open | 134,934 | 6 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q1 | row7_lt6m | 21,253 | 6 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q1 | row7_m6_1y | 16,709 | 6 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q1 | row7_ge1y | 56,678 | 6 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q1 | row7_weighted | 175,126 | 6 | ocr (4/5 variants agree) |
| morgan_stanley | 2026Q1 | retail_weighted | 313,963 | 6 | ocr (4/4 variants agree) |
| morgan_stanley | 2026Q1 | total_asf_weighted | 745,258 | 6 | ocr (3/3 variants agree) |
| morgan_stanley | 2026Q1 | nsfr_ratio_pct | 118 | 6 | ocr (2/2 variants agree) |
| hsbc_north_america | 2026Q2 | row7_open | 17,234 | 8 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q2 | row7_lt6m | 287 | 8 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q2 | row7_m6_1y | 346 | 8 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q2 | row7_ge1y | 2,732 | 8 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q2 | row7_weighted | 11,249 | 8 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q2 | retail_weighted | 32,179 | 8 | ocr (1/1 variants agree) CHECK |
| hsbc_north_america | 2026Q2 | total_asf_weighted | 82,984 | 8 | ocr (3/3 variants agree) |
| hsbc_north_america | 2026Q2 | nsfr_ratio_pct | 129.3 | 8 | ocr (3/3 variants agree) |
| hsbc_north_america | 2026Q1 | row7_open | 17,193 | 7 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q1 | row7_lt6m | 259 | 7 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q1 | row7_m6_1y | 370 | 7 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q1 | row7_ge1y | 2,728 | 7 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q1 | row7_weighted | 11,236 | 7 | ocr (2/3 variants agree) |
| hsbc_north_america | 2026Q1 | retail_weighted | 32,119 | 7 | ocr (1/1 variants agree) CHECK |
| hsbc_north_america | 2026Q1 | total_asf_weighted | 80,859 | 7 | ocr (5/5 variants agree) |
| hsbc_north_america | 2026Q1 | nsfr_ratio_pct | 129.6 | 7 | ocr (3/3 variants agree) |
| dws_usa | 2026Q2 | nsfr_ratio_pct | 123.72 | 8 | manual: row 39 of the page-8 table image (OCR reads 123.72%; equals Total ASF 1,810.05 / Total adjusted RSF 1,463.01) |
| dws_usa | 2026Q1 | nsfr_ratio_pct | 122.83 | 8 | manual: row 39 of the page-8 table image (OCR variant psm4 reads 122.83%; equals Total ASF 1,786.21 / Total adjusted RSF 1,454.27) |

Five random figures with the page text around them (human spot-check):

- **The Bank of New York Mellon Corporation**, 2026Q1, `retail_weighted` = 21,042 — bny_nsfr_2026q2.pdf p.7: `4          Retail funding:                                                        26,247             2,872             2,658            2,361              -    `
- **The PNC Financial Services Group, Inc.**, 2026Q2, `row7_weighted` = 5,930 — pnc_nsfr_2026q2.pdf p.8: `7         Sweep deposits, brokered reciprocal deposits and brokered deposits                                6,971         185          226           2          `
- **DWS USA Corporation**, 2026Q1, `total_asf_weighted` = 1786.21 — dws_usa_nsfr_2026q2.pdf p.5: `(not in text layer - OCR page)`
- **HSBC North America Holdings Inc.**, 2026Q2, `retail_weighted` = 32,179 — hsbc_north_america_nsfr_2026q2.pdf p.8: `(not in text layer - OCR page)`
- **State Street Corporation**, 2026Q2, `total_asf_weighted` = 164,051 — state_street_nsfr_2026q2.pdf p.6: `15   Total ASF                                                                                                               164,051`

OCR-derived rows (image-only table pages), confirmed visually against the rendered page image during the build:

- Morgan Stanley 2026Q2: morgan_stanley_nsfr_2026q2.pdf p.5 (ocr (4/5 variants agree))
- Morgan Stanley 2026Q1: morgan_stanley_nsfr_2026q2.pdf p.6 (ocr (4/5 variants agree))
- HSBC North America Holdings Inc. 2026Q2: hsbc_north_america_nsfr_2026q2.pdf p.8 (ocr (2/3 variants agree))
- HSBC North America Holdings Inc. 2026Q1: hsbc_north_america_nsfr_2026q2.pdf p.7 (ocr (2/3 variants agree))

## 4. Offline render of the HTML dashboard

External resource tags (script/link/img/iframe with http(s) URLs): 0. Hyperlinks to sources in the notes: 19 (anchors only; nothing is loaded).

Headless Chromium, all non-file:// requests aborted: network requests attempted = 0, console/page errors = 0, table rows = 25, charts = 2, bars = 48, note items = 66, page height = 8221px; first row after sorting by reciprocal $ descending = Huntington. Screenshot: data/processed/verification/dashboard_render.png

