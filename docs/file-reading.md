# Datei-Handling: Lesen, Suchen, Auflisten

Konvention fuer alle Agents. Ziel: kein unnoetiger Dateiinhalt im Kontextfenster —
jeder Folge-Turn bezahlt ihn mit.

Gilt unabhaengig davon, ob Guard-Hooks aktiv sind. Die Hooks (siehe unten) sind nur
das Netz, nicht die Regel: sie laufen nur in `~/.claude`, nicht bei Vibe/Codex/Gemini,
und nicht in Sessions ohne globale Agent-Konfig.

## Regeln

| Aufgabe | So | Nicht so |
|---------|----|----------|
| Datei lesen | `Read` (bzw. das Lese-Tool des Agents) | `cat`, `less`, `nl`, `head`, `tail`, `sed` als Voll-Dump |
| Grosse Datei lesen (ab ~4 KB / ~1.000 Tokens) | `Read` mit `offset`/`limit` auf den relevanten Abschnitt, oder `Grep` mit Pattern | ganze Datei ins Fenster kippen |
| Inhalt suchen | `Grep` | `grep -rn` ueber die Shell |
| Dateien finden | `Glob` | `find` ohne Eingrenzung |
| Verzeichnis ansehen | kurze Listings direkt, sonst filtern | `ls -R`, `ls -la` auf grosse Baeume |

Wenn doch die Shell noetig ist:

- `find` immer eingrenzen (`-name`, `-maxdepth`) oder nachfiltern (`| head`, `| grep`).
- Shell-Ausgabe = gefiltertes Ergebnis (`| grep`, `| wc -l`, `| head`), nie Dateiinhalt.
- Ein bewusst begrenzter Ausschnitt (`sed -n '120,180p'`, `head -50`) ist erlaubt —
  der Voll-Dump ist das Problem, nicht das Kommando.

Nicht durchsuchen: `.git/`, `__pycache__/`, `node_modules/`, `.idea/`, `.vscode/`,
`.gemini/`.

## Warum

Ein Voll-Read von 2.500 Tokens kostet nicht 2.500 Tokens, sondern 2.500 Tokens **mal
jedem weiteren Turn der Session**. Gefiltertes Lesen ist deshalb kein Stil-, sondern
ein Kostenthema — und je voller das Fenster, desto schlechter die Antwortqualitaet.

## Hooks (nur Claude, `~/.claude/hooks/`)

Absicherung derselben Regel, deployt via `setup_global_hooks.sh`. Details:
`hooks/README.md` im ai-SKILL-set-Repo.

| Hook | Blockt | Ventil |
|------|--------|--------|
| `read-size-guard.sh` | `Read` auf `.jsonl`/`.log` hart; Voll-Reads ab ~2.500 geschaetzten Tokens (Warnung ab ~1.000) | `READ_SIZE_GUARD_OFF=1` |
| `read-dedupe-guard.sh` | erneuten `Read` derselben, unveraenderten Datei innerhalb des Kontextfensters | `READ_DEDUPE_GUARD_OFF=1` |
| `file-dump-guard.sh` | Bash-Voll-Dumps von Dateien > 300 Zeilen und ungefiltertes `find`/lange Listings | `FILE_DUMP_GUARD_MAX_LINES=<n>` |

Ein Ventil nur setzen, wenn die ganze Datei wirklich gebraucht wird — und das im
Turn begruenden, nicht stillschweigend.

## Wenn ein Hook blockt

Die Deny-Meldung nennt den Grund und den Ausweg. Erwartetes Verhalten:

1. Meldung lesen, den vorgeschlagenen Weg gehen (`offset`/`limit`, `Grep`, Filter).
2. Nicht dasselbe Kommando wiederholen und nicht auf ein anderes Dump-Kommando
   ausweichen (`cat` → `sed` → `nl`), um den Guard zu umgehen.
3. Bleibt es blockiert und ist der Voll-Read wirklich noetig: dem Nutzer sagen,
   warum — dann das Ventil setzen.

## Im Auto-/Genehmigt-Modus

Die Regel gilt unveraendert, auch wenn Tool-Calls nicht einzeln bestaetigt werden.
Ein genehmigter Plan genehmigt die Aufgabe, nicht das ungefilterte Lesen.
