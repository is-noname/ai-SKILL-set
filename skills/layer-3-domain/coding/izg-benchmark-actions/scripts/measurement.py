#!/usr/bin/env python3
"""Der Messlauf - Umschaltung, Ausfuehrung, Verwerfung und Verbuchung in einem Modul.

Warum eigenes Modul: die Regeln, die entscheiden ob eine Messung ueberhaupt zaehlt,
sind die teuersten Regeln des Skills - ein stillschweigend verbuchter Abbruch faelscht
jedes spaetere Urteil. Sie lagen bisher in der Schleife von `cmd_run` und waren damit
nur mit einem echten `claude`-Aufruf erreichbar; testbar war allein `discard_reason()`,
also die eine Zeile, die nie bricht.

Die Ausfuehrung selbst steht deshalb hinter einem seam: `drive()` bekommt sie als
Aufrufparameter (Protokoll `Executor`). Im Betrieb reicht `bench.py` den Adapter auf
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
class RunSpec:
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
class RunResult:
    """Das Ergebnis eines einzelnen Laufs - verbucht oder verworfen, nie beides.

    `discarded` traegt den Grund im Klartext; ist es gesetzt, sind `record` und `path`
    None und die Laufnummer bleibt fuer den naechsten Versuch frei.
    """

    index: int
    run: int
    session_id: str
    discarded: str | None = None
    record: dict[str, Any] | None = None
    path: Path | None = None


class Executor(Protocol):
    """Der seam zur Aussenwelt: Shell, `claude -p` und das Transcript auf der Platte.

    Alles, was Geld kostet oder Dateien anfasst, liegt hinter diesen drei Methoden.
    """

    def switch(self, setup: str, project: Path) -> None:
        """Stellt den Zustand der Variante her. Fehler bleiben ungeprueft - siehe SKILL.md."""

    def start(self, spec: RunSpec, session_id: str) -> dict[str, Any]:
        """Fuehrt einen Lauf aus. Wirft `subprocess.TimeoutExpired` bei Zeitueberschreitung."""

    def measure(self, project: Path, session_id: str) -> dict[str, Any]:
        """Liest das Transcript. Wirft `FileNotFoundError`, wenn es keines gibt."""


def discard_reason(meta: dict[str, Any]) -> str | None:
    """Prueft Exitcode und CLI-Subtype eines Laufs auf Abbruch - ohne subprocess, ohne I/O.

    `meta` ist die Rueckgabe von `Executor.start()`.
    """
    if meta["exit_code"] != 0:
        return f"Exitcode {meta['exit_code']}"
    subtype = meta.get("cli_subtype")
    if subtype and subtype != "success":
        return f"Abbruch ({subtype})"
    return None


def _new_session() -> str:
    return str(uuid.uuid4())


def drive(out: Path, spec: RunSpec, repeats: int, executor: Executor,
          *,
          new_session: Callable[[], str] = _new_session,
          notify: Callable[[int, int, int, str], None] | None = None,
          ) -> Iterator[RunResult]:
    """Faehrt `repeats` Laeufe einer Variante und verbucht, was zaehlt.

    Generator statt Liste: ein Lauf dauert Minuten, der Aufrufer soll nach jedem einzelnen
    ausgeben koennen statt am Ende alles auf einmal. `notify` wird *vor* dem Start gerufen
    (Nummer, Gesamtzahl, Laufnummer, Session-ID), damit waehrend eines langen Laufs
    ueberhaupt etwas auf dem Schirm steht.
    """
    for i in range(1, repeats + 1):
        run = runs.next_run_index(out, spec.task, spec.variant)
        if spec.setup:
            executor.switch(spec.setup, spec.project)
        sid = new_session()
        if notify:
            notify(i, repeats, run, sid)

        try:
            meta = executor.start(spec, sid)
        except subprocess.TimeoutExpired:
            yield RunResult(i, run, sid, discarded=f"Timeout nach {spec.timeout} s")
            continue

        if reason := discard_reason(meta):
            yield RunResult(i, run, sid, discarded=reason)
            continue

        try:
            measured = executor.measure(spec.project, sid)
        except FileNotFoundError as exc:
            yield RunResult(i, run, sid, discarded=str(exc))
            continue

        rec = runs.build_record(task=spec.task, variant=spec.variant, run=run,
                                project=spec.project, outcome=spec.outcome,
                                note=spec.note, measured=measured, meta=meta,
                                prompt_chars=len(spec.prompt), env=spec.env)
        yield RunResult(i, run, sid, record=rec, path=runs.write_record(out, rec))
