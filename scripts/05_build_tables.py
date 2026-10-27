#!/usr/bin/env python3
"""Step 5 - holding-company rollups and the metrics behind the dashboard.

Reads data/processed/bank_detail.csv (call report items, USD thousands) and
data/processed/nsfr_detail_extracted.csv (NSFR figures, USD millions), writes
  * data/processed/nsfr_detail.csv  - tidy NSFR table with derived totals/ratios
  * data/processed/summary.csv      - one row per holding company:
      1. reciprocal deposits ($, sum of insured subs' RC-E M.1.g)
      2. reciprocal / total deposits (%)
      3. brokered reciprocal (RC-O item 9) and as % of reciprocal
      4. total brokered deposits and as % of total deposits
      5. NSFR row 7 unweighted total (Q2 2026 avg) and as % of total retail funding (unweighted)
      6. ranks on 1 and 2
All dollar figures in summary.csv are USD millions unless the column says otherwise.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROCESSED, holding_companies, log, read_csv, to_int, write_csv  # noqa: E402


def fnum(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def pct(a, b):
    return round(100.0 * a / b, 3) if (a is not None and b not in (None, 0)) else None


def main() -> None:
    hcs = holding_companies()
    banks = read_csv(PROCESSED / "bank_detail.csv")
    nsfr_x = read_csv(PROCESSED / "nsfr_detail_extracted.csv") if (PROCESSED / "nsfr_detail_extracted.csv").exists() else []
    sources = {s["hc_slug"]: s for s in read_csv(PROCESSED / "sources.csv")} if (PROCESSED / "sources.csv").exists() else {}

    # ---- NSFR tidy table (USD millions)
    nsfr_rows = []
    nsfr_by = {}
    for r in nsfr_x:
        buckets = [fnum(r.get(f"row7_{k}")) for k in ("open", "lt6m", "m6_1y", "ge1y", "perpetual")]
        rbuckets = [fnum(r.get(f"retail_{k}")) for k in ("open", "lt6m", "m6_1y", "ge1y", "perpetual")]
        row7_unw = sum(b for b in buckets if b is not None) if any(b is not None for b in buckets[:4]) else None
        retail_unw = sum(b for b in rbuckets if b is not None) if any(b is not None for b in rbuckets[:4]) else None
        d = dict(r)
        d["row7_unweighted_total"] = row7_unw
        d["retail_unweighted_total"] = retail_unw
        d["row7_pct_of_retail_unweighted"] = pct(row7_unw, retail_unw)
        d["row7_weighted_pct_of_retail_weighted"] = pct(fnum(r.get("row7_weighted")), fnum(r.get("retail_weighted")))
        d["row7_weighted_pct_of_total_asf"] = pct(fnum(r.get("row7_weighted")), fnum(r.get("total_asf_weighted")))
        nsfr_rows.append(d)
        nsfr_by[(r["hc_slug"], r["quarter"])] = d
    if nsfr_rows:
        cols = list(nsfr_x[0].keys()) + ["row7_unweighted_total", "retail_unweighted_total", "row7_pct_of_retail_unweighted",
                                         "row7_weighted_pct_of_retail_weighted", "row7_weighted_pct_of_total_asf"]
        write_csv(PROCESSED / "nsfr_detail.csv", nsfr_rows, cols)

    # ---- call report rollups (USD thousands -> millions)
    agg = defaultdict(lambda: defaultdict(int))
    nbanks = defaultdict(int)
    FIELDS = ("reciprocal_deposits_k", "brokered_deposits_k", "rco9_reciprocal_brokered_k", "deposits_domestic_k",
              "deposits_foreign_k", "total_deposits_k", "total_assets_k")
    for b in banks:
        s = b["hc_slug"]
        nbanks[s] += 1
        for f in FIELDS:
            agg[s][f] += to_int(b.get(f)) or 0      # blank items (e.g. foreign deposits on FFIEC 041) count as 0
    out = []
    for h in hcs:
        s = h["hc_slug"]
        a = agg.get(s)
        row = {"hc_slug": s, "hc_name": h["hc_name"], "hc_legal_name": h["hc_legal_name"], "category": h["category_task"],
               "n_insured_subs": nbanks.get(s, 0), "highlight": "yes" if s == "rbc_us" else ""}
        if a:
            m = {k: v / 1000.0 for k, v in a.items()}   # USD millions
            row.update({
                "reciprocal_deposits_musd": m["reciprocal_deposits_k"],
                "total_deposits_musd": m["total_deposits_k"],
                "deposits_domestic_musd": m["deposits_domestic_k"],
                "deposits_foreign_musd": m["deposits_foreign_k"],
                "total_assets_musd": m["total_assets_k"],
                "reciprocal_pct_of_deposits": pct(m["reciprocal_deposits_k"], m["total_deposits_k"]),
                "brokered_reciprocal_rco9_musd": m["rco9_reciprocal_brokered_k"],
                "brokered_reciprocal_pct_of_reciprocal": pct(m["rco9_reciprocal_brokered_k"], m["reciprocal_deposits_k"]),
                "total_brokered_musd": m["brokered_deposits_k"],
                "brokered_pct_of_deposits": pct(m["brokered_deposits_k"], m["total_deposits_k"]),
                "call_report_source": "FFIEC CDR bulk, Call Reports Single Period 06/30/2026 (sum of insured subsidiaries)",
            })
        else:
            row.update({"call_report_source": "no insured depository subsidiary (FDIC BankFind)"})
        src = sources.get(s, {})
        q2 = nsfr_by.get((s, "2026Q2"), {})
        q1 = nsfr_by.get((s, "2026Q1"), {})
        row.update({
            "nsfr_status": src.get("status", "not found"),
            "nsfr_row7_unweighted_total_q2_musd": q2.get("row7_unweighted_total"),
            "nsfr_row7_weighted_q2_musd": fnum(q2.get("row7_weighted")),
            "nsfr_row7_pct_of_retail_funding_q2": q2.get("row7_pct_of_retail_unweighted"),
            "nsfr_retail_funding_unweighted_q2_musd": q2.get("retail_unweighted_total"),
            "nsfr_total_asf_q2_musd": fnum(q2.get("total_asf_weighted")),
            "nsfr_ratio_q2_pct": fnum(q2.get("nsfr_ratio_pct")),
            "nsfr_row7_unweighted_total_q1_musd": q1.get("row7_unweighted_total"),
            "nsfr_ratio_q1_pct": fnum(q1.get("nsfr_ratio_pct")),
            "nsfr_pdf_file": src.get("pdf_file", ""),
            "nsfr_row7_page_q2": q2.get("row7_page", ""),
        })
        out.append(row)
    # ---- ranks (only firms with call report data)
    ranked = [r for r in out if r.get("reciprocal_deposits_musd") is not None]
    for key, rank_col in (("reciprocal_deposits_musd", "rank_reciprocal_usd"), ("reciprocal_pct_of_deposits", "rank_reciprocal_pct")):
        for i, r in enumerate(sorted(ranked, key=lambda x: -(x.get(key) or 0)), start=1):
            r[rank_col] = i
    cols = ["hc_slug", "hc_name", "hc_legal_name", "category", "n_insured_subs", "highlight",
            "reciprocal_deposits_musd", "reciprocal_pct_of_deposits", "rank_reciprocal_usd", "rank_reciprocal_pct",
            "brokered_reciprocal_rco9_musd", "brokered_reciprocal_pct_of_reciprocal", "total_brokered_musd", "brokered_pct_of_deposits",
            "total_deposits_musd", "deposits_domestic_musd", "deposits_foreign_musd", "total_assets_musd",
            "nsfr_status", "nsfr_row7_unweighted_total_q2_musd", "nsfr_row7_weighted_q2_musd", "nsfr_row7_pct_of_retail_funding_q2",
            "nsfr_retail_funding_unweighted_q2_musd", "nsfr_total_asf_q2_musd", "nsfr_ratio_q2_pct",
            "nsfr_row7_unweighted_total_q1_musd", "nsfr_ratio_q1_pct", "nsfr_pdf_file", "nsfr_row7_page_q2", "call_report_source"]
    for r in out:
        for c in cols:
            r.setdefault(c, "")
    write_csv(PROCESSED / "summary.csv", out, cols)
    tot = sum(r["reciprocal_deposits_musd"] for r in ranked)
    log(f"wrote summary.csv ({len(out)} holding companies); total reciprocal across set = ${tot/1000:,.1f}bn")
    # rollup check
    for r in ranked:
        s = sum(to_int(b["reciprocal_deposits_k"]) or 0 for b in banks if b["hc_slug"] == r["hc_slug"]) / 1000.0
        assert abs(s - r["reciprocal_deposits_musd"]) < 1e-6, r["hc_slug"]
    log("rollup check passed: holding-company reciprocal = sum of bank rows for every firm")


if __name__ == "__main__":
    main()
