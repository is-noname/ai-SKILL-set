# Messung: izg-improve-token-usage

Messaufbau fuer `izg-benchmark-actions`. Testaufgabe steht in [aufgabe.md](aufgabe.md) —
**nie umformulieren**, sonst sind alle frueheren Laeufe unvergleichbar (das Skript merkt
sich ihre Pruefsumme: `7c7adffb028e`).

Task-Kennung: `izg-improve-token-usage`
Laufdaten: `~/.local/share/izg-bench/`
Messplan: `~/.local/share/izg-bench/plans/izg-improve-token-usage.json`

## Varianten

| Variante | Umschaltung | Frage dahinter |
|---|---|---|
| `ohne-skill` | [setup-ohne-skill.sh](setup-ohne-skill.sh) | Lohnt sich der Skill ueberhaupt? |
| `mit-skill` | [setup-mit-skill.sh](setup-mit-skill.sh) | Basis fuer Optimierungen |
| `v<n>` | eigenes Setup, das die neue Fassung einspielt | Hat die Ueberarbeitung was gebracht? |

`setup-mit-skill.sh` entfernt beim Kopieren `disable-model-invocation: true`. Ohne das
zieht das Modell den Skill nicht, weil die Testaufgabe ihn (absichtlich) nicht nennt —
und man misst zweimal `ohne-skill`, ohne es zu merken.

## Bewertungskriterien

Vorab festgelegt, damit der Ertrag nicht nachtraeglich passend gemacht wird.

- **`ok`** — drei Kandidaten, jeder mit konkreter Stelle, einem Messwert aus den
  Transcripts und einem Aenderungsvorschlag. Nichts am Repo geaendert, kein Ticket.
- **`partial`** — weniger als drei Kandidaten, oder ein Kandidat ohne Messwert
  (Vermutung statt Beleg), oder ein Vorschlag fehlt.
- **`fail`** — keine Messung stattgefunden (rein statisch geraten), oder das Repo
  wurde veraendert.

Der HTML-Report des Skills zaehlt **nicht** zum Ertrag: die Testaufgabe stoppt davor,
damit beide Varianten dasselbe Artefakt liefern. Gemessen ist damit der analytische
Teil des Skills, nicht sein voller Ablauf.

## Naechste Runde

Immer **beide** Varianten der Runde frisch messen. Alte Zahlen sind kein Vergleichspunkt:
zwischen zwei Runden liegen Modellwechsel, neue Systemprompts und CLI-Versionen.

```bash
cd ../../izg-benchmark-actions   # Skript liegt dort

# 1. produktive Fassung erneut messen - die Basis dieser Runde
python3 scripts/bench.py run --task izg-improve-token-usage --variant mit-skill --repeat 3

# 2. ueberarbeitete Fassung
python3 scripts/bench.py run --task izg-improve-token-usage --variant v3 --repeat 3 \
  --setup "bash <pfad>/benchmark/setup-v3.sh"

# 3. jeden Lauf bewerten (Kriterien oben)
python3 scripts/bench.py judge --task izg-improve-token-usage --variant v3 --run 1 --outcome ok

# 4. Urteil - beide aus derselben Runde
python3 scripts/bench.py compare --task izg-improve-token-usage --baseline mit-skill
```

Testaufgabe, Projekt, Modell und Umschaltung kommen aus dem Messplan, deshalb die kurzen
Kommandos. Nach der letzten Messung `.claude/skills/izg-improve-token-usage` entfernen —
der Ausgangszustand des Repos hat den Skill dort nicht liegen.

`ohne-skill` gehoert **nicht** in eine Optimierungsrunde. Das ist eine eigene Frage und
wird nur gemessen, wenn sie gestellt wird.

## Ergebnisprotokoll

Eine Zeile je Variante und Runde. Urteile gelten nur innerhalb einer Runde; der Verlauf
darunter ist Beobachtung mit Datum, kein Beleg (`bench.py history --task izg-improve-token-usage`).

### Runde 2026-08-14 — Modell sonnet, CLI 2.1.232

| Variante | n | Gew. Tokens | Kosten $ | Turns | Cache | Ertrag | Urteil |
|---|---:|---:|---:|---:|---:|---|---|
| `mit-skill` | 1 | 49.080 | 0,19 | 4 | 83 % | ok | — |
| `ohne-skill` | 1 | 172.156 | 0,6071 | 17 | 94 % | ok | Basis |

**Kein Urteil — n < 3.** Probelauf, um den Messaufbau zu pruefen.

Beobachtung ohne Belegkraft: `mit-skill` bei rund einem Drittel der gewichteten Tokens.
Der Abstand kommt aus den Turns (4 gegen 17) — mit Skill genuegt ein Aufruf von
`analyze_transcript.py`, ohne Skill baut der Agent die Auswertung in 14 Bash-Aufrufen
selbst. Beide Varianten nannten unabhaengig voneinander dieselben drei Tokenfresser.
