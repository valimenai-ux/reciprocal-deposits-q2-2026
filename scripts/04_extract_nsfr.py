#!/usr/bin/env python3
"""Step 4 - extract NSFR figures from the downloaded disclosure PDFs.

For every row of data/processed/sources.csv with a PDF in data/raw/nsfr/, the script
reads each page with pdfplumber (text layer). Pages whose table is an embedded image
(no text layer) are rendered with pdftoppm and OCR'd with tesseract in several
resolution / page-segmentation variants; the variants vote and the winning parse is
marked extraction_method = "ocr (k/n variants agree)". OCR figures are eyeballed
against the page image during verification (scripts/07_verify.py; README).

Extracted per firm and quarter (Q1 2026, Q2 2026), with PDF file name and page number:
  * US template row 7 "Sweep deposits, brokered reciprocal deposits, and brokered
    deposits provided by a retail customer or counterparty": average unweighted amounts
    by residual maturity (open maturity, < 6 months, 6 months to < 1 year, >= 1 year,
    plus a "perpetual" column where the firm prints one) and the average weighted amount
  * Total retail funding (template row 4 "Retail funding" total line or a "Total retail
    funding" row), unweighted buckets and weighted amount
  * Total ASF (weighted)
  * The reported NSFR ratio
  * Every sentence mentioning "reciprocal" (data/processed/nsfr_text_mentions.csv)

The row-7 figure is a BUNDLE (sweep + brokered reciprocal + retail brokered). It is
labelled "NSFR sweep/reciprocal/brokered (row 7)" everywhere downstream.

Per-firm parsing hints (page -> quarter, column layout, manual values read off the page
by a person, with the page cited) can be given in data/reference/nsfr_parse_overrides.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROCESSED, RAW, REFERENCE, log, read_csv, write_csv  # noqa: E402

import pdfplumber  # noqa: E402

RAW_NSFR = RAW / "nsfr"
DEBUG = False
Q2, Q1 = "2026Q2", "2026Q1"

Q_PATTERNS = {
    Q2: [r"june\s*30,?\s*2026", r"06/30/2026", r"6/30/2026", r"second quarter (of )?2026", r"\b2Q\s?2026", r"\bQ2\s?2026",
         r"april 1,? (2026 )?(to|through) june 30,? 2026", r"\b2Q26\b", r"30 june 2026", r"jun(e)?[\s-]+2026"],
    Q1: [r"march\s*31,?\s*2026", r"03/31/2026", r"3/31/2026", r"first quarter (of )?2026", r"\b1Q\s?2026", r"\bQ1\s?2026",
         r"january 1,? (2026 )?(to|through) march 31,? 2026", r"\b1Q26\b", r"31 march 2026", r"mar(ch)?[\s-]+2026"],
}

ROW7_RE = re.compile(r"sweep\s+deposits,?\s+brokered\s+reciprocal\s+deposits", re.I)
RETAIL_RE = re.compile(r"^\s*\(?(\d{1,2}\)?[\.\)]?\s+)?(total\s+)?retail\s+funding\b", re.I)
TOTAL_ASF_RE = re.compile(r"^\s*\(?(\d{1,2}\)?[\.\)]?\s+)?total\s+(available\s+stable\s+funding|asf)(?![a-z])", re.I)
NSFR_RE = re.compile(r"net\s+stable\s+funding\s+ratio|nsfr\s+stable\s+funding\s+ratio|^\s*\(?40\)?[\.\)]?\s+[A-Za-z (]*ratio", re.I)
ROWSTART_RE = re.compile(r"^\s*\(?\d{1,2}\)?[\.\)]?\s+[A-Za-z(]")
NUM_RE = re.compile(r"\(?\$?\d{1,3}(?:[,\.]\d{3})+\)?|\(?\$?\d+(?:\.\d+)?%?\)?|(?<![\w/])[-–—](?![\w/])")
OCR_VARIANTS = [(400, 4), (300, 4), (400, 6), (600, 6), (300, 6)]
KEYS = {"std": ["open", "lt6m", "m6_1y", "ge1y", "weighted"],
        "perp": ["open", "lt6m", "m6_1y", "ge1y", "perpetual", "weighted"]}


def numbers_in(s: str) -> list[float]:
    """Numeric tokens of a table fragment, in order. A lone '-'/'—' (nil) counts as 0."""
    out: list[float] = []
    for tok in NUM_RE.findall(s):
        t = tok.strip()
        if t in ("-", "–", "—"):
            out.append(0.0)
            continue
        neg = t.startswith("(") and t.endswith(")")
        t = t.strip("()$%")
        if re.fullmatch(r"\d{1,3}(?:[,\.]\d{3})+", t):
            t = re.sub(r"[,\.]", "", t)
        try:
            v = float(t)
        except ValueError:
            continue
        out.append(-v if neg else v)
    return out


def tail_after(line: str, end: int) -> str:
    """Numeric tail of a table line after the label match ending at ``end``."""
    rest = re.sub(r"\(\d\)", "", line[end:])
    rest = re.sub(r"(\d)\s+,\s*(\d{3})", r"\1,\2", rest)   # "1 ,312,393" -> "1,312,393" (split separator)
    rest = re.sub(r"(\d),\s+(\d{3})", r"\1,\2", rest)
    rest = re.sub(r"^\s*\d(?=\s)", "", rest)        # footnote digit glued to the label ("Total ASF1 1,351,857")
    m = re.search(r"\(?\$?\d|(?<![\w/])[-–—](?![\w/])", rest)
    return rest[m.start():] if m else ""


def numeric_line(s: str) -> bool:
    """A continuation line holding only numbers / nil markers (no real words)."""
    return bool(re.search(r"\d|[-–—]", s)) and not re.search(r"[A-Za-z]{3,}", s)


def tokens_pos(line: str, start: int = 0) -> list[tuple[int, float]]:
    """(character position, value) of every numeric token at or after ``start``."""
    seg = line[start:]
    seg = re.sub(r"\(\d\)", lambda m: " " * len(m.group(0)), seg)            # footnote markers
    seg = re.sub(r"(\d)\s+,\s*(\d{3})", lambda m: m.group(1) + "," + m.group(2), seg)   # "1 ,312,393"
    seg = re.sub(r"^(\s*)\d(?=\s)", lambda m: m.group(1) + " ", seg)          # footnote digit glued to label
    out = []
    for m in NUM_RE.finditer(seg):
        vals = numbers_in(m.group(0))
        if vals:
            out.append((start + m.start(), vals[0]))
    return out


def row_tail(lines: list[str], idx: int, end: int, aligned: bool = False, want: int | None = None) -> tuple[list[float], str]:
    """Numbers of the table row whose label match ends at ``end`` on lines[idx].

    Labels can wrap, and a row's numbers can sit on the line after the label and/or (one
    column, typically the weighted amount) on the line before it. Lines are combined when
    the label line is incomplete (< 5 numbers). For layout-preserving text (``aligned``,
    pdftotext -layout) tokens are ordered by character column across the lines; otherwise
    in the order: label line, following line(s), preceding line."""
    own = tokens_pos(lines[idx], end)
    raw = [lines[idx]]
    need = want or 5
    if len(own) >= need:
        return [v for _, v in own], lines[idx]
    nxt: list[tuple[int, float]] = []
    j = idx + 1
    while j < len(lines) and j <= idx + 2 and numeric_line(lines[j]):
        nxt += tokens_pos(lines[j]); raw.append(lines[j]); j += 1
    if not nxt:   # wrapped label: the numbers may follow the label's continuation line
        j = idx + 1
        while j < len(lines) and j <= idx + 2 and not ROWSTART_RE.match(lines[j]) and not numeric_line(lines[j]):
            lastw = None
            for lastw in re.finditer(r"[A-Za-z%:'\u2019]{2,}", lines[j]):
                pass
            cand = tokens_pos(lines[j], lastw.end() if lastw else 0)
            if len(cand) >= 2:
                nxt += cand; raw.append(lines[j]); break
            j += 1
    prv = tokens_pos(lines[idx - 1]) if idx > 0 and numeric_line(lines[idx - 1]) and len(own) + len(nxt) < need else []
    if prv:
        raw.insert(0, lines[idx - 1])
    if aligned:
        toks = sorted(own + nxt + prv, key=lambda t: t[0])
    else:
        toks = own + nxt + prv
    return [v for _, v in toks], " // ".join(raw)


def detect_quarters(text: str) -> list[str]:
    """Quarters mentioned in ``text``, ordered by first appearance."""
    t = text.lower()
    found = []
    for q, pats in Q_PATTERNS.items():
        pos = [m.start() for p in pats for m in [re.search(p, t)] if m]
        if pos:
            found.append((min(pos), q))
    return [q for _, q in sorted(found)]


def nearest_quarter(text_before: str, default: str) -> str:
    t = text_before.lower()
    best = (-1, default)
    for q, pats in Q_PATTERNS.items():
        for p in pats:
            for m in re.finditer(p, t):
                if m.start() > best[0]:
                    best = (m.start(), q)
    return best[1]


def split_columns(nums: list[float], nq: int, hint: str) -> list[dict] | None:
    order = ["perp", "std"] if hint == "perp" else ["std", "perp"]
    for layout in order:
        k = KEYS[layout]
        if nq == 2 and len(nums) == 2 * len(k):
            return [dict(zip(k, nums[:len(k)])), dict(zip(k, nums[len(k):]))]
        if nq == 1 and len(nums) == len(k):
            return [dict(zip(k, nums))]
    return None


def ocr_page(pdf_path: Path, page_no: int, dpi: int, psm: int) -> str:
    with tempfile.TemporaryDirectory() as td:
        prefix = Path(td) / "pg"
        subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page_no), "-l", str(page_no), "-gray", "-png",
                        str(pdf_path), str(prefix)], check=True)
        png = next(Path(td).glob("pg*.png"))
        subprocess.run(["tesseract", str(png), str(prefix), "--psm", str(psm)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return (Path(td) / "pg.txt").read_text(encoding="utf-8", errors="replace")


def pdftotext_page(pdf_path: Path, page_no: int) -> str:
    r = subprocess.run(["pdftotext", "-layout", "-f", str(page_no), "-l", str(page_no), str(pdf_path), "-"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def page_candidates(pdf_path: Path) -> list[tuple[int, list[tuple[str, str]]]]:
    """[(page_no, [(method, text), ...])] - two text-layer readers (pdfplumber, pdftotext -layout);
    OCR variants are added for image-only table pages."""
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, p in enumerate(pdf.pages, start=1):
            text = p.extract_text() or ""
            cands = [("text", text), ("pdftotext", pdftotext_page(pdf_path, i))]
            big_image = any((im["x1"] - im["x0"]) * (im["bottom"] - im["top"]) > 0.3 * float(p.width) * float(p.height) for im in p.images)
            if big_image and not any(ROW7_RE.search(t) or RETAIL_RE.search(t) for _, t in cands):
                for dpi, psm in OCR_VARIANTS:
                    try:
                        o = ocr_page(pdf_path, i, dpi, psm)
                    except Exception as e:  # pragma: no cover
                        log(f"OCR failed on {pdf_path.name} p{i} @{dpi}/psm{psm}: {e}")
                        continue
                    if ROW7_RE.search(o) or RETAIL_RE.search(o) or NSFR_RE.search(o):
                        cands.append((f"ocr{dpi}p{psm}", text + "\n" + o))
            out.append((i, cands))
    return out


def parse_text(text: str, qs: list[str], hint: str, aligned: bool = False) -> dict:
    """{quarter: {field: value}} for the rows found in one page text."""
    found: dict[str, dict] = {}
    lines = text.splitlines()
    # pass 1: the column count of the row-7 line fixes the table layout for the page
    ncols: int | None = None
    for idx, line in enumerate(lines):
        m7 = ROW7_RE.search(line)
        if m7:
            nums, _ = row_tail(lines, idx, m7.end(), aligned)
            nq = 2 if (len(qs) == 2 and len(nums) in (10, 12)) else 1
            if split_columns(nums, nq, hint):
                ncols = len(nums) // nq
                break
    for idx, line in enumerate(lines):
        m7 = ROW7_RE.search(line)
        mr = RETAIL_RE.search(line) if not re.search(r"other retail", line, re.I) else None
        if m7 or mr:
            prefix, m = ("row7", m7) if m7 else ("retail", mr)
            nums, raw = row_tail(lines, idx, m.end(), aligned, ncols)
            if ncols and len(nums) not in (ncols, 2 * ncols):
                if DEBUG:
                    log(f"      ? {prefix}: {len(nums)} numbers but row 7 had {ncols}: {raw!r}")
                continue
            nq = 2 if (len(qs) == 2 and len(nums) in (10, 12)) else 1
            cols = split_columns(nums, nq, hint)
            if not cols:
                if DEBUG:
                    log(f"      ? {prefix}: {len(nums)} numbers {nums} from {raw!r}")
                continue
            targets = qs[:2] if nq == 2 else [nearest_quarter("\n".join(lines[:idx]), qs[0]) if len(qs) > 1 else qs[0]]
            for q, c in zip(targets, cols):
                d = found.setdefault(q, {})
                if f"{prefix}_weighted" in d:
                    continue
                d.update({f"{prefix}_{k}": v for k, v in c.items()})
                d[f"{prefix}_raw_line"] = " ".join(raw.split())[:300]
        elif TOTAL_ASF_RE.search(line):
            m = TOTAL_ASF_RE.search(line)
            nums = [n for n in numbers_in(tail_after(line, m.end())) if n]
            if not nums and idx + 1 < len(lines) and not re.search(r"[A-Za-z]{4}", lines[idx + 1]):
                nums = [n for n in numbers_in(lines[idx + 1]) if n]
            if not nums:
                continue
            if len(qs) == 2 and len(nums) >= 2:
                pairs = list(zip(qs, nums[-2:]))
            else:
                q = nearest_quarter("\n".join(lines[:idx]), qs[0]) if len(qs) > 1 else qs[0]
                pairs = [(q, nums[-1])]
            for q, v in pairs:
                d = found.setdefault(q, {})
                d.setdefault("total_asf_weighted", v)
                d.setdefault("total_asf_raw_line", " ".join(line.split())[:300])
        elif NSFR_RE.search(line):
            m = NSFR_RE.search(line)
            vals = [v for v in numbers_in(tail_after(line, m.end())) if 50 <= v <= 400]
            if not vals and idx + 1 < len(lines) and not re.search(r"[A-Za-z]{4}", lines[idx + 1]):
                vals = [v for v in numbers_in(lines[idx + 1]) if 50 <= v <= 400]
            if not vals:
                continue
            if len(qs) == 2 and len(vals) >= 2:
                pairs = list(zip(qs, vals[:2]))
            else:
                q = nearest_quarter("\n".join(lines[:idx]), qs[0]) if len(qs) > 1 else qs[0]
                pairs = [(q, vals[0])]
            for q, v in pairs:
                d = found.setdefault(q, {})
                d.setdefault("nsfr_ratio_pct", v)
                d.setdefault("nsfr_ratio_raw_line", " ".join(line.split())[:300])
    return found


GROUPS = {"row7": [f"row7_{k}" for k in KEYS["perp"]], "retail": [f"retail_{k}" for k in KEYS["perp"]],
          "total_asf": ["total_asf_weighted"], "nsfr": ["nsfr_ratio_pct"]}


def vote(cands_found: list[tuple[str, dict]], q: str) -> dict:
    """Merge the parses of several text variants of one page: majority vote per field group."""
    merged: dict = {}
    for g, fields in GROUPS.items():
        tuples = []
        for method, found in cands_found:
            d = found.get(q, {})
            if fields[-1] in d:
                tuples.append((tuple(d.get(f) for f in fields), method, d))
        if not tuples:
            continue
        counts = Counter(t for t, _, _ in tuples)
        best, n = counts.most_common(1)[0]
        method, d = next((m, d) for t, m, d in tuples if t == best)
        for f, v in zip(fields, best):
            if v is not None:
                merged[f] = v
        raw_key = {"row7": "row7_raw_line", "retail": "retail_raw_line", "total_asf": "total_asf_raw_line", "nsfr": "nsfr_ratio_raw_line"}[g]
        merged[raw_key] = d.get(raw_key, "")
        text_tuples = [t for t, m, _ in tuples if m in ("text", "pdftotext")]
        if method in ("text", "pdftotext"):
            merged[f"{g}_method"] = f"text layer ({n}/{len(text_tuples)} readers agree)"
            if len(set(text_tuples)) > 1:
                merged[f"{g}_method"] += " CHECK"
        else:
            merged[f"{g}_method"] = f"ocr ({n}/{len(tuples)} variants agree)"
            if n < 2:
                merged[f"{g}_method"] += " CHECK"
    return merged


def extract_pdf(src: dict, overrides: dict) -> tuple[list[dict], list[dict]]:
    slug, pdf_file = src["hc_slug"], src["pdf_file"]
    pdf_path = RAW_NSFR / pdf_file
    ov = overrides.get(slug, {})
    results: dict[str, dict] = {Q2: {}, Q1: {}}
    mentions: list[dict] = []
    for page_no, cands in page_candidates(pdf_path):
        text0 = max((t for _, t in cands), key=len)   # richest text variant for mentions / quarter detection
        # --- reciprocal mentions
        joined = " ".join(l.strip() for l in text0.splitlines())
        for sent in re.split(r"(?<=[\.\;])\s+(?=[A-Z(“])", joined):
            if not re.search(r"reciprocal", sent, re.I):
                continue
            s = " ".join(sent.split())
            if ROW7_RE.search(s):
                m = re.search(r"(\(?\d{1,2}\)?\s+)?" + ROW7_RE.pattern, s, re.I)
                s, ctype = s[m.start(): m.end() + 90], "table_row_label"
            else:
                ctype = "narrative"
                if len(s) > 500:
                    m = re.search(r"reciprocal", s, re.I)
                    s = "..." + s[max(0, m.start() - 250): m.end() + 250] + "..."
            mentions.append({"hc_slug": slug, "pdf_file": pdf_file, "page": page_no, "context_type": ctype,
                             "extraction_method": "text layer" if len(cands) <= 2 else "ocr", "quote": s[:600]})
        # --- quarters and layout
        qs = ov.get("page_quarters", {}).get(str(page_no)) or detect_quarters(text0)
        if isinstance(qs, str):
            qs = [qs]
        hint = ov.get("layout") or ("perp" if re.search(r"perpetual|erpetual", text0, re.I) else "std")
        if DEBUG:
            hits = [l for l in text0.splitlines() if ROW7_RE.search(l) or RETAIL_RE.search(l) or TOTAL_ASF_RE.search(l) or NSFR_RE.search(l)]
            log(f"  [{slug} p{page_no} {','.join(c[0] for c in cands)}] quarters={qs} hint={hint} hits={hits[:5]}")
        if not qs:
            continue
        cands_found = [(method, parse_text(text, qs, hint, aligned=(method == "pdftotext"))) for method, text in cands]
        for q in (Q2, Q1):
            merged = vote(cands_found, q)
            for k, v in merged.items():
                if k not in results[q]:
                    results[q][k] = v
                    g = k.split("_")[0] if not k.startswith("total_asf") else "total_asf"
                    g = "nsfr" if k.startswith("nsfr") else g
                    results[q].setdefault(f"{g}_page", page_no)
    # --- manual overrides (values read off the page by a person; page cited)
    for q in (Q2, Q1):
        for k, v in ov.get("manual", {}).get(q, {}).items():
            results[q][k] = v
    rows = []
    for q in (Q2, Q1):
        r = {"hc_slug": slug, "firm": src["firm"], "quarter": q, "pdf_file": pdf_file,
             "units": src.get("units") or "USD millions"}
        r.update(results[q])
        rows.append(r)
    return rows, mentions


COLS = ["hc_slug", "firm", "quarter", "pdf_file", "units",
        "row7_open", "row7_lt6m", "row7_m6_1y", "row7_ge1y", "row7_perpetual", "row7_weighted", "row7_page", "row7_method", "row7_raw_line",
        "retail_open", "retail_lt6m", "retail_m6_1y", "retail_ge1y", "retail_perpetual", "retail_weighted", "retail_page", "retail_method", "retail_raw_line",
        "total_asf_weighted", "total_asf_page", "total_asf_method", "total_asf_raw_line",
        "nsfr_ratio_pct", "nsfr_page", "nsfr_method", "nsfr_ratio_raw_line"]


def main() -> None:
    global DEBUG
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated slugs")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    DEBUG = args.debug
    sources = [s for s in read_csv(PROCESSED / "sources.csv") if s.get("pdf_file")]
    if args.only:
        sources = [s for s in sources if s["hc_slug"] in args.only.split(",")]
    ov_path = REFERENCE / "nsfr_parse_overrides.json"
    overrides = json.loads(ov_path.read_text()) if ov_path.exists() else {}
    all_rows, all_mentions = [], []
    for s in sources:
        if not (RAW_NSFR / s["pdf_file"]).exists():
            log(f"missing PDF for {s['hc_slug']}: {s['pdf_file']}")
            continue
        rows, mentions = extract_pdf(s, overrides)
        all_rows += rows
        all_mentions += mentions
        for r in rows:
            log(f"{s['hc_slug']:20s} {r['quarter']} row7={[r.get(f'row7_{k}') for k in KEYS['perp']]} p{r.get('row7_page')} {r.get('row7_method','')} "
                f"| retail={[r.get(f'retail_{k}') for k in KEYS['perp']]} | ASF={r.get('total_asf_weighted')} | NSFR={r.get('nsfr_ratio_pct')} ({r.get('nsfr_method','')})")
    for r in all_rows:
        for c in COLS:
            r.setdefault(c, "")
    write_csv(PROCESSED / "nsfr_detail_extracted.csv", all_rows, COLS)
    write_csv(PROCESSED / "nsfr_text_mentions.csv", all_mentions,
              ["hc_slug", "pdf_file", "page", "context_type", "extraction_method", "quote"])
    log(f"wrote nsfr_detail_extracted.csv ({len(all_rows)} rows) and nsfr_text_mentions.csv ({len(all_mentions)} mentions)")


if __name__ == "__main__":
    main()
