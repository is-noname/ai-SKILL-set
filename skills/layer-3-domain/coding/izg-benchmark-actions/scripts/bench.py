#!/usr/bin/env python3
"""Misst und vergleicht die Kosten einzelner Ablaeufe (Skills, Workflows, Prompts).

Anders als eine Verbrauchsanalyse ueber ein ganzes Projekt misst dieses Skript
**einzelne Laeufe**: jeder Lauf bekommt eine eigene Session-ID, wird isoliert
ausgefuehrt und einzeln verbucht. Aus mehreren Laeufen pro Variante entsteht ein
Vergleich mit Median und Spanne.

Nutzung:
    bench.py run --task t1 --variant mit-skill --prompt-file aufgabe.md --repeat 3
    bench.py measure --task t1 --variant manuell --session-id <uuid>
    bench.py judge --task t1 --variant mit-skill --run 1 --outcome ok
    bench.py compare --baseline ohne-skill
    bench.py history --task t1        # Verlauf ueber mehrere Messrunden
    bench.py plan show --task t1      # gespeicherte Messdefinition

Diese Datei ist die Kommandozeile und sonst nichts. Was sie zusammenschaltet:
`ausfuehrung.py` (CLI-Aufruf und Messung), `messlauf.py` (Schleife und Verwerfung),
`runs.py` (Laufdatensatz), `plans.py` (Messplan), `urteil.py` (das Urteil),
`bericht.py` (die Darstellung).

Alle Laufdaten liegen als JSON unter --out (Default: ~/.local/share/izg-bench).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import ausfuehrung
import bericht
import messlauf
import plans
import runs
import urteil

OUTCOMES = ("ok", "partial", "fail", "unset")


def default_out() -> Path:
    """Dauerhafte Ablage, nicht /tmp.

    Wer messen will, ob eine Optimierung etwas gebracht hat, braucht die Messung von vor
    drei Monaten noch. In /tmp ist sie nach dem naechsten Neustart weg, und dann bleibt
    nur der Vergleich gegen eine Erinnerung.
    """
    if env := os.environ.get("IZG_BENCH_OUT"):
        return Path(env).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "izg-bench"


def resolve_plan(args: argparse.Namespace, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Traegt Messplan und Kommandozeile zusammen. Der Aufruf schlaegt den Plan immer."""
    plan = None if args.no_plan else plans.load_plan(out, args.task)
    values = {k: getattr(args, k, None) for k in plans.PLAN_OPTIONS}
    if plan:
        print(f"Messplan: {plans.plan_path(out, args.task)}")
        values, notes = plans.fill_from_plan(plan, values)
        for n in notes:
            print(f"  ! {n}")
    else:
        plan = plans.new_plan(args.task)
    return plan, values


# ----------------------------------------------------------------------------- CLI


