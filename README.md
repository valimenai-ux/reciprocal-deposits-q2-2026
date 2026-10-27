# Reciprocal deposits at large US banks, Q2 2026

Sizing of reciprocal deposit usage across the US holding companies that publish NSFR
disclosures (Category I-III, plus Category IV firms with >= $50bn of weighted short-term
wholesale funding), as of the 6/30/2026 Call Report, with each firm's NSFR
"sweep / brokered reciprocal / retail brokered" line (US template row 7) shown as context.
Audience: a liquidity manager. Everything needed to read the results is committed; nothing
has to be run on the reading side.

**Headline.** Across the 24 holding companies with insured bank subsidiaries, reciprocal
deposits (Schedule RC-E, Memorandum item 1.g, summed over insured subsidiaries) totalled
**$36.7bn** at 6/30/2026. Largest users by dollar amount: Huntington $9.2bn, RBC US Group Holdings $7.4bn, UBS Americas Holding $4.5bn.

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
| JPMorgan Chase & Co. | published, not retrievable by an automated client |  | [landing page](https://jpmorganchaseco.gcs-web.com/ir/sec-other-filings/basel-pillar-and-lcr-disclosures/us-nsfr-disclosures-bank-holding-company/) |
| Bank of America Corporation | parsed | bank_of_america_nsfr_2026q2.pdf | [https://d1io3yog0oux5.cloudfront.net/_aeb230be383d47c749addfadd4ff23f1...](https://d1io3yog0oux5.cloudfront.net/_aeb230be383d47c749addfadd4ff23f1/bankofamerica/db/879/10597/pdf/1Q+and+2Q+2026+Pillar+3+U.S.+Net+Stable+Funding+Ratio+Disclosure+-+++Final_ADA.pdf) |
| Citigroup Inc. | parsed | citigroup_nsfr_2026q2.pdf | [https://www.citigroup.com/rcs/citigpa/storage/public/q2-2026-nsfr-publ...](https://www.citigroup.com/rcs/citigpa/storage/public/q2-2026-nsfr-public-disclosure.pdf) |
| Wells Fargo & Company | parsed | wells_fargo_nsfr_2026q2.pdf | [https://www.wellsfargo.com/assets/pdf/about/investor-relations/basel-d...](https://www.wellsfargo.com/assets/pdf/about/investor-relations/basel-disclosures/2026-q1-q2-nsfr-disclosure.pdf) |
| The Goldman Sachs Group, Inc. | parsed | goldman_sachs_nsfr_2026q2.pdf | [https://www.goldmansachs.com/investor-relations/financials/other-infor...](https://www.goldmansachs.com/investor-relations/financials/other-information/2026/1q-2q-nsfr-2026.pdf) |
| Morgan Stanley | parsed | morgan_stanley_nsfr_2026q2.pdf | [https://www.morganstanley.com/content/dam/msdotcom/en/about-us-ir/pdf/...](https://www.morganstanley.com/content/dam/msdotcom/en/about-us-ir/pdf/US_NSFR_Disclosures_06302026.pdf) |
| The Bank of New York Mellon Corporation | parsed | bny_nsfr_2026q2.pdf | [https://www.bny.com/content/dam/bnymellon/documents/pdf/investor-relat...](https://www.bny.com/content/dam/bnymellon/documents/pdf/investor-relations/q2-2026-nsfr-disclosure.pdf) |
| State Street Corporation | parsed | state_street_nsfr_2026q2.pdf | [https://s203.q4cdn.com/888565246/files/doc_downloads/2026/08/1Q26-2Q26...](https://s203.q4cdn.com/888565246/files/doc_downloads/2026/08/1Q26-2Q26-STT-NSFR-Disclosure-v-F.pdf) |
| Northern Trust Corporation | published, not retrievable by an automated client |  | [https://www.northerntrust.com/content/dam/northerntrust/pws/nt/documen...](https://www.northerntrust.com/content/dam/northerntrust/pws/nt/documents/earnings/net-stable-funding/net-stable-funding-ratio-disclosure-jun-2026.pdf) |
| American Express Company | published, not retrievable by an automated client |  | [landing page](https://ir.americanexpress.com/) |
| U.S. Bancorp | published, not retrievable by an automated client |  | [landing page](https://ir.usbank.com/financials/Supporting-Documents/default.aspx) |
| The PNC Financial Services Group, Inc. | parsed | pnc_nsfr_2026q2.pdf | [https://d1io3yog0oux5.cloudfront.net/_abb435f92c236359b15e9d11a31f96f5...](https://d1io3yog0oux5.cloudfront.net/_abb435f92c236359b15e9d11a31f96f5/pnc/db/2467/24025/disclosure/Q2+2026+LCR_NSFR+Disclosures_FINAL.pdf) |
| Truist Financial Corporation | parsed | truist_nsfr_2026q2.pdf | [https://ir.truist.com/download/TFC_1H26_NSFR_Disclosures.pdf](https://ir.truist.com/download/TFC_1H26_NSFR_Disclosures.pdf) |
| Capital One Financial Corporation | published, not retrievable by an automated client |  | [landing page](https://investor.capitalone.com/net-stable-funding-ratio-disclosures) |
| The Charles Schwab Corporation | published, not retrievable by an automated client |  | [landing page](https://www.aboutschwab.com/regulatory-disclosures) |
| Fifth Third Bancorp | not required |  | [landing page](https://ir.53.com/) |
| Huntington Bancshares Incorporated | not required |  | [landing page](https://ir.huntington.com/) |
| Barclays US LLC | parsed | barclays_us_nsfr_2026q2.pdf | [https://home.barclays/content/dam/home-barclays/documents/investor-rel...](https://home.barclays/content/dam/home-barclays/documents/investor-relations/usfilings/1H26%20Barclays%20IHC%20US%20NSFR%20Disclosure.pdf) |
| DB USA Corporation | parsed | db_usa_nsfr_2026q2.pdf | [https://investor-relations.db.com/files/documents/regulatory-reporting...](https://investor-relations.db.com/files/documents/regulatory-reporting/2026/DBUSACorporationUSNetStableFundingRatioDisclosures2Q2026.pdf) |
| TD Group US Holdings LLC | parsed | td_group_us_nsfr_2026q2.pdf | [https://www.td.com/content/dam/tdcom/canada/about-td/pdf/quarterly-res...](https://www.td.com/content/dam/tdcom/canada/about-td/pdf/quarterly-results/2026/q2/2026-q1-q2-tdgus-nsfr-public-disclosure.pdf) |
| UBS Americas Holding LLC | parsed | ubs_americas_nsfr_2026q2.pdf | [https://www.ubs.com/global/en/investor-relations/complementary-financi...](https://www.ubs.com/global/en/investor-relations/complementary-financial-information/disclosure-legal-entities/ubs-americas-holding-llc/_jcr_content/root/contentarea/mainpar/toplevelgrid/col_1/linklistnewlook_2483/link_copy_copy_copy__1649801341.1476892854.file/PS9jb250ZW50L2RhbS9hc3NldHMvY2MvaW52ZXN0b3ItcmVsYXRpb25zL3Vicy1hbWVyaWNhcy1ob2xkaW5nLWxsYy9xMi1haGxsYy1uc2ZyLWRpc2Nsb3N1cmUtZmluYWwyNi5wZGY=/q2-ahllc-nsfr-disclosure-final26.pdf) |
| BMO Financial Corp. | published, not retrievable by an automated client |  | [https://www.bmo.com/ir/files/F26%20Files/NSFRCY26Q2.pdf](https://www.bmo.com/ir/files/F26%20Files/NSFRCY26Q2.pdf) |
| HSBC North America Holdings Inc. | parsed | hsbc_north_america_nsfr_2026q2.pdf | [https://www.about.us.hsbc.com/-/media/us/en/hsbc-in-the-usa/regulatory...](https://www.about.us.hsbc.com/-/media/us/en/hsbc-in-the-usa/regulatory-information/260813-net-stable-funding-ratio-disclosure-semi-annual-report-june-30-2026.pdf?sc_lang=en-GB&hash=9AD29B8C344AC6E177F68CC17C26E03C) |
| RBC US Group Holdings LLC | not filed / not found |  | [landing page](https://www.rbc.com/investor-relations/regulatory-information.html) |
| DWS USA Corporation | parsed | dws_usa_nsfr_2026q2.pdf | [https://download.dws.com/download/asset/dd9145e9-ea98-4242-af38-adb3e6...](https://download.dws.com/download/asset/dd9145e9-ea98-4242-af38-adb3e68aa3de) |

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

* Fresh CDR bulk file downloaded 2026-10-27T23:13:03+00:00 (5,981,366 bytes).
* Result: all 5 pairs match.
* Result: all FDIC values match.
* 120 holding-company totals checked against the sum of their bank rows: all equal.
* 240 extracted figures checked for presence on their recorded PDF page (text layer): 206 found verbatim; 34 not in the text layer, all of them on image-only (OCR) pages or manual entries read from the page image.
* External resource tags (script/link/img/iframe with http(s) URLs): 0. Hyperlinks to sources in the notes: 19 (anchors only; nothing is loaded).
* Headless Chromium, all non-file:// requests aborted: network requests attempted = 0, console/page errors = 0, table rows = 25, charts = 2, bars = 48, note items = 66, page height = 8221px; first row after sorting by reciprocal $ descending = Huntington. Screenshot: data/processed/verification/dashboard_render.png
* Every NSFR figure carries its PDF file name and page number in `nsfr_detail.csv`; five
  random figures are printed with their page text in the log, and the image-only pages
  (Morgan Stanley, HSBC North America, DWS USA) were compared with the rendered page images.

## Open items and judgment calls

1. **Structure source.** Subsidiary lists and RSSD IDs were verified against the FDIC BankFind Suite institutions API (fields FED_RSSD, RSSDHCR, NAMEHCR; data index of 23 October 2026), not the FFIEC NIC, because NIC (www.ffiec.gov) serves a Cloudflare CAPTCHA to automated clients. Both draw on Federal Reserve structure data, but NIC itself was not consulted. The FDIC list reflects active institutions at the time of the pull (late October 2026), not exactly 6/30/2026; all 39 banks have 6/30/2026 Call Reports in the CDR file.
2. **IHC attribution.** For foreign-owned firms the FDIC top holder is the foreign parent (Barclays PLC, Deutsche Bank AG, The Toronto-Dominion Bank, UBS Group AG, Bank of Montreal, HSBC Holdings plc, Royal Bank of Canada). Their US insured banks are attributed to the US (intermediate) holding company named in the brief; the attribution of the smaller banks (RBC Bank (Georgia) N.A., Deutsche Bank Trust Company Delaware, HSBC Trust Company (Delaware) N.A., BMO Harris Central N.A., TD Bank USA N.A.) to the IHC is inferred from the parent, not read from NIC.
3. **Subsidiaries beyond the brief.** FDIC data adds insured subsidiaries the brief did not list, all included in the rollups: Bank of America California N.A.; JPMorgan Chase Bank, Dearborn; Wells Fargo National Bank West and Wells Fargo Bank South Central N.A.; BNY Mellon N.A., The Bank of New York Mellon Trust Company N.A. and BNY Mellon Trust of Delaware; Deutsche Bank Trust Company Delaware; TD Bank USA N.A.; BMO Harris Central N.A.; HSBC Trust Company (Delaware) N.A.; RBC Bank (Georgia) N.A. All report zero reciprocal deposits except none; they add deposits to the denominators. DWS USA Corporation has no insured depository subsidiary.
4. **NSFR disclosures not retrievable.** Seven firms publish a Q1-Q2 2026 NSFR disclosure that could not be downloaded by an automated client (JPMorgan Chase, Capital One, Charles Schwab, U.S. Bancorp, American Express: HTTP 403 bot protection on the IR host; Northern Trust and BMO: connection closed without a response). Their NSFR columns are blank. URLs checked are in data/processed/sources.csv. Manual fix: download in a browser to data/raw/nsfr/<slug>_nsfr_2026q2.pdf, set status=found, re-run scripts 04-07.
5. **NSFR not required / not filed.** Fifth Third (Category IV in Q2 2026; Category III from Q3 2026) and Huntington (Category IV) had no NSFR requirement and publish nothing. RBC US Group Holdings LLC appears as Category III in the Federal Reserve's June 2026 listing (Category IV in 2025) but has published no NSFR disclosure; under the rule's transition timing none is expected for Q2 2026. Nothing was estimated for these firms.
6. **Category corrections.** BMO Financial Corp. is Category III (85% NSFR), not Category IV; Charles Schwab and TD Group US Holdings run the full 100% NSFR; American Express became Category II during Q2 2026 with an 85% transition factor; RBC US moved to Category III. The brief's labels are kept in the 'category' column and the verified values in data/reference/holding_companies.csv (category_verified).
7. **RC-O item 9.a.** Schedule RC-O item 9.a (RCONL190, 'Fully consolidated reciprocal brokered deposits') is completed only by institutions that consolidate another insured depository institution; none of the 39 banks report it (12 banks in the whole population do, all zero). It is shown as not applicable, not as zero.
8. **Pre-rule call report.** The 6/30/2026 Call Report precedes the FDIC interim final rule of September 1, 2026 (tiered cap up to $30bn) and the ROAD to Housing Act of July 11, 2026; RC-O item 9 amounts reflect the old cap (lesser of $5bn or 20% of liabilities). From the 9/30/2026 report date RC-O items 9 and 9.a are confidential, so this is the last public quarter for the brokered-reciprocal split.
9. **Zero reciprocal balances.** 11 of the 24 holding companies with insured banks report zero reciprocal deposits in RC-E Memorandum item 1.g (including JPMorgan Chase, Citigroup, Wells Fargo, Goldman Sachs, State Street, Northern Trust, American Express, Charles Schwab, Barclays US, TD Group US, BMO). These are reported values, not missing data.
10. **OCR-derived NSFR figures.** Morgan Stanley, HSBC North America and DWS USA publish image-only tables. Figures were OCR'd (five variants voting) and then checked visually against the rendered page images; DWS USA's template omits the retail rows, so its row 7 is nil by construction. HSBC's Q2 2026 ratio is taken from table row 40 (129.3%).
11. **Data vintage.** The CDR bulk file is the FFIEC's 'as of 2026-10-15' extract (see data/raw/call_reports/Readme.txt); amendments filed after that date are not reflected. NSFR PDFs were downloaded on 27 October 2026 and their SHA-256 hashes are recorded in data/processed/sources.csv.
12. **Units and rounding.** Call Report items are in USD thousands as filed; NSFR amounts are in USD millions as published (DWS USA to two decimals). The dashboard shows $bn to two decimals and percentages to two decimals; the spreadsheet carries the full values.
