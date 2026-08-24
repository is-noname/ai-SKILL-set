# Ticketsystem — Architektur & Funktionsweise

Dieser Guide erklärt, **wie** das Ticketsystem aufgebaut ist und intern arbeitet —
für Funktionsverständnis, nicht als Konvention-Nachschlagewerk.

> 🇬🇧 English version: [`ticket-system-architecture.en.md`](./ticket-system-architecture.en.md)

> **Platzhalter-Hinweis:** In diesem Dokument steht `PRJ` überall für das
> **projektspezifische Prefix**. Jedes Projekt hat sein eigenes Prefix in der
> Registry `~/ai-shared/project-identifier.md` (z.B. ein
> dreistelliges Prefix pro Repo). `PRJ`, `NNN` und Namen wie `mein-projekt` sind
> generische Platzhalter — **keine** festen oder reservierten Bezeichnungen.

| Du willst… | Lies… |
|------------|-------|
| die Regeln/Felder (was darf rein, wie heißt was) | `docs/tickets.md` |
| die Kurz-Lookup-Regeln im Projekt | `tickets/PROTOCOL.md` |
| **verstehen wie die Mechanik funktioniert** | **dieses Dokument** |

---

## 1. Idee in einem Satz

Tickets sind **Markdown-Dateien in Ordnern**. Der Ordner, in dem eine Datei liegt,
*ist* ihr Status. Es gibt keine Datenbank, kein Backend, keinen Server — nur Dateien,
ein Zähler, ein Hook und drei Shell-Skripte. Alles ist git-freundlich, diffbar und
von mehreren Agenten (z.B. Claude, Gemini, Codex) gemeinsam nutzbar.

**Konsequenz:** Den Status eines Tickets ändert man, indem man das `status:`-Feld im
Frontmatter editiert. Ein Hook verschiebt die Datei dann in den passenden Ordner.
Ordner und Frontmatter-Status sind also immer redundant — aber das Frontmatter ist
die Quelle der Wahrheit, der Ordner nur die Projektion.

---

## 2. Komponenten-Landkarte

```
projekt/
├── scripts/
│   ├── init_tickets.sh          # Bootstrap pro PROJEKT (legt tickets/ an)
│   ├── next_ticket_id.sh        # vergibt die nächste freie ID (atomar)
│   └── setup_global_conventions.sh  # Bootstrap pro AGENT (deployt Konvention global)
├── hooks/
│   └── ticket-mover.sh          # verschiebt Tickets bei Status-Änderung
├── docs/
│   ├── tickets.md               # Konvention (wird ins Agent-Verzeichnis deployt)
│   ├── doc-ids.md               # Doc-ID-Schema (ebenso global deployt; Prefix-Registry separat)
│   └── ticketsystem-architektur.md  # dieses Dokument
└── tickets/
    ├── .counter                 # höchste bisher vergebene Nummer
    ├── PROTOCOL.md              # projektlokale Kurzregeln
    ├── open/                    # status: open
    ├── in-progress/             # status: in-progress
    ├── blocked/                 # status: blocked
    └── done/                    # status: done  (finales Archiv)
```

| Komponente | Rolle | Wann aktiv |
|------------|-------|------------|
| `tickets/<status>/` | Ablage; Ordnername = Status | immer |
| `.counter` | merkt sich die höchste ID-Nummer | bei ID-Vergabe |
| `next_ticket_id.sh` | berechnet & reserviert die nächste ID | manuell vor Ticket-Anlage |
| `ticket-mover.sh` (Hook) | hält Ordner und `status:` synchron | automatisch nach jedem Edit/Write |
| `init_tickets.sh` | baut `tickets/` in einem Projekt auf | einmal pro Projekt |
| `setup_global_conventions.sh` | deployt Konvention ins Agent-Verzeichnis | einmal pro Agent/Maschine |
| `project-identifier.md` | liefert das Projekt-Prefix `PRJ` (Registry, global) | bei ID-Vergabe |

---

## 3. Lebenszyklus eines Tickets

```
                  next_ticket_id.sh PRJ
                          │
                          ▼
        ┌────────────────────────────────────────┐
        │  Datei anlegen: open/PRJ-T-NNN_…​.md     │
        │  status: open                            │
        └────────────────────────────────────────┘
                          │
    status: in-progress   │   (Hook verschiebt → in-progress/)
                          ▼
        ┌────────────────────────────────────────┐
        │            Arbeit läuft                  │
        └────────────────────────────────────────┘
            │                       │
status: done│                       │ status: blocked
            ▼                       ▼
      done/ (Archiv)           blocked/
                                    │ status: open
                                    ▼
                                 open/  (nie direkt → in-progress)
```

**Regeln, die die Mechanik erzwingt bzw. erwartet:**
- Jeder Statuswechsel = ein Verlaufseintrag (wann, warum, was erledigt/offen).
  Das erzwingt kein Skript — es ist Konvention und Teil der Review-Qualität.
