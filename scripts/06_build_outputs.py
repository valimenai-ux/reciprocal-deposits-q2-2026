#!/usr/bin/env python3
"""Step 6 - build the two deliverables from the processed CSVs.

  output/reciprocal_deposits_q2_2026.html  one self-contained page: inline CSS/JS, SVG
                                           charts drawn here in Python, no external
                                           resources of any kind (opens from file://)
  output/reciprocal_deposits_q2_2026.xlsx  sheets Summary, Bank detail, NSFR detail,
                                           Sources, Notes; plain values, no formulas
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUTPUT, PROCESSED, RAW, REPORT_DATE, read_csv  # noqa: E402

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

STATUS_TEXT = {"found": "found", "found_not_retrievable": "published; not retrievable by automated client (see notes)",
               "not_found": "not yet filed / not found", "not_required": "not required (no NSFR requirement in Q2 2026)"}
STATUS_SHORT = {"found": "found", "found_not_retrievable": "published, not retrievable", "not_found": "not filed / not found", "not_required": "not required"}

HTML_OUT = OUTPUT / "reciprocal_deposits_q2_2026.html"
XLSX_OUT = OUTPUT / "reciprocal_deposits_q2_2026.xlsx"

# ---- palette (validated with the dataviz validator, light surface #fcfcfb)
C = {"surface": "#fcfcfb", "page": "#f9f9f7", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
     "grid": "#e1e0d9", "axis": "#c3c2b7", "series": "#2a78d6", "accent": "#eb6834", "hl_bg": "#fff3ec",
     "border": "rgba(11,11,11,0.10)"}


def f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def bn(v, d=2):
    """USD millions -> '$x.xxbn' text."""
    x = f(v)
    return "–" if x is None else f"{x / 1000:,.{d}f}"


def pc(v, d=2):
    x = f(v)
    return "–" if x is None else f"{x:,.{d}f}%"


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def nice_ticks(vmax: float, n: int = 5) -> list[float]:
    if vmax <= 0:
        return [0, 1]
    import math
    raw = vmax / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    ticks, t = [], 0.0
    while t <= vmax + 1e-9:
        ticks.append(round(t, 6))
        t += step
    if ticks[-1] < vmax:
        ticks.append(round(ticks[-1] + step, 6))
    return ticks


def hbar_chart(rows: list[dict], value_key: str, label_fmt, title: str, subtitle: str, unit_suffix: str, chart_id: str) -> str:
    """Horizontal bar chart as inline SVG (single series; RBC US emphasised)."""
    data = [r for r in rows if f(r.get(value_key)) is not None]
    data.sort(key=lambda r: -f(r[value_key]))
    W, LABEL_W, RIGHT_PAD, TOP, ROW_H, BAR_H = 960, 250, 90, 34, 22, 14
    H = TOP + ROW_H * len(data) + 28
    plot_w = W - LABEL_W - RIGHT_PAD
    vmax = max(f(r[value_key]) for r in data) or 1.0
    ticks = nice_ticks(vmax)
    scale = plot_w / ticks[-1]
    parts = [f'<svg class="chart" id="{chart_id}" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="{chart_id}-t">',
             f'<title id="{chart_id}-t">{esc(title)}</title>']
    # gridlines + axis ticks
    for t in ticks:
        x = LABEL_W + t * scale
        parts.append(f'<line x1="{x:.1f}" y1="{TOP - 6}" x2="{x:.1f}" y2="{H - 24}" stroke="{C["grid"]}" stroke-width="1"/>')
        lbl = f"{t:g}{unit_suffix}"
        parts.append(f'<text x="{x:.1f}" y="{H - 8}" text-anchor="middle" class="tick">{esc(lbl)}</text>')
    parts.append(f'<line x1="{LABEL_W}" y1="{TOP - 6}" x2="{LABEL_W}" y2="{H - 24}" stroke="{C["axis"]}" stroke-width="1"/>')
    for i, r in enumerate(data):
        v = f(r[value_key])
        y = TOP + i * ROW_H
        hl = r.get("highlight") == "yes"
        color = C["accent"] if hl else C["series"]
        name = r["hc_name"] + (" (City National)" if hl else "")
        w = max(0.0, v * scale)
        rr = min(4, w / 2)
        tip = f"{name}: {label_fmt(v)}"
        parts.append(f'<g class="bar{" hl" if hl else ""}"><title>{esc(tip)}</title>')
        parts.append(f'<rect x="0" y="{y}" width="{W}" height="{ROW_H}" fill="transparent"/>')
        parts.append(f'<text x="{LABEL_W - 10}" y="{y + ROW_H / 2 + 4:.1f}" text-anchor="end" class="cat{" hlcat" if hl else ""}">{esc(name)}</text>')
        if w > 0.5:
            # 4px rounded data-end, square at the baseline, 2px surface gap between neighbours via BAR_H < ROW_H
            x0, y0 = LABEL_W + 1, y + (ROW_H - BAR_H) / 2
            d = (f"M{x0:.1f},{y0:.1f} h{w - rr:.1f} a{rr:.1f},{rr:.1f} 0 0 1 {rr:.1f},{rr:.1f} v{BAR_H - 2 * rr:.1f} "
                 f"a{rr:.1f},{rr:.1f} 0 0 1 -{rr:.1f},{rr:.1f} h-{w - rr:.1f} z")
            parts.append(f'<path d="{d}" fill="{color}"/>')
            parts.append(f'<text x="{x0 + w + 6:.1f}" y="{y + ROW_H / 2 + 4:.1f}" class="val">{esc(label_fmt(v))}</text>')
        else:
            parts.append(f'<text x="{LABEL_W + 6}" y="{y + ROW_H / 2 + 4:.1f}" class="val zero">0</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def build_html(summary, banks, nsfr, sources, notes, mentions, field_map, entities) -> str:
    with_cr = [r for r in summary if f(r.get("reciprocal_deposits_musd")) is not None]
    total = sum(f(r["reciprocal_deposits_musd"]) for r in with_cr)
    dep_total = sum(f(r["total_deposits_musd"]) for r in with_cr)
    top_usd = sorted(with_cr, key=lambda r: -f(r["reciprocal_deposits_musd"]))[:3]
    top_pct = sorted(with_cr, key=lambda r: -(f(r["reciprocal_pct_of_deposits"]) or 0))[:3]
    n_pos = sum(1 for r in with_cr if f(r["reciprocal_deposits_musd"]) > 0)
    nsfr_found = [s for s in sources if s["status"] == "found"]
    nsfr_other = [s for s in sources if s["status"] != "found"]
    build_date = dt.date.today().isoformat()

    def name_of(r):
        return r["hc_name"] + (" (City National)" if r.get("highlight") == "yes" else "")

    headline = (f"Across the {len(with_cr)} holding companies with insured bank subsidiaries, reciprocal deposits totalled "
                f"<strong>${total / 1000:,.1f}bn</strong> at 6/30/2026 ({total / dep_total * 100:.2f}% of their ${dep_total / 1e6:,.1f}tn of deposits; "
                f"{n_pos} of {len(with_cr)} report any). Top 3 by $: " +
                ", ".join(f"{esc(name_of(r))} ${f(r['reciprocal_deposits_musd']) / 1000:,.1f}bn" for r in top_usd) +
                ". Top 3 by % of deposits: " +
                ", ".join(f"{esc(name_of(r))} {f(r['reciprocal_pct_of_deposits']):.2f}%" for r in top_pct) + ".")

    # ---- table
    cols = [  # (key, header, title, kind)
        ("hc_name", "Holding company", "Holding company (category in grey)", "text"),
        ("n_insured_subs", "Banks", "Number of active FDIC-insured depository subsidiaries (FDIC BankFind)", "num"),
        ("reciprocal_deposits_musd", "Reciprocal $bn", "Total reciprocal deposits, RC-E M.1.g (RCONJH83), sum of insured subs, 6/30/2026", "bn"),
        ("reciprocal_pct_of_deposits", "% of deposits", "Reciprocal deposits / total deposits incl. foreign offices", "pct"),
        ("rank_reciprocal_usd", "Rank $", "Rank on reciprocal $", "num"),
        ("rank_reciprocal_pct", "Rank %", "Rank on reciprocal % of deposits", "num"),
        ("brokered_reciprocal_rco9_musd", "Brokered recip. $bn", "Reciprocal brokered deposits, RC-O item 9 (RCONG803)", "bn"),
        ("brokered_reciprocal_pct_of_reciprocal", "% of recip.", "RC-O item 9 as % of total reciprocal deposits", "pct"),
        ("total_brokered_musd", "Total brokered $bn", "Total brokered deposits, RC-E M.1.b (RCON2365)", "bn"),
        ("brokered_pct_of_deposits", "Brokered % dep.", "Total brokered deposits / total deposits", "pct"),
        ("total_deposits_musd", "Deposits $bn", "Total deposits incl. foreign offices (RCON2200 + RCFN2200)", "bn"),
        ("nsfr_row7_unweighted_total_q2_musd", "NSFR row 7 unw. $bn", "NSFR sweep/reciprocal/brokered (row 7): unweighted total, Q2 2026 average (holding company, consolidated)", "bn"),
        ("nsfr_row7_pct_of_retail_funding_q2", "Row 7 % retail", "NSFR row 7 unweighted total as % of total retail funding (unweighted), Q2 2026 average", "pct"),
        ("nsfr_ratio_q2_pct", "NSFR Q2", "Reported NSFR, Q2 2026 quarterly average", "ratio"),
        ("nsfr_status", "NSFR disclosure", "Q1-Q2 2026 NSFR public disclosure status", "text"),
    ]
    th = "".join(f'<th data-kind="{k}" title="{esc(t)}"><button type="button">{esc(h)}</button></th>' for _, h, t, k in cols)
    trs = []
    for r in summary:
        hl = r.get("highlight") == "yes"
        tds = []
        for key, _, _, kind in cols:
            v = r.get(key, "")
            if key == "hc_name":
                cat = r.get("category_verified") or r["category"]
                cell = f'<div class="hc">{esc(name_of(r))}</div><div class="cat" title="Verified tailoring category (brief: {esc(r["category"])})">Cat. {esc(cat)}</div>'
                tds.append(f'<td data-v="{esc(r["hc_name"])}">{cell}</td>')
            elif key == "nsfr_status":
                txt = STATUS_SHORT.get(v, v or "–")
                tds.append(f'<td data-v="{esc(txt)}" class="txt" title="{esc(STATUS_TEXT.get(v, v))}">{esc(txt)}</td>')
            elif kind == "bn":
                x = f(v)
                tds.append(f'<td data-v="{x if x is not None else -1}" class="num">{bn(v)}</td>')
            elif kind == "pct":
                x = f(v)
                tds.append(f'<td data-v="{x if x is not None else -1}" class="num">{pc(v)}</td>')
            elif kind == "ratio":
                x = f(v)
                tds.append(f'<td data-v="{x if x is not None else -1}" class="num">{"–" if x is None else f"{x:g}%"}</td>')
            else:
                x = f(v)
                tds.append(f'<td data-v="{x if x is not None else -1}" class="num">{"–" if x is None else f"{x:g}"}</td>')
        trs.append(f'<tr{" class=\"hl\"" if hl else ""}>{"".join(tds)}</tr>')
    table = f'<table id="summary"><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'

    chart1 = hbar_chart(summary, "reciprocal_deposits_musd", lambda v: f"${v / 1000:,.2f}bn",
                        "Reciprocal deposits by holding company, $bn, 6/30/2026", "", "", "c1")
    chart2 = hbar_chart(summary, "reciprocal_pct_of_deposits", lambda v: f"{v:.2f}%",
                        "Reciprocal deposits as % of total deposits, 6/30/2026", "", "%", "c2")

    # ---- notes
    def note_items(section):
        return [n for n in notes if n["section"] == section]
    sections = []
    for sec in dict.fromkeys(n["section"] for n in notes):
        items = "".join(f"<li><strong>{esc(n['title'])}.</strong> {esc(n['text'])}</li>" for n in sorted(note_items(sec), key=lambda n: int(n["order"])))
        sections.append(f"<h3>{esc(sec)}</h3><ul>{items}</ul>")
    # firms excluded / not filed
    exc = "".join(f"<li><strong>{esc(s['firm'])}</strong>: {esc(STATUS_TEXT.get(s['status'], s['status']))}. {esc(s.get('notes', ''))}</li>" for s in nsfr_other)
    no_bank = [r for r in summary if f(r.get("reciprocal_deposits_musd")) is None]
    exc += "".join(f"<li><strong>{esc(r['hc_name'])}</strong>: no FDIC-insured depository subsidiary in FDIC BankFind, so no call report figures; shown in the table for completeness.</li>" for r in no_bank)
    sections.append(f"<h3>Firms excluded, not required, or not yet filed</h3><ul>{exc or '<li>none</li>'}</ul>")
    # reciprocal mentions
    narr = [m for m in mentions if m["context_type"] == "narrative"]
    if narr:
        li = "".join(f"<li><strong>{esc(next((s['firm'] for s in sources if s['hc_slug'] == m['hc_slug']), m['hc_slug']))}</strong> ({esc(m['pdf_file'])}, p. {esc(m['page'])}): “{esc(m['quote'])}”</li>" for m in narr)
    else:
        li = "<li>No disclosure in the set contains narrative text about reciprocal deposits beyond the row-7 label itself.</li>"
    sections.append(f"<h3>Qualitative NSFR text mentioning reciprocal deposits</h3><ul>{li}</ul>")
    # open items
    open_items = read_csv(PROCESSED / "open_items.csv") if (PROCESSED / "open_items.csv").exists() else []
    if open_items:
        sections.append("<h3>Open items and judgment calls</h3><ol>" + "".join(f"<li><strong>{esc(o['item'])}.</strong> {esc(o['detail'])}</li>" for o in open_items) + "</ol>")
    # sources
    src_li = "".join(f"<li><strong>{esc(s['firm'])}</strong>: {esc(s.get('document_type', ''))}{' — ' if s.get('disclosure_url') else ''}"
                     f"{('<a href=\"' + esc(s['disclosure_url']) + '\">' + esc(s['disclosure_url']) + '</a>') if s.get('disclosure_url') else ''}"
                     f"{(' (saved as ' + esc(s['pdf_file']) + ')') if s.get('pdf_file') else ''}</li>" for s in sources)
    sections.append("<h3>Sources</h3><ul>"
                    "<li><strong>Call reports</strong>: FFIEC CDR Public Data Distribution, bulk download “Call Reports -- Single Period”, 06/30/2026, TSV "
                    "(<a href=\"https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx\">cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx</a>); MDRM codes from the bulk file’s dictionary rows and the Federal Reserve MDRM data dictionary.</li>"
                    "<li><strong>Entity structure</strong>: FDIC BankFind Suite institutions API (<a href=\"https://api.fdic.gov/banks/institutions\">api.fdic.gov/banks/institutions</a>), active institutions, fields FED_RSSD / RSSDHCR / NAMEHCR.</li>"
                    f"{src_li}</ul>")
    notes_html = "".join(sections)

    css = f"""
