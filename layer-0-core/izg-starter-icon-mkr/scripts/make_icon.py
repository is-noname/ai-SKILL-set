#!/usr/bin/env python3
"""Erzeugt ein Custom-App-Icon als SVG im IZG-Designstil.

Stil = dunkle abgerundete Kachel (--bg #111, Rahmen #272727, rx 24) mit einem
Glyph in Canto-Green (#06fc99). Entspricht den globalen Design-Tokens und den
bisherigen handgebauten Icons (claude-config-dashboard.svg, hub-icon.svg).

Glyph-Varianten:
    letter    Initiale(n) der App, gross und grün (Default, generisch)
    play      Play-Dreieck (Starter-Charakter)
    terminal  Terminal-/Dashboard-Fenster
    rhombus   Raute (wie Mistral Hub)

Beispiel:
    make_icon.py --name "Stonky" --out ~/.local/share/icons/stonky.svg
    make_icon.py --name "Pattern Pilot" --glyph play --out /tmp/pp.svg
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ACCENT = "#06fc99"
BG = "#111111"
BORDER = "#272727"
SURFACE = "#232323"
MUTED = "#555555"
FAINT = "#333333"


def initials(name: str) -> str:
    words = [w for w in re.split(r"[\s_\-]+", name.strip()) if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def glyph_letter(name: str) -> str:
    text = initials(name)
    size = 56 if len(text) == 1 else 44
    return (
        f'  <text x="64" y="64" font-family="Manrope, Segoe UI, sans-serif" '
        f'font-size="{size}" font-weight="800" fill="{ACCENT}" '
        f'text-anchor="middle" dominant-baseline="central">{text}</text>\n'
    )


def glyph_play() -> str:
    return (
        f'  <circle cx="64" cy="64" r="34" fill="none" stroke="{ACCENT}" stroke-width="6"/>\n'
        f'  <path d="M54 46 L86 64 L54 82 Z" fill="{ACCENT}"/>\n'
    )


def glyph_rhombus() -> str:
    return (
        f'  <path d="M64 30 L92 64 L64 98 L36 64 Z" fill="none" stroke="{ACCENT}" '
        f'stroke-width="6" stroke-linejoin="round"/>\n'
        f'  <path d="M64 48 L78 64 L64 80 L50 64 Z" fill="{ACCENT}"/>\n'
    )


def glyph_terminal() -> str:
    return (
        f'  <rect x="24" y="28" width="80" height="72" rx="8" fill="{SURFACE}" '
        f'stroke="{BORDER}" stroke-width="2"/>\n'
        f'  <rect x="24" y="28" width="80" height="8" rx="6" fill="{ACCENT}"/>\n'
        f'  <path d="M36 56 L48 66 L36 76" fill="none" stroke="{ACCENT}" '
        f'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>\n'
        f'  <rect x="56" y="72" width="34" height="5" rx="2" fill="{MUTED}"/>\n'
        f'  <rect x="36" y="86" width="54" height="4" rx="2" fill="{FAINT}"/>\n'
    )


GLYPHS = {
    "letter": lambda name: glyph_letter(name),
    "play": lambda name: glyph_play(),
    "terminal": lambda name: glyph_terminal(),
    "rhombus": lambda name: glyph_rhombus(),
}


def build_svg(name: str, glyph: str) -> str:
    body = GLYPHS[glyph](name)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" '
        'viewBox="0 0 128 128">\n'
        f'  <rect x="4" y="4" width="120" height="120" rx="24" fill="{BG}" '
        f'stroke="{BORDER}" stroke-width="2"/>\n'
        f"{body}"
        "</svg>\n"
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Custom-App-Icon (SVG) im IZG-Stil erzeugen.")
    p.add_argument("--name", required=True, help="App-Name (für Initialen/Default)")
    p.add_argument("--glyph", choices=list(GLYPHS), default="letter",
                   help="Glyph-Variante (Default: letter)")
    p.add_argument("--out", required=True, help="Zielpfad der SVG-Datei")
    args = p.parse_args()

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_svg(args.name, args.glyph), encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