- `blocked/` geht immer zurück nach `open/`, nie direkt nach `in-progress/`.
- `done/` wird nie gelöscht — es ist das Archiv und die Quelle für die
  Selbstheilung der ID-Vergabe (siehe §4).

---

## 4. ID-Vergabe — wie `next_ticket_id.sh` arbeitet

Aufruf (Argument ist das Projekt-Prefix):
```bash
bash scripts/next_ticket_id.sh PRJ     # → PRJ-T-019
```

Das Skript ist **selbstheilend** und **kollisionssicher**. Ablauf:

```
1. flock auf .counter.lock          → serialisiert parallele Aufrufe
2. counter   = Wert aus .counter    → Nicht-Ziffern werden weggeworfen (kein Crash)
3. max_exist = höchste PRJ-T-NNN     → über ALLE Ordner (grep über tickets/)
4. floor     = max(counter, max_exist)
5. next      = floor + 1
6. .counter  = next                  → fortschreiben
7. Ausgabe   = PRJ-T-019
```

**Warum so?**

- **Selbstheilend (Schritt 3):** Der Counter ist nur ein Cache. Die wahre höchste
  Nummer ergibt sich aus den real existierenden Tickets. Geht der Counter verloren,
  driftet oder wird ein Projekt nachträglich gebootstrappt, liefert `grep` über alle
  Ordner trotzdem die korrekte Basis. Es gibt damit genau **eine Quelle der Wahrheit**.
- **Crash-fest (Schritt 2):** `tr -dc '0-9'` schält nicht-numerischen Müll aus
  `.counter`. Schlimmstenfalls steht der Counter auf 0 — Schritt 3 fängt das auf.
- **Kollisionssicher (Schritt 1):** Ohne Lock würden zwei gleichzeitig laufende
  Agenten beide denselben `floor` lesen und dieselbe ID bekommen. `flock` über
  fd 9 auf `.counter.lock` serialisiert das Lesen-Rechnen-Schreiben. Fehlt `flock`
  auf dem System, läuft es ohne Lock weiter — die Selbstheilung fängt Drift dann
  nachträglich ab (nur die Echtzeit-Eindeutigkeit ist dann nicht garantiert).

> Das Prefix `PRJ` ist **kein** Teil des Skripts — es kommt als Argument und stammt
> aus der Registry `~/ai-shared/project-identifier.md` (Single
> Source of Truth für Projekt-Prefix). Jedes Projekt hat sein eigenes.

> **Standardweg:** `scripts/tickets.sh new` ruft denselben `flock`-Codepfad auf,
> legt die Datei aber gleich mit an und füllt das Frontmatter — ein Kommando statt
> ID abfragen und Datei von Hand anlegen (siehe `docs/tickets.md`). Der obige Ablauf
> (Schritte 1–7) ist die Mechanik dahinter, unverändert.

---

## 5. Status-Synchronisation — wie der Hook arbeitet

`hooks/global/ticket-mover.sh` ist ein **PostToolUse-Hook**: Claude Code ruft ihn nach
jedem `Edit`/`Write` auf und übergibt JSON über stdin. Der Hook entscheidet selbst,
ob er zuständig ist.

```
Edit/Write auf eine Datei
        │
        ▼
  Ist es ein Edit/Write?                  nein → exit (nichts tun)
        │ ja
  Liegt die Datei unter */tickets/*?      nein → exit
        │ ja
  Hat sie gültiges Frontmatter            nein → exit
  (id: PRJ-T-NNN)?
        │ ja
  status: ist ein bekannter Wert?         nein → exit
  (open|in-progress|blocked|done)
        │ ja
  Ordnername == status?                   ja   → exit (schon korrekt)
        │ nein
  Ziel-Datei existiert schon?             ja   → WARNUNG, NICHT verschieben
        │ nein
        ▼
  mv -n  →  tickets/<status>/<datei>
  Meldung auf stderr
```

**Wichtige Eigenschaften:**
- **Idempotent & defensiv:** Greift nur bei echten Ticket-Dateien mit gültigem
  Frontmatter und bekanntem Status. Alles andere lässt er unangetastet.
- **Kollisionsschutz:** Liegt im Zielordner bereits eine gleichnamige Datei (z.B.
  gleiche ID durch manuelles Verschieben in zwei Ordnern), verschiebt der Hook
  **nicht** und warnt auf stderr — kein stilles Überschreiben, kein Datenverlust.
  `mv -n` ist die zweite Absicherung.
- **Der Hook verschiebt nur — er ändert nie Inhalt.** Das `status:`-Feld setzt
  immer der Mensch oder Agent.