def cmd_run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    plan, values = resolve_plan(args, out)

    project = Path(values["project"] or os.getcwd()).resolve()
    permission_mode = values["permission_mode"] or "acceptEdits"
    timeout = values["timeout"] or 900
    prompt_file = Path(values["prompt_file"]).resolve() if values["prompt_file"] else None

    if args.prompt:
        prompt = args.prompt
    elif prompt_file:
        prompt = prompt_file.read_text(encoding="utf-8")
    else:
        print("Weder --prompt noch --prompt-file gesetzt (und kein Messplan hinterlegt).")
        return 2

    sha = plans.prompt_sha(prompt)
    if plan.get("prompt_sha") and plan["prompt_sha"] != sha:
        print(f"  ! Testaufgabe hat sich seit dem Messplan geaendert "
              f"({plan['prompt_sha']} -> {sha}). Frueher gemessene Laeufe sind nicht mehr "
              f"vergleichbar - alle Varianten neu messen.")

    setup = args.setup if args.setup is not None else plans.variant_setup(plan, args.variant)
    if note := plans.record_variant(plan, args.variant, setup):
        print(f"  {note}")
    if setup is None:
        print("  ! Keine Umschaltung (--setup) fuer diese Variante - es wird der Zustand "
              "gemessen, wie er gerade im Projekt liegt.")

    # Der Plan wird vor dem ersten Lauf geschrieben: ein Abbruch mittendrin soll die
    # Messdefinition nicht verlieren, sie ist das Teuerste an der Sache.
    for k in plans.PLAN_OPTIONS:
        if values.get(k) is not None:
            plan[k] = str(prompt_file) if k == "prompt_file" and prompt_file else values[k]
    plan["prompt_sha"] = sha
    plans.save_plan(out, plan)

    messrunde = args.round or date.today().isoformat()
    env = {"round": messrunde, "model": values["model"],
           "cli_version": ausfuehrung.cli_version(), "prompt_sha": sha}
    print(f"Messrunde {messrunde}, Modell {values['model'] or '(CLI-Default)'}, "
          f"CLI {env['cli_version'] or '?'}")

    auftrag = messlauf.Laufauftrag(
        task=args.task, variant=args.variant, project=project, prompt=prompt,
        outcome=args.outcome, note=args.note, setup=setup, model=values["model"],
        permission_mode=permission_mode, timeout=timeout, env=env)

    def melde(i: int, gesamt: int, run: int, sid: str) -> None:
        print(f"[{i}/{gesamt}] {args.task}/{args.variant} run {run} session {sid}")

    for erg in messlauf.fahre(out, auftrag, args.repeat,
                              ausfuehrung.ClaudeAusfuehrung(), melde=melde):
        if erg.verworfen:
            print(f"  {erg.verworfen} - Lauf wird nicht verbucht.")
            continue
        print(f"  gewichtet {erg.record['weighted_tokens']:,}".replace(",", ".")
              + f" Tokens, {erg.record['duration_s']} s -> {erg.pfad}")
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    project = Path(args.project or os.getcwd()).resolve()
    out = Path(args.out)
    try:
        measured = ausfuehrung.measure_session(project, args.session_id)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    run = args.run or runs.next_run_index(out, args.task, args.variant)
    env = {"round": args.round or date.today().isoformat(), "model": args.model,
           "cli_version": ausfuehrung.cli_version(), "prompt_sha": None}
    rec = runs.build_record(task=args.task, variant=args.variant, run=run, project=project,
                             outcome=args.outcome, note=args.note, measured=measured, env=env)
    print(f"verbucht: {runs.write_record(out, rec)}")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    p = runs.record_path(Path(args.out), args.task, args.variant, args.run)
    if not p.is_file():
        print(f"Kein Lauf unter {p}")
        return 1
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["outcome"] = args.outcome
    if args.note:
        rec["note"] = args.note
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{p.name}: outcome={args.outcome}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    out = Path(args.out)
    recs = runs.load_records(out, args.task)
    if args.round:
        recs = [r for r in recs if r.get("round") == args.round]
    if not recs:
        print(f"Keine Laufdaten unter {args.out}.")
        return 1
    baselines, notes = plans.resolve_baselines(out, (r["task"] for r in recs), args.baseline)
    beurteilt = urteil.beurteile(recs, baselines, strict_round=not args.across_rounds)
    print(json.dumps(urteil.zu_json(beurteilt.tabelle), ensure_ascii=False, indent=2)
          if args.json else bericht.report(beurteilt.tabelle, baselines))
    for n in notes:
        print(n)
    if args.across_rounds:
        print("\n! --across-rounds: Laeufe aus verschiedenen Messrunden stehen hier "
              "gegeneinander. Das Urteil ist eine Orientierung, kein Beleg.")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    out = Path(args.out)
    recs = runs.load_records(out, args.task)
    if not recs:
        print(f"Keine Laufdaten unter {args.out}.")
        return 1
    baselines, notes = plans.resolve_baselines(out, (r["task"] for r in recs), args.baseline)
    beurteilt = urteil.beurteile(recs, baselines, je_runde=True)
    if args.json:
        print(json.dumps({"runden": urteil.zu_json(beurteilt.tabelle),
                          "verlauf": urteil.zu_json(beurteilt.verlauf)},
                         ensure_ascii=False, indent=2))
    else:
        print(bericht.report(beurteilt.tabelle, baselines, show_round=True))
        print(bericht.render_trend(beurteilt.verlauf))
    for n in notes:
        print(n)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if args.plan_cmd == "list":
        found = plans.list_plans(out)
        if not found:
            print(f"Keine Messplaene unter {plans.plans_dir(out)}.")
            return 1
        for p in found:
            varianten = ", ".join(sorted(p.get("variants") or {})) or "-"
            print(f"{p['task']}: Varianten [{varianten}], Basis {p.get('baseline') or '-'}, "
                  f"Modell {p.get('model') or '-'}, "
                  f"zuletzt {p.get('updated_at') or p.get('created_at')}")
        return 0

    plan = plans.load_plan(out, args.task)
    if args.plan_cmd == "show":
        if not plan:
            print(f"Kein Messplan fuer '{args.task}' unter {plans.plans_dir(out)}.")
            return 1
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    # save: legt an oder aktualisiert, ohne dass dafuer gemessen werden muss.
    plan = plan or plans.new_plan(args.task)
    for k in plans.PLAN_OPTIONS:
        if (val := getattr(args, k, None)) is not None:
            plan[k] = str(Path(val).resolve()) if k in ("prompt_file", "project") else val
    if plan.get("prompt_file") and Path(plan["prompt_file"]).is_file():
        plan["prompt_sha"] = plans.prompt_sha(
            Path(plan["prompt_file"]).read_text(encoding="utf-8"))
    if note := plans.record_baseline(plan, args.baseline):
        print(note)
    if args.variant:
        if note := plans.record_variant(plan, args.variant, args.setup):
            print(note)
    print(f"gespeichert: {plans.save_plan(out, plan)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(default_out()), help="Ablage der Laufdaten")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--task", required=True, help="Kennung der Testaufgabe")
        p.add_argument("--variant", required=True, help="Kennung der Variante")
        # Default None statt cwd: nur so laesst sich "nicht angegeben" von "bewusst gesetzt"
        # unterscheiden - und nur dann darf ein Messplan den Wert beisteuern.
        p.add_argument("--project", help="Arbeitsverzeichnis des Laufs (Default: cwd/Messplan)")
        p.add_argument("--outcome", choices=OUTCOMES, default="unset", help="Ertrag des Laufs")
        p.add_argument("--note", default="", help="Freitext zum Lauf")
        p.add_argument("--round", help="Messrunde (Default: heutiges Datum). Nur innerhalb "
                                       "einer Runde wird ein Urteil gefaellt.")

    r = sub.add_parser("run", help="Laeufe headless ausfuehren und verbuchen")
    common(r)
    r.add_argument("--prompt", help="Testaufgabe als Text")
    r.add_argument("--prompt-file", help="Testaufgabe aus Datei (identisch fuer alle Varianten)")
    r.add_argument("--repeat", type=int, default=3, help="Anzahl Laeufe (Default 3)")
    r.add_argument("--setup", help="Shell-Kommando vor jedem Lauf, z. B. Variante einspielen")
    r.add_argument("--model", help="Modell fuer den Lauf")
    r.add_argument("--permission-mode", help="Default acceptEdits")
    r.add_argument("--timeout", type=int, help="Sekunden pro Lauf (Default 900)")
    r.add_argument("--no-plan", action="store_true",
                   help="gespeicherten Messplan ignorieren und nicht fortschreiben")
    r.set_defaults(func=cmd_run)

    m = sub.add_parser("measure", help="bereits gelaufene Session verbuchen")
    common(m)
    m.add_argument("--session-id", required=True)
    m.add_argument("--run", type=int, help="Laufnummer (Default: naechste freie)")
    m.add_argument("--model", help="Modell des Laufs, fuer die Vergleichbarkeit")
    m.set_defaults(func=cmd_measure)

    j = sub.add_parser("judge", help="Ertrag eines verbuchten Laufs setzen")
    j.add_argument("--task", required=True)
    j.add_argument("--variant", required=True)
    j.add_argument("--run", type=int, required=True)
    j.add_argument("--outcome", choices=OUTCOMES, required=True)
    j.add_argument("--note", default="")
    j.set_defaults(func=cmd_judge)

    c = sub.add_parser("compare", help="Varianten gegenueberstellen")
    c.add_argument("--task", help="nur diese Testaufgabe")
    c.add_argument("--baseline", help="Variante, gegen die verglichen wird")
    c.add_argument("--round", help="nur diese Messrunde")
    c.add_argument("--across-rounds", action="store_true",
                   help="Urteil auch ueber Messrunden hinweg faellen (nicht belastbar)")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_compare)

    h = sub.add_parser("history", help="Verlauf einer Testaufgabe ueber mehrere Messrunden")
    h.add_argument("--task", help="nur diese Testaufgabe")
    h.add_argument("--baseline", help="Variante, gegen die je Runde verglichen wird")
    h.add_argument("--json", action="store_true")
    h.set_defaults(func=cmd_history)

    pl = sub.add_parser("plan", help="Messdefinition speichern, ansehen, auflisten")
    plsub = pl.add_subparsers(dest="plan_cmd", required=True)
    for name, hint in (("save", "anlegen oder aendern"), ("show", "anzeigen")):
        sp = plsub.add_parser(name, help=hint)
        sp.add_argument("--task", required=True)
        if name == "save":
            sp.add_argument("--prompt-file", help="Datei mit der Testaufgabe")
            sp.add_argument("--project", help="Arbeitsverzeichnis der Laeufe")
            sp.add_argument("--model")
            sp.add_argument("--permission-mode")
            sp.add_argument("--timeout", type=int)
            sp.add_argument("--baseline", help="Variante, gegen die verglichen wird")
            sp.add_argument("--variant", help="Variante, deren Umschaltung festgehalten wird")
            sp.add_argument("--setup", help="Umschaltkommando dieser Variante")
    plsub.add_parser("list", help="alle Messplaene")
    pl.set_defaults(func=cmd_plan)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
