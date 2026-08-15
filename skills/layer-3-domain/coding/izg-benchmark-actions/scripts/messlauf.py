#!/usr/bin/env python3
"""Der Messlauf - Umschaltung, Ausfuehrung, Verwerfung und Verbuchung in einem Modul.

Warum eigenes Modul: die Regeln, die entscheiden ob eine Messung ueberhaupt zaehlt,
sind die teuersten Regeln des Skills - ein stillschweigend verbuchter Abbruch faelscht
jedes spaetere Urteil. Sie lagen bisher in der Schleife von `cmd_run` und waren damit
nur mit einem echten `claude`-Aufruf erreichbar; testbar war allein `discard_reason()`,
also die eine Zeile, die nie bricht.

Die Ausfuehrung selbst steht deshalb hinter einem seam: `fahre()` bekommt sie als
Aufrufparameter (Protokoll `Ausfuehrung`). Im Betrieb reicht `bench.py` den Adapter auf
die echte CLI herein, im Test einen Fake, der Timeout, Fehler-Exitcode und fehlendes
Transcript auf Kommando liefert. Zwei Adapter, also ein echter seam - keine Vorratshaltung.

Was hier zusammenbleibt, weil es nur zusammen richtig ist:

- Umschaltung laeuft vor *jedem* Lauf, nicht einmal je Variante
- ein verworfener Lauf belegt keine Laufnummer: `next_run_index` wird erst beim
  Schreiben verbraucht, der naechste Versuch bekommt dieselbe Nummer erneut
- verworfen wird bei Timeout, Fehler-Exitcode, Abbruch-Subtype und fehlendem Transcript;
  ein verworfener Lauf wird nicht verbucht und darf auch nicht nachgetragen werden
"""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import runs


@dataclass(frozen=True)
class Laufauftrag:
    """Alles, was fuer die Laeufe *einer* Variante feststeht - die Konstante der Schleife.

    `env` traegt Messrunde, Modell, CLI-Version und Aufgaben-Pruefsumme; es wird
    unveraendert an `runs.build_record()` durchgereicht.
    """

    task: str
    variant: str
    project: Path
    prompt: str
    outcome: str = "unset"
    note: str = ""
    setup: str | None = None
    model: str | None = None
    permission_mode: str = "acceptEdits"
    timeout: int = 900
    env: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Laufergebnis:
    """Das Ergebnis eines einzelnen Laufs - verbucht oder verworfen, nie beides.

    `verworfen` traegt den Grund im Klartext; ist es gesetzt, sind `record` und `pfad`
    None und die Laufnummer bleibt fuer den naechsten Versuch frei.
    """

    nummer: int
    run: int
    session_id: str
    verworfen: str | None = None
    record: dict[str, Any] | None = None
    pfad: Path | None = None


class Ausfuehrung(Protocol):
    """Der seam zur Aussenwelt: Shell, `claude -p` und das Transcript auf der Platte.

    Alles, was Geld kostet oder Dateien anfasst, liegt hinter diesen drei Methoden.
    """

    def schalte_um(self, setup: str, project: Path) -> None:
        """Stellt den Zustand der Variante her. Fehler bleiben ungeprueft - siehe SKILL.md."""

    def starte(self, auftrag: Laufauftrag, session_id: str) -> dict[str, Any]:
        """Fuehrt einen Lauf aus. Wirft `subprocess.TimeoutExpired` bei Zeitueberschreitung."""

    def miss(self, project: Path, session_id: str) -> dict[str, Any]:
        """Liest das Transcript. Wirft `FileNotFoundError`, wenn es keines gibt."""


def discard_reason(meta: dict[str, Any]) -> str | None:
    """Prueft Exitcode und CLI-Subtype eines Laufs auf Abbruch - ohne subprocess, ohne I/O.

    `meta` ist die Rueckgabe von `Ausfuehrung.starte()`.
    """
    if meta["exit_code"] != 0:
        return f"Exitcode {meta['exit_code']}"
    subtype = meta.get("cli_subtype")
    if subtype and subtype != "success":
        return f"Abbruch ({subtype})"
    return None


def _neue_session() -> str:
    return str(uuid.uuid4())


def fahre(out: Path, auftrag: Laufauftrag, wiederholungen: int, ausfuehrung: Ausfuehrung,
          *,
          neue_session: Callable[[], str] = _neue_session,
          melde: Callable[[int, int, int, str], None] | None = None,
          ) -> Iterator[Laufergebnis]:
    """Faehrt `wiederholungen` Laeufe einer Variante und verbucht, was zaehlt.

    Generator statt Liste: ein Lauf dauert Minuten, der Aufrufer soll nach jedem einzelnen
    ausgeben koennen statt am Ende alles auf einmal. `melde` wird *vor* dem Start gerufen
    (Nummer, Gesamtzahl, Laufnummer, Session-ID), damit waehrend eines langen Laufs
    ueberhaupt etwas auf dem Schirm steht.
    """
    for i in range(1, wiederholungen + 1):
        run = runs.next_run_index(out, auftrag.task, auftrag.variant)
        if auftrag.setup:
            ausfuehrung.schalte_um(auftrag.setup, auftrag.project)
        sid = neue_session()
        if melde:
            melde(i, wiederholungen, run, sid)

        try:
            meta = ausfuehrung.starte(auftrag, sid)
        except subprocess.TimeoutExpired:
            yield Laufergebnis(i, run, sid, verworfen=f"Timeout nach {auftrag.timeout} s")
            continue

        if grund := discard_reason(meta):
            yield Laufergebnis(i, run, sid, verworfen=grund)
            continue

        try:
            measured = ausfuehrung.miss(auftrag.project, sid)
        except FileNotFoundError as exc:
            yield Laufergebnis(i, run, sid, verworfen=str(exc))
            continue

        rec = runs.build_record(task=auftrag.task, variant=auftrag.variant, run=run,
                                project=auftrag.project, outcome=auftrag.outcome,
                                note=auftrag.note, measured=measured, meta=meta,
                                prompt_chars=len(auftrag.prompt), env=auftrag.env)
        yield Laufergebnis(i, run, sid, record=rec, pfad=runs.write_record(out, rec))