> **Standardweg:** `scripts/tickets.sh move <ID> <status> "<verlaufstext>"` schreibt
> Verlaufseintrag und `status:`-Feld in einem Kommando und ruft danach denselben
> `sync`-Codepfad auf, den der Hook nutzt (siehe `docs/tickets.md`). Der Hook bleibt
> das Sicherheitsnetz für den manuellen Zwei-Edit-Weg (Verlaufseintrag, dann
> `status:` per Hand) — bei Claude/Vibe automatisch, bei Codex/Gemini durch
> expliziten `tickets.sh sync`-Aufruf. Der obige Ablauf beschreibt diese
> Sicherheitsnetz-Mechanik, unverändert.

---

## 6. Zwei Bootstrap-Ebenen

Das System wird auf zwei Ebenen eingerichtet — leicht zu verwechseln:

| | `setup_global_conventions.sh` | `init_tickets.sh` |
|---|---|---|
| **Ebene** | pro AI-Agent (global) | pro Projekt |
| **Wie oft** | einmal pro Agent/Maschine | einmal pro Projekt |
| **Was** | deployt `tickets.md` + `doc-ids.md` + `project-identifier.md` (Prefix-Registry, per Symlink) **und** `init_tickets.sh` ins Agent-Verzeichnis und patcht dessen Konfig | legt `tickets/`-Ordnerstruktur, `.counter`, `PROTOCOL.md` und `next_ticket_id.sh` an |
| **Ziel** | `~/.claude`, `~/.codex`, `~/.gemini`, `~/.vibe` | beliebiger Projektordner |
| **Konfig-Datei** | `CLAUDE.md` / `AGENTS.md` (Codex) / `GEMINI.md` / `AGENTS.md` (Vibe) | — |

**Globale Ebene** — jeder Agent kennt die Konvention systemweit:
```bash
bash scripts/setup_global_conventions.sh ~/.claude
bash scripts/setup_global_conventions.sh ~/.codex
```
Die Konvention-Docs **und** `init_tickets.sh` bezieht das Skript in dieser Reihenfolge:
1. lokal aus dem Repo (wenn ausgecheckt) — der Normalfall
2. per `curl` von `RAW_BASE` (aus `git remote` abgeleitet, per
   `AISKILLSET_RAW_BASE` überschreibbar)
3. ist beides nicht erreichbar → klare Fehlermeldung + Exit 1 (kein stiller Skip)

`init_tickets.sh` landet dabei in `$AGENT_DIR/scripts/`, damit der unten in die
Agent-Konfig gepatchte Bootstrap-Hinweis auch wirklich auf ein vorhandenes Skript zeigt
(für jeden Agent sein eigenes Verzeichnis, nicht hartkodiert `~/.claude`).

**Projekt-Ebene** — ein konkretes Projekt bekommt sein `tickets/` (Pfad zeigt aufs eigene
Agent-Verzeichnis, hier `~/.claude` als Beispiel):
```bash
bash ~/.claude/scripts/init_tickets.sh /pfad/zum/projekt
```
Idempotent: erneutes Ausführen rüstet fehlenden Counter / aktuelles
`next_ticket_id.sh` nach, ohne bestehende Tickets oder `PROTOCOL.md` zu überschreiben.

**Bestandsprojekte nachziehen:** Kommen im Repo neue oder geänderte Projekt-Skripte
dazu (etwa `tickets.sh` mit IZG-T-089), bekommen bereits gebootstrappte Projekte die
nicht von selbst — sie behalten den Stand ihres letzten Laufs. Nach solchen Änderungen
denselben Befehl im Bestandsprojekt erneut ausführen; er kopiert die aktuellen Skripte
über die alten und lässt Tickets, Counter und `PROTOCOL.md` unangetastet.

### Verteilung und Drift-Erkennung (IZG-T-158)

`pull_skill.py` verteilt **Skills** (Registry-basiert, Ziel `.claude/skills/`).
`scripts/tickets.sh` ist kein Skill, sondern **Projekt-Infrastruktur** im Projekt-Root und
bleibt deshalb bewusst ein getrennter Weg über `init_tickets.sh`. Grund: Skills sind
zustandslose Verzeichnisse, die per Digest vergleichbar sind; das Ticketsystem hat
projektlokalen Zustand (`PROTOCOL.md` mit dem Prefix, `.counter`), der beim Kopieren
mitgeprüft werden muss. Eine frisch kopierte `tickets.sh` ist ohne diesen Zustand nicht
zwingend funktionsfähig.

Damit dieser Stand nicht still driftet, gibt es den Ist-Soll-Bericht:

```bash
bash scripts/check_project_drift.sh                       # alle Projekte unter ~/Dokumente
bash scripts/check_project_drift.sh /pfad/zum/projekt     # gezielt
```

