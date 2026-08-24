---
name: izg-kissd
description: Prueft Skills und Workflows auf Idiotensicherheit — findet Stellen, an denen ein schwaches Modell abweichen kann, und liefert konkrete Korrekturvorschlaege. Use when ein Skill, ein Prompt oder ein Workflow reproduzierbar und fremdmodell-tauglich werden soll.
layer: 1
dependencies: []
---

# IZG KISSD — Keep It Simple Stupid, Dude

Ein Skill ist erst fertig, wenn ihn ein schwaches Fremdmodell ohne Vorwissen
fehlerfrei und wiederholbar abarbeitet. Dieser Skill misst genau das: **wie viel
Handlungsspielraum bleibt dem Agenten, und wo wird daraus ein Fehler?**

Prueft fremde Skills, Prompts, Runbooks, CLAUDE.md-Abschnitte. Er **aendert nichts**
von sich aus — er liefert Befund plus Korrekturvorschlag, das Umschreiben ist ein
eigener Auftrag.

## Die Rubrik

| ID | Prinzip | Fehlerbild beim schwachen Modell |
|----|---------|----------------------------------|
| K1 | **Kein Spielraum** | "den passenden Pfad waehlen" → Modell erfindet einen |
| K2 | **Kopiervorlage statt Prosa** | Befehl beschrieben statt gezeigt → falsche Flags |
| K3 | **Absolute Anker** | `./script.sh` → laeuft im falschen Verzeichnis |
| K4 | **Verifikation pro Schritt** | kein Soll-Zustand → Fehler faellt drei Schritte spaeter auf |
| K5 | **Fehlerpfad benannt** | Schritt scheitert → Modell macht stumm weiter |
| K6 | **Reihenfolge erzwungen** | unnummeriert → Modell springt oder ueberspringt |
| K7 | **Voraussetzungen deklariert** | Tool fehlt → Abbruch mitten im Ablauf |
| K8 | **Token-sparsam** | `cat`/`find` ohne Filter, aufgeblaehte SKILL.md |
| K9 | **Idempotent** | zweiter Lauf bricht ab oder dupliziert |
| K10 | **Metadaten korrekt** | Frontmatter kaputt → Skill wird nie gefunden |

**Merksatz:** Jeder Schritt hat genau eine richtige Ausfuehrung, einen sichtbaren
Soll-Zustand und eine benannte Reaktion auf Fehlschlag.

## Ablauf

1. Ziel klaeren. Fehlt der Pfad, den Nutzer fragen — nicht raten.

2. Lint starten (deckt K1-K10 mechanisch ab):

```bash
KISSD=~/.claude/skills/izg-kissd
ZIEL=.claude/skills/beispiel-skill   # vom Nutzer genannter Pfad
python3 "$KISSD/scripts/kissd_lint.py" "$ZIEL" --json
```

`ZIEL` ist eine `SKILL.md`, ein Skill-Ordner, ein Verzeichnisbaum oder eine
Markdown-Datei. Ohne `--json` kommt eine Markdown-Tabelle. `--strict` setzt
Exit-Code 1 auch bei `warn`.

3. Zieldatei lesen und die vier Punkte pruefen, die kein Regex entscheidet:

   - **Selbsttest-Frage:** Ein Modell ohne diese Session, ohne dieses Repo, ohne
     Rueckfragemoeglichkeit — kommt es durch? Jede Stelle, an der die Antwort
     "kommt drauf an" lautet, ist ein Befund.
   - **Entscheidungspunkte:** Jede Verzweigung braucht eine pruefbare Bedingung
     ("wenn Exit-Code 1"), keine Einschaetzung ("wenn es Probleme gibt").
   - **Vorwissen:** Wird ein Skill, ein Alias, eine Konvention vorausgesetzt, die
     ein Fremdagent nicht hat? Dann braucht es einen Fallback im Dokument.
   - **Ergebnisform:** Ist das Ausgabeformat festgelegt (Datei, Abschnitte,
     Sortierung)? Freies Format heisst: nicht reproduzierbar, nicht diffbar.

4. Report schreiben (Format unten). Lint-Befunde und manuelle Befunde in **eine**
   Tabelle, sortiert nach Severity, dann Check-ID, dann Zeile.

5. Fragen, ob die Vorschlaege eingebaut werden sollen. Erst auf Zusage editieren.

## Report-Format

Fest, damit zwei Laeufe vergleichbar bleiben:

```markdown
# KISSD-Report: <ziel>

KISS-Score <n>/100 — block: <n> | warn: <n> | info: <n>

## Befunde

| Check | Sev | Stelle | Befund | Vorschlag |
|---|---|---|---|---|

## Top-3-Korrekturen

1. <Befund> → <konkreter Ersatztext oder Codeblock>
```

Regeln fuer die Vorschlagsspalte:

- Jeder Befund braucht einen Vorschlag. Befund ohne Vorschlag wird gestrichen.
- Der Vorschlag ist **Ersatztext**, keine Absichtserklaerung: nicht "praeziser
  formulieren", sondern der fertige Satz oder Codeblock.
- Top-3 nach Severity, dann nach Zahl der betroffenen Stellen.

## Verifikation

Nach dem Lauf pruefen:

- Exit-Code 0 = keine `block`-Befunde. Exit-Code 1 = mindestens einer, der
  Report nennt ihn. Exit-Code 2 = Pfad existiert nicht.
- Jeder Befund im Report traegt Datei und Zeilennummer.
- Zweiter Lauf ueber denselben Stand liefert denselben Score.

## Wenn etwas fehlschlaegt

| Symptom | Ursache | Massnahme |
|---|---|---|
| Exit-Code 2, "Pfad existiert nicht" | Ziel falsch angegeben | Nutzer nach dem Pfad fragen, nicht suchen |
| "keine SKILL.md gefunden" | Verzeichnis ohne Skills | Direkt auf die Markdown-Datei zeigen |
| Score 100, aber Skill fuehlt sich unsicher an | Befund liegt in Schritt 3 | Die vier manuellen Punkte durchgehen — Lint ersetzt sie nicht |
| Sehr viele K7-Befunde | `requires.json` fehlt | Eine `requires.json` anlegen, danach erneut pruefen |

## Grenzen

Der Lint prueft Text, keine Wirkung. Ein Skill kann 100/100 erreichen und
trotzdem das Falsche tun — Korrektheit der Logik ist Aufgabe eines Reviews, nicht
dieses Skills. `warn`-Befunde sind Hinweise auf Spielraum, kein Urteil: in einem
bewusst explorativen Skill ist Spielraum gewollt. Das gehoert in den Report als
Einordnung, nicht als stille Unterdrueckung.
