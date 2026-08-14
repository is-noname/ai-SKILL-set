#!/usr/bin/env python3
"""Rendert das analyze()-Ergebnis als eigenstaendige HTML-Datei.

Teilt sich das Datenformat mit report() aus analyze_transcript.py - beide
nehmen dasselbe analyze()-Dict entgegen (Shape siehe dort). Aufbau,
Diagramm-Muster und Stil fuer die Kandidaten-Karten generiert dieses Skript
nicht - die kennt nur der Agent, siehe HTML-REPORT.md. `#kandidaten` und
`#hebel` bleiben deshalb leere, kommentierte Container.
"""

from __future__ import annotations

from html import escape
from typing import Any

CACHE_HIT_RATE_THRESHOLD = 0.85


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + " %"


def _bars(tokens_per_tool: dict[str, int]) -> str:
    if not tokens_per_tool:
        return '<p class="text-sm text-slate-500">Keine Tool-Aufrufe gemessen.</p>'
    max_tokens = max(tokens_per_tool.values())
    rows = []
    for tool, tokens in tokens_per_tool.items():
        width = round(tokens / max_tokens * 100, 1) if max_tokens else 0
        rows.append(
            '<div class="flex items-center gap-3">'
            f'<span class="w-24 text-xs uppercase tracking-wider">{escape(tool)}</span>'
            f'<div class="bar burn" style="width: {width}%"></div>'
            f'<span class="font-mono text-sm">{_fmt(tokens)}</span>'
            "</div>"
        )
    return '<div class="space-y-2">' + "".join(rows) + "</div>"


def _cache_tile(cache_hit_rate: float) -> str:
    unter_schwelle = cache_hit_rate < CACHE_HIT_RATE_THRESHOLD
    tint = "bg-red-50 border-red-300 text-red-700" if unter_schwelle else "bg-white border-slate-200"
    hinweis = "Cache-Bruch - unter der 85 %-Schwelle." if unter_schwelle else "Cache haelt."
    return (
        f'<div class="rounded-lg border {tint} p-4 max-w-xs">'
        f'<div class="font-mono text-2xl">{_fmt_pct(cache_hit_rate)}</div>'
        f'<div class="text-sm">{hinweis}</div>'
        "</div>"
    )


def _repeats_table(repeats: list[dict[str, Any]]) -> str:
    if not repeats:
        return '<p class="text-sm text-slate-500">Keine wiederholten Aufrufe.</p>'
    rows = []
    for r in repeats:
        rows.append(
            "<tr>"
            f'<td class="pr-4 py-1">{r["count"]}x</td>'
            f'<td class="pr-4 py-1 font-mono text-xs">{_fmt(r["tokens"])}</td>'
            f'<td class="py-1 font-mono text-xs break-all">{escape(r["tool"])} {escape(r["label"])}</td>'
            "</tr>"
        )
    return (
        '<table class="w-full text-left text-sm">'
        '<thead><tr class="text-xs uppercase tracking-wider text-slate-500">'
        '<th class="pr-4">Wiederholungen</th><th class="pr-4">Tokens</th><th>Aufruf</th>'
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_html(data: dict[str, Any], project_name: str, generated_at: str) -> str:
    """Rendert `data` (Shape von `analyze_transcript.analyze()`) als HTML-Report.

    `data["sessions"] == 0` steht fuer den Fall ohne Transcripts und zeigt den
    roten "Keine Messdaten"-Kasten statt der Messwerte.
    """
    keine_daten = data["sessions"] == 0
    if keine_daten:
        header_extra = (
            '<div class="rounded border border-red-300 bg-red-50 text-red-700 px-4 py-2 text-sm">'
            "Keine Messdaten. Alle Kandidaten sind statisch geschaetzt."
            "</div>"
        )
        datenbasis = "Keine Transcripts ausgewertet."
    else:
        header_extra = ""
        datenbasis = (
            f'{data["requests"]} Requests aus {data["sessions"]} Sessions, '
            f'Cache-Trefferquote {_fmt_pct(data["cache_hit_rate"])}'
        )

    return f"""<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <title>Token-Review — {escape(project_name)}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
    </script>
    <style>
      .bar {{ height: 1.5rem; border-radius: 2px; }}
      .burn {{ background: #dc2626; }}
      .save {{ background: #059669; }}
      .idle {{ background: #cbd5e1; }}
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header class="space-y-2">
        <h1 class="text-2xl font-semibold">Token-Review — {escape(project_name)}</h1>
        <p class="text-sm text-slate-500">{escape(generated_at)}</p>
        <p class="text-sm">{escape(datenbasis)}</p>
        {header_extra}
      </header>
      <section id="messung" class="space-y-8">
        <h2 class="text-lg font-semibold">Messung</h2>
        {_bars(data["tokens_per_tool"])}
        {_cache_tile(data["cache_hit_rate"])}
        {_repeats_table(data["repeats"])}
      </section>
      <!-- Kandidaten-Karten - fuellt der Agent, siehe HTML-REPORT.md -->
      <section id="kandidaten" class="space-y-10"></section>
      <!-- Groesster Hebel - fuellt der Agent, siehe HTML-REPORT.md -->
      <section id="hebel"></section>
    </main>
  </body>
</html>
"""