Read-only, Gegenstück zu `check_global_drift.sh` (dieselbe Frage für die Agent-Dirs).
Gemeldet wird pro Projekt: deployte Skripte (`fehlt` / `veraltet` / `aktuell`),
Vollständigkeit der Statusordner, ob der `{PRJ}`-Platzhalter in `PROTOCOL.md` ersetzt ist,
und ob `.counter` unter der höchsten real vergebenen ID liegt. Exit 1 = Drift gefunden.

**Kein Versionsfeld in `tickets.sh`.** Verglichen wird der Dateiinhalt gegen die
Repo-Quelle. Eine von Hand gepflegte Versionsnummer wäre genau die Art stiller Drift, die
der Bericht aufdecken soll — vergisst jemand das Hochzählen, meldet das Skript fälschlich
„aktuell". Die Repo-Quelle ist ohnehin die einzige Wahrheit und beim Prüflauf immer da.

---

## 7. Kopplung mit dem doc-ids-System

Das Ticketsystem und die Doc-IDs teilen sich das **Projekt-Prefix** aus der Registry
`project-identifier.md`:

- Ticket-IDs: `PRJ-T-NNN` → `{PREFIX}-T-{NUMMER}`
- Doc-IDs: `{TYP}-{DATUM}-{SEQ}` (z.B. `AUD-{YYYYMMDD}-001_…`)

Verknüpfung in beide Richtungen:
- **Dokument → Tickets:** ein Audit/Report schlägt Tickets vor; im Ticket verweist
  das `source:`-Feld zurück auf das auslösende Dokument.
- **Tickets → Gruppe:** zusammengehörige Tickets teilen sich ein `group:`-Feld
  (ersetzt lose TODO-Listen). Abfrage (Gruppen-Slug ist frei wählbar):
  ```bash
  grep -rl "^group: <gruppen-slug>" tickets/
  ```

`FIX`, `FIXR`, `TODO` sind **keine** Doc-IDs — sie werden als Tickets erfasst.

---

## 8. Mehr-Agenten-Betrieb

Mehrere Agenten arbeiten am selben `tickets/`:
- `created-by:` und `assigned:` halten fest, wer ein Ticket erstellt hat bzw. wer
  zuständig ist (`claude` / `gemini` / `codex` / `me`).
- Die ID-Vergabe ist durch `flock` gegen Race Conditions abgesichert (§4).
- Da alles Dateien sind, läuft die Koordination über Git: Tickets werden committet,
  Konflikte sind normale Merge-Konflikte auf Textdateien.

---

## 9. Troubleshooting

| Symptom | Ursache / Lösung |
|---------|------------------|
| Ticket bleibt nach Status-Änderung im falschen Ordner | Hook nicht installiert/aktiv, oder Frontmatter ungültig (`id:`/`status:` prüfen). Status muss exakt `open`/`in-progress`/`blocked`/`done` sein. |
| „Ziel … existiert bereits — nicht verschoben" | Gleiche ID liegt in zwei Ordnern. Manuell auflösen, dann erneut Status setzen. |
| `next_ticket_id.sh` liefert dieselbe ID doppelt | `flock` fehlt auf dem System → installieren (util-linux). Die Selbstheilung korrigiert Drift beim nächsten Lauf. |
| Zwei Tickets mit gleicher Nummer existieren | Eines umbenennen (höhere freie Nummer via Skript holen), Verlauf vermerken. |
| `.counter` zeigt absurden Wert | Egal — Skript nimmt das Maximum aus Counter und realen Tickets. Optional auf die höchste vergebene Nummer setzen. |
| Globaler Setup bricht mit Fetch-Fehler ab | Repo lokal auschecken oder `AISKILLSET_RAW_BASE` auf eine erreichbare Quelle setzen. |
| Hook tut gar nichts, keine Meldung | `<projekt>/scripts/tickets.sh` fehlt — der Hook ist nur ein Adapter und steigt dann wortlos aus. `bash scripts/check_project_drift.sh <projekt>` zeigt es, `init_tickets.sh` rüstet es nach. |
| `tickets.sh new` sagt „Projekt-Prefix nicht ermittelbar" | In `tickets/PROTOCOL.md` steht noch der `{PRJ}`-Platzhalter. `bash scripts/init_tickets.sh <projekt> PREFIX` ersetzt ihn. |

---

## 10. Designentscheidungen in Kürze

- **Dateien statt DB:** diffbar, git-mergebar, ohne Tooling lesbar, agent-agnostisch.
- **Ordner = Status:** der Status ist auf einen Blick sichtbar (`ls tickets/open`),
  ohne jede Datei zu öffnen.
- **Frontmatter ist die Wahrheit, der Hook nur die Projektion:** man editiert ein
  Feld, nicht den Dateipfad — das ist weniger fehleranfällig und für Agenten leichter.
- **Counter als Cache, nicht als Autorität:** verhindert, dass ein verlorener/falscher
  Zähler das System dauerhaft beschädigt.