:root {{ color-scheme: light; --surface:{C['surface']}; --page:{C['page']}; --ink:{C['ink']}; --ink2:{C['ink2']}; --muted:{C['muted']};
  --grid:{C['grid']}; --axis:{C['axis']}; --series:{C['series']}; --accent:{C['accent']}; --hl:{C['hl_bg']}; --border:{C['border']}; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: var(--page); color: var(--ink); font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; font-size: 14px; line-height: 1.45; }}
main {{ max-width: 1240px; margin: 0 auto; padding: 24px 16px 48px; }}
header h1 {{ font-size: 24px; margin: 0 0 4px; font-weight: 650; letter-spacing: -0.01em; }}
header .sub {{ color: var(--ink2); margin: 0 0 18px; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px 18px; margin: 0 0 18px; }}
.headline {{ font-size: 16px; }}
.headline strong {{ font-size: 28px; font-weight: 700; }}
.kpis {{ display: flex; flex-wrap: wrap; gap: 24px; margin-top: 10px; }}
.kpi .label {{ color: var(--ink2); font-size: 12px; }}
.kpi .value {{ font-size: 22px; font-weight: 650; }}
h2 {{ font-size: 17px; margin: 0 0 10px; font-weight: 650; }}
h3 {{ font-size: 14px; margin: 14px 0 4px; }}
.hint {{ color: var(--muted); font-size: 12px; margin: 0 0 8px; }}
.tablewrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; white-space: nowrap; }}
th {{ text-align: right; font-weight: 600; color: var(--ink2); font-size: 12px; position: sticky; top: 0; background: var(--surface); }}
th:first-child {{ text-align: left; }}
th button {{ all: unset; cursor: pointer; }}
th button:hover {{ color: var(--ink); text-decoration: underline; }}
th[aria-sort="ascending"] button::after {{ content: " \\25B2"; font-size: 9px; }}
th[aria-sort="descending"] button::after {{ content: " \\25BC"; font-size: 9px; }}
td.num {{ text-align: right; }}
td.txt {{ white-space: normal; max-width: 160px; color: var(--ink2); }}
td .hc {{ font-weight: 600; }}
td .cat {{ color: var(--muted); font-size: 11px; }}
tr.hl td {{ background: var(--hl); }}
tr.hl td .hc::after {{ content: " \\25C6"; color: var(--accent); font-size: 10px; }}
tbody tr:hover td {{ background: #f3f3ef; }}
tbody tr.hl:hover td {{ background: #ffe9db; }}
.legend {{ color: var(--ink2); font-size: 12px; margin: 4px 0 0; }}
.legend .sw {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px; vertical-align: -1px; margin-right: 4px; }}
svg.chart {{ display: block; height: auto; font-family: inherit; }}
svg.chart text {{ fill: var(--ink2); font-size: 12px; }}
svg.chart text.tick {{ fill: var(--muted); font-size: 11px; }}
svg.chart text.cat {{ fill: var(--ink); }}
svg.chart text.hlcat {{ font-weight: 650; }}
svg.chart text.val {{ fill: var(--ink2); font-size: 11.5px; }}
svg.chart text.zero {{ fill: var(--muted); }}
svg.chart g.bar:hover path {{ filter: brightness(1.12); }}
.notes ul {{ margin: 0 0 6px 18px; padding: 0; }}
.notes li {{ margin: 0 0 6px; }}
.notes a {{ color: #1c5cab; word-break: break-all; }}
footer {{ color: var(--muted); font-size: 12px; margin-top: 12px; }}
@media print {{
  @page {{ size: A4 landscape; margin: 10mm; }}
  html, body {{ background: #fff; font-size: 10.5px; }}
  main {{ max-width: none; padding: 0; }}
  .card {{ border: none; padding: 0; margin: 0 0 10px; break-inside: avoid; }}
  .tablewrap {{ overflow: visible; }}
  th {{ position: static; }}
  th button::after {{ content: "" !important; }}
  .hint, .noprint {{ display: none; }}
  tr {{ break-inside: avoid; }}
  svg.chart {{ max-height: 95vh; }}
  .notes {{ break-before: page; }}
}}
"""
    js = """
(function(){
  var table = document.getElementById('summary');
  if (!table) return;
  var ths = table.querySelectorAll('thead th');
  ths.forEach(function(th, idx){
    th.querySelector('button').addEventListener('click', function(){
      var kind = th.getAttribute('data-kind');
      var current = th.getAttribute('aria-sort');
      var dir = current === 'descending' ? 'ascending' : 'descending';
      if (kind === 'text' && current !== 'ascending' && current !== 'descending') dir = 'ascending';
      ths.forEach(function(t){ t.removeAttribute('aria-sort'); });
      th.setAttribute('aria-sort', dir);
      var rows = Array.prototype.slice.call(table.tBodies[0].rows);
      rows.sort(function(a, b){
        var va = a.cells[idx].getAttribute('data-v'), vb = b.cells[idx].getAttribute('data-v');
        var r;
        if (kind === 'text') { r = va.localeCompare(vb); }
        else { r = parseFloat(va) - parseFloat(vb); }
        return dir === 'ascending' ? r : -r;
      });
      rows.forEach(function(r){ table.tBodies[0].appendChild(r); });
    });
  });
})();
"""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reciprocal deposits, large US banks, Q2 2026</title>
<style>{css}</style>
</head>
<body>
<main>
<header>
<h1>Reciprocal deposits at large US banks — 6/30/2026</h1>
<p class="sub">Call Report sizing for the NSFR-disclosing holding companies (Category I–III and Category IV with ≥ $50bn weighted short-term wholesale funding), with the NSFR sweep/reciprocal/brokered line (row 7) as context. Built {esc(build_date)}; self-contained, works offline.</p>
</header>

<section class="card headline">
<p style="margin:0">{headline}</p>
<div class="kpis">
  <div class="kpi"><div class="label">Total reciprocal deposits (call report, sum of insured subs)</div><div class="value">${total / 1000:,.1f}bn</div></div>
  <div class="kpi"><div class="label">Share of the set’s total deposits</div><div class="value">{total / dep_total * 100:.2f}%</div></div>
  <div class="kpi"><div class="label">Holding companies reporting any reciprocal deposits</div><div class="value">{n_pos} of {len(with_cr)}</div></div>
  <div class="kpi"><div class="label">Q1–Q2 2026 NSFR disclosures parsed</div><div class="value">{len(nsfr_found)} of {len(sources)}</div><div class="label">{sum(1 for s in sources if s['status'] == 'found_not_retrievable')} more published but not retrievable; {sum(1 for s in sources if s['status'] in ('not_required', 'not_found'))} not required / not filed</div></div>
</div>
</section>

<section class="card">
<h2>Holding-company summary</h2>
<p class="hint">Click a column header to sort. Hover a header for the item definition. Dollar columns in $bn; call report items are point-in-time at 6/30/2026 and summed over each firm’s FDIC-insured bank subsidiaries; the NSFR columns are consolidated holding-company quarterly averages and the row-7 line is a bundle (sweep + brokered reciprocal + retail brokered), not reciprocal deposits. Highlighted row: RBC US Group Holdings / City National Bank.</p>
<div class="tablewrap">{table}</div>
</section>

<section class="card">
<h2>Reciprocal deposits, $bn (RC-E M.1.g, sum of insured subs, 6/30/2026)</h2>
{chart1}
<p class="legend"><span class="sw" style="background:{C['series']}"></span>holding company &nbsp; <span class="sw" style="background:{C['accent']}"></span>RBC US Group Holdings (City National Bank), highlighted</p>
</section>

<section class="card">
<h2>Reciprocal deposits as % of total deposits (6/30/2026)</h2>
{chart2}
<p class="legend"><span class="sw" style="background:{C['series']}"></span>holding company &nbsp; <span class="sw" style="background:{C['accent']}"></span>RBC US Group Holdings (City National Bank), highlighted</p>
</section>

<section class="card notes">
<h2>Notes</h2>
{notes_html}
</section>
<footer>Data: FFIEC CDR Call Reports (6/30/2026), FDIC BankFind institutions, firms’ NSFR public disclosures (Q1–Q2 2026). Spreadsheet twin: reciprocal_deposits_q2_2026.xlsx. Pipeline and raw files: see README.md in the repository.</footer>
</main>
<script>{js}</script>
</body>
</html>
"""
    return page


def build_xlsx(summary, banks, nsfr, sources, notes, mentions, field_map, entities) -> None:
    wb = Workbook()
    bold = Font(bold=True)
    hdr_fill = PatternFill("solid", fgColor="EDEDE8")
    hl_fill = PatternFill("solid", fgColor="FFF3EC")
    thin = Side(style="thin", color="DDDDDD")

    def sheet(ws, headers, rows, formats=None, widths=None, highlight_col=None):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill, c.alignment = bold, hdr_fill, Alignment(wrap_text=True, vertical="top")
        for r in rows:
            ws.append(r)
        ws.freeze_panes = "B2"
        for j, h in enumerate(headers, start=1):
            col = get_column_letter(j)
            ws.column_dimensions[col].width = (widths or {}).get(h, max(10, min(60, len(h) + 2)))
            fmt = (formats or {}).get(h)
            if fmt:
                for i in range(2, ws.max_row + 1):
                    ws[f"{col}{i}"].number_format = fmt
        if highlight_col is not None:
            for i in range(2, ws.max_row + 1):
                if ws.cell(row=i, column=highlight_col).value == "yes":
                    for c in ws[i]:
                        c.fill = hl_fill
        ws.row_dimensions[1].height = 42

    # ---- Summary
    ws = wb.active
    ws.title = "Summary"
    cols = [("hc_name", "Holding company"), ("hc_legal_name", "Legal name"), ("category", "Category (brief)"), ("category_verified", "Category (verified, Q2 2026)"),
            ("n_insured_subs", "Insured bank subs (#)"), ("highlight", "Highlight"),
            ("reciprocal_deposits_musd", "Reciprocal deposits ($m)"), ("reciprocal_pct_of_deposits", "Reciprocal % of deposits"),
            ("rank_reciprocal_usd", "Rank ($)"), ("rank_reciprocal_pct", "Rank (%)"),
            ("brokered_reciprocal_rco9_musd", "Brokered reciprocal RC-O 9 ($m)"), ("brokered_reciprocal_pct_of_reciprocal", "Brokered reciprocal % of reciprocal"),
            ("total_brokered_musd", "Total brokered deposits ($m)"), ("brokered_pct_of_deposits", "Brokered % of deposits"),
            ("total_deposits_musd", "Total deposits incl. foreign ($m)"), ("deposits_domestic_musd", "Domestic-office deposits ($m)"),
            ("deposits_foreign_musd", "Foreign-office deposits ($m)"), ("total_assets_musd", "Total assets ($m)"),
            ("nsfr_status", "NSFR disclosure status"), ("nsfr_row7_unweighted_total_q2_musd", "NSFR sweep/reciprocal/brokered (row 7) unweighted total, Q2 2026 avg ($m)"),
            ("nsfr_row7_weighted_q2_musd", "NSFR row 7 weighted, Q2 2026 avg ($m)"), ("nsfr_row7_pct_of_retail_funding_q2", "NSFR row 7 % of total retail funding (unweighted), Q2 2026"),
            ("nsfr_retail_funding_unweighted_q2_musd", "NSFR total retail funding unweighted, Q2 2026 avg ($m)"), ("nsfr_total_asf_q2_musd", "NSFR total ASF, Q2 2026 avg ($m)"),
            ("nsfr_ratio_q2_pct", "NSFR ratio Q2 2026 (%)"), ("nsfr_row7_unweighted_total_q1_musd", "NSFR row 7 unweighted total, Q1 2026 avg ($m)"),
            ("nsfr_ratio_q1_pct", "NSFR ratio Q1 2026 (%)"), ("nsfr_pdf_file", "NSFR source PDF"), ("nsfr_row7_page_q2", "NSFR row 7 page (Q2)"),
            ("call_report_source", "Call report source")]
    pct_keys = {"reciprocal_pct_of_deposits", "brokered_reciprocal_pct_of_reciprocal", "brokered_pct_of_deposits", "nsfr_row7_pct_of_retail_funding_q2"}
    rows = []
    for r in summary:
        row = []
        for k, _ in cols:
            v = r.get(k, "")
            x = f(v)
            if k in pct_keys:
                row.append(None if x is None else x / 100.0)
            elif k in ("n_insured_subs", "rank_reciprocal_usd", "rank_reciprocal_pct"):
                row.append(None if x is None else int(x))
            elif k.endswith("_musd") or k.endswith("_pct"):
                row.append(x)
            else:
                row.append(v)
        rows.append(row)
    fmts = {h: "#,##0.0" for k, h in cols if k.endswith("_musd")}
    fmts.update({h: "0.00%" for k, h in cols if k in pct_keys})
    fmts.update({h: "0.0" for k, h in cols if k in ("nsfr_ratio_q2_pct", "nsfr_ratio_q1_pct")})
    sheet(ws, [h for _, h in cols], rows, fmts, {"Holding company": 26, "Legal name": 36, "Category": 22, "Call report source": 60}, highlight_col=5)

    # ---- Bank detail
    ws = wb.create_sheet("Bank detail")
    bcols = [("hc_name", "Holding company"), ("bank_name", "Bank"), ("rssd_id", "RSSD ID"), ("fdic_cert", "FDIC cert"), ("filing_form", "Call report form"),
             ("report_date", "Report date"), ("reciprocal_deposits_k", "Reciprocal deposits RC-E M.1.g ($000)"), ("brokered_deposits_k", "Total brokered deposits RC-E M.1.b ($000)"),
             ("rco9_reciprocal_brokered_k", "Reciprocal brokered deposits RC-O 9 ($000)"), ("rco9a_fully_insured_reciprocal_brokered_k", "Fully consolidated reciprocal brokered RC-O 9.a ($000) [n/a for these banks]"),
             ("deposits_domestic_k", "Deposits in domestic offices RC 13.a ($000)"), ("deposits_foreign_k", "Deposits in foreign offices RC 13.b ($000)"),
             ("total_deposits_k", "Total deposits ($000)"), ("total_assets_k", "Total assets ($000)"), ("cdr_submission_updated", "CDR submission updated"), ("source", "Source")]
    ent = {e["rssd_id"]: e for e in entities}
    rows = []
    for b in banks:
        row = []
        for k, _ in bcols:
            v = b.get(k, "")
            row.append(f(v) if k.endswith("_k") else v)
        e = ent.get(b["rssd_id"], {})
        row += [e.get("bank_class_desc", ""), e.get("primary_regulator", ""), e.get("city", ""), e.get("state", ""), e.get("fdic_top_holder_name", ""), e.get("fdic_top_holder_rssd", "")]
        rows.append(row)
    headers = [h for _, h in bcols] + ["Charter class (FDIC)", "Primary federal regulator", "City", "State", "FDIC top holder (NAMEHCR)", "FDIC top holder RSSD (RSSDHCR)"]
    sheet(ws, headers, rows, {h: "#,##0" for k, h in bcols if k.endswith("_k")}, {"Holding company": 24, "Bank": 48, "Source": 34})

    # ---- NSFR detail
    ws = wb.create_sheet("NSFR detail")
    if nsfr:
        ncols = [("firm", "Firm"), ("quarter", "Quarter"), ("pdf_file", "PDF file"), ("units", "Units"),
                 ("row7_open", "Row 7 unweighted: open maturity"), ("row7_lt6m", "Row 7 unweighted: < 6 months"), ("row7_m6_1y", "Row 7 unweighted: 6 months to < 1 year"),
                 ("row7_ge1y", "Row 7 unweighted: >= 1 year"), ("row7_perpetual", "Row 7 unweighted: perpetual (if printed)"), ("row7_unweighted_total", "Row 7 unweighted total"),
                 ("row7_weighted", "Row 7 weighted amount"), ("row7_page", "Row 7 page"), ("row7_method", "Row 7 extraction method"),
                 ("retail_open", "Total retail funding unweighted: open"), ("retail_lt6m", "Total retail funding unweighted: < 6 months"), ("retail_m6_1y", "Total retail funding unweighted: 6m to < 1y"),
                 ("retail_ge1y", "Total retail funding unweighted: >= 1 year"), ("retail_perpetual", "Total retail funding unweighted: perpetual"), ("retail_unweighted_total", "Total retail funding unweighted total"),
                 ("retail_weighted", "Total retail funding weighted"), ("retail_page", "Retail funding page"),
                 ("row7_pct_of_retail_unweighted", "Row 7 % of total retail funding (unweighted)"), ("row7_weighted_pct_of_retail_weighted", "Row 7 weighted % of retail funding weighted"),
                 ("total_asf_weighted", "Total ASF (weighted)"), ("total_asf_page", "Total ASF page"), ("row7_weighted_pct_of_total_asf", "Row 7 weighted % of total ASF"),
                 ("nsfr_ratio_pct", "NSFR ratio (%)"), ("nsfr_page", "NSFR ratio page"), ("nsfr_method", "NSFR extraction method"),
                 ("row7_raw_line", "Row 7 raw line (as parsed)"), ("retail_raw_line", "Retail funding raw line"), ("total_asf_raw_line", "Total ASF raw line"), ("nsfr_ratio_raw_line", "NSFR raw line")]
        pk = {"row7_pct_of_retail_unweighted", "row7_weighted_pct_of_retail_weighted", "row7_weighted_pct_of_total_asf"}
        rows = []
        for r in nsfr:
            row = []
            for k, _ in ncols:
                v = r.get(k, "")
                x = f(v)
                if k in pk:
                    row.append(None if x is None else x / 100.0)
                elif k.startswith(("row7_", "retail_", "total_asf_", "nsfr_ratio")) and not k.endswith(("_line", "_method", "_page")):
                    row.append(x)
                elif k.endswith("_page"):
                    row.append(None if x is None else int(x))
                else:
                    row.append(v)
            rows.append(row)
        fm = {h: "#,##0" for k, h in ncols if k.startswith(("row7_", "retail_", "total_asf_")) and not k.endswith(("_line", "_method", "_page")) and k not in pk}
        fm.update({h: "0.00%" for k, h in ncols if k in pk})
        sheet(ws, [h for _, h in ncols], rows, fm, {"Firm": 30, "PDF file": 34, "Row 7 raw line (as parsed)": 60, "Retail funding raw line": 50, "Total ASF raw line": 40, "NSFR raw line": 40})
        ws.append([])
        ws.append(["Reciprocal mentions (every sentence containing 'reciprocal'; table_row_label = the row-7 label itself)"])
        ws.append(["Firm", "PDF file", "Page", "Context", "Method", "Quote"])
        firm_of = {s["hc_slug"]: s["firm"] for s in sources}
        for m in mentions:
            ws.append([firm_of.get(m["hc_slug"], m["hc_slug"]), m["pdf_file"], int(m["page"]), m["context_type"], m["extraction_method"], m["quote"]])
    else:
        ws.append(["No NSFR figures extracted yet"])

    # ---- Sources
    ws = wb.create_sheet("Sources")
    scols = [("firm", "Firm"), ("status", "Status"), ("document_type", "Document type"), ("disclosure_url", "Disclosure URL"), ("landing_page_url", "Landing page"),
             ("pdf_file", "Saved as (data/raw/nsfr/)"), ("pages", "Pages"), ("sha256", "SHA-256"), ("download_status", "Download status"), ("units", "Units"), ("notes", "Notes"), ("urls_checked", "URLs checked")]
    rows = [[s.get(k, "") for k, _ in scols] for s in sources]
    rows += [[], ["Call reports", "used", "FFIEC CDR bulk download, Call Reports -- Single Period, 06/30/2026, TSV", "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx", "", "data/raw/call_reports/FFIEC_CDR_Call_Bulk_All_Schedules_06302026.zip", "", "", "USD thousands", "MDRM codes in data/processed/field_map.csv"],
             ["Entity structure", "used", "FDIC BankFind Suite institutions API (active institutions; FED_RSSD, RSSDHCR, NAMEHCR)", "https://api.fdic.gov/banks/institutions", "https://api.fdic.gov/banks/docs/", "data/raw/fdic/", "", "", "", "NIC not used (CAPTCHA to automated clients)"],
             ["MDRM dictionary", "used", "Federal Reserve Micro Data Reference Manual, CSV download", "https://www.federalreserve.gov/apps/mdrm/pdf/MDRM.zip", "https://www.federalreserve.gov/apps/mdrm/", "data/raw/mdrm/mdrm_items_extract.csv", "", "", "", "item names and confidentiality windows"]]
    sheet(ws, [h for _, h in scols], rows, None, {"Firm": 30, "Document type": 22, "Disclosure URL": 80, "Landing page": 50, "Saved as (data/raw/nsfr/)": 34, "SHA-256": 20, "Notes": 60, "URLs checked": 60})
    ws.append([]); ws.append(["Field map (call report items)"])
    ws.append(list(field_map[0].keys()))
    for r in field_map:
        ws.append(list(r.values()))

    # ---- Notes
    ws = wb.create_sheet("Notes")
    open_items = read_csv(PROCESSED / "open_items.csv") if (PROCESSED / "open_items.csv").exists() else []
    sheet(ws, ["Section", "Title", "Text"], [[n["section"], n["title"], n["text"]] for n in notes] + [["Open items", o["item"], o["detail"]] for o in open_items],
          None, {"Section": 28, "Title": 44, "Text": 120})
    for i in range(2, ws.max_row + 1):
        ws[f"C{i}"].alignment = Alignment(wrap_text=True, vertical="top")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    wb.save(XLSX_OUT)


def main() -> None:
    summary = read_csv(PROCESSED / "summary.csv")
    from common import holding_companies
    hc = {h["hc_slug"]: h for h in holding_companies()}
    for r in summary:
        r["category_verified"] = hc.get(r["hc_slug"], {}).get("category_verified", "")
    banks = read_csv(PROCESSED / "bank_detail.csv")
    nsfr = read_csv(PROCESSED / "nsfr_detail.csv") if (PROCESSED / "nsfr_detail.csv").exists() else []
    sources = read_csv(PROCESSED / "sources.csv")
    notes = read_csv(PROCESSED / "notes.csv")
    mentions = read_csv(PROCESSED / "nsfr_text_mentions.csv") if (PROCESSED / "nsfr_text_mentions.csv").exists() else []
    field_map = read_csv(PROCESSED / "field_map.csv")
    entities = read_csv(PROCESSED / "entities.csv")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(build_html(summary, banks, nsfr, sources, notes, mentions, field_map, entities), encoding="utf-8")
    build_xlsx(summary, banks, nsfr, sources, notes, mentions, field_map, entities)
    print(f"wrote {HTML_OUT} ({HTML_OUT.stat().st_size:,} bytes) and {XLSX_OUT} ({XLSX_OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
