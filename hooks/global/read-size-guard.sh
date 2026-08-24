#!/bin/bash
# PreToolUse Read: bremst Voll-Reads, die zu viel Kontext ins Fenster kippen.
#
# Hintergrund: Die Schwelle hing bis IZG-T-153 an Zeilen. Zeilen sind ein schlechter
# Tokenproxy - dichter Python-Code kostet ~10 Tokens/Zeile, lockeres YAML/Markdown
# ein Vielfaches weniger. Gemessen 16.08.2026: drei Dateien unter der alten
# 600-Zeilen-Sperre lagen trotzdem bei 2.100-3.100 Tokens. Seither schaetzt der Guard
# Tokens ueber die Dateigroesse (4 Zeichen/Token, Faktor aus analyze_transcript.py).
#
# Verhalten:
#   .jsonl/.log        -> harte Sperre (Transcripts, Logs)
#   offset oder limit  -> immer durchlassen, der Read ist bereits begrenzt
#   > WARN  (1000 Tok) -> Hinweis via additionalContext
#   > MAX   (2500 Tok) -> deny mit Verweis auf Grep / offset/limit
#
# Schwellen: READ_SIZE_GUARD_WARN_TOKENS (Default 1000),
#            READ_SIZE_GUARD_MAX_TOKENS  (Default 2500).
# Bestand:   READ_SIZE_GUARD_WARN / READ_SIZE_GUARD_MAX wirken weiter als
#            Zeilenschwellen, falls gesetzt - sonst braechen alte Setzungen still.
# Ventil:    READ_SIZE_GUARD_OFF=1 schaltet die Groessenpruefung ab.
# Muster analog zu FILE_DUMP_GUARD_MAX_LINES in file-dump-guard.sh.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  exit 0
fi

# .jsonl und .log Dateien hart blockieren (Transcripts, Logs) - vom Ventil unberuehrt
if echo "$FILE" | grep -qE '\.(jsonl|log)$'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Datei-Typ .jsonl/.log blockiert (zu gross, meist Transcripts). Nutze Grep mit spezifischem Pattern statt Read."
    }
  }'
  exit 0
fi

# Bilder/PDF/Binaerformate durchlassen: Read rendert sie als Bild bzw. ueber pages,
# die Byte-Groesse sagt dort nichts ueber die Kontextlast - offset/limit hilft nicht.
if echo "$FILE" | grep -qiE '\.(png|jpe?g|webp|gif|bmp|ico|pdf|ipynb)$'; then
  exit 0
fi

# Ausweg-Ventil: ganze Datei wird wirklich gebraucht (z.B. Refactoring ueber ein Modul)
if [ "$READ_SIZE_GUARD_OFF" = "1" ]; then
  exit 0
fi

# Teil-Reads nie behindern - genau die Loesung, die der Guard erzwingen soll
BOUNDED=$(echo "$INPUT" | jq -r 'if (.tool_input.offset // null) != null or (.tool_input.limit // null) != null then "1" else "0" end')
if [ "$BOUNDED" = "1" ]; then
  exit 0
fi

CHARS_PER_TOKEN=4
WARN_TOK="${READ_SIZE_GUARD_WARN_TOKENS:-1000}"
MAX_TOK="${READ_SIZE_GUARD_MAX_TOKENS:-2500}"

BYTES=$(wc -c < "$FILE" 2>/dev/null || echo 0)
TOKENS=$(( BYTES / CHARS_PER_TOKEN ))

NAME=$(basename "$FILE")
HINT="Nutze Grep mit Pattern, um die Stelle zu finden, oder Read mit offset/limit auf den relevanten Abschnitt. Wird die ganze Datei wirklich gebraucht: READ_SIZE_GUARD_OFF=1 setzen."

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

hint() {
  jq -n --arg msg "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $msg
    }
  }'
  exit 0
}

# Bestandsschwellen in Zeilen: nur pruefen, wenn jemand sie ausdruecklich gesetzt hat
LINES=0
if [ -n "${READ_SIZE_GUARD_WARN:-}" ] || [ -n "${READ_SIZE_GUARD_MAX:-}" ]; then
  LINES=$(wc -l < "$FILE" 2>/dev/null || echo 0)
fi

if [ -n "${READ_SIZE_GUARD_MAX:-}" ] && [ "$LINES" -gt "$READ_SIZE_GUARD_MAX" ]; then
  deny "Voll-Read von $NAME ($LINES Zeilen) blockiert - ueber der gesetzten Zeilenschwelle READ_SIZE_GUARD_MAX=$READ_SIZE_GUARD_MAX. $HINT"
fi

if [ "$TOKENS" -gt "$MAX_TOK" ]; then
  deny "Voll-Read von $NAME kostet geschaetzt $TOKENS Tokens - blockiert, ab $MAX_TOK Tokens kippt das zu viel Kontextlast ins Fenster, die jeder Folge-Turn mitbezahlt. $HINT"
fi

if [ -n "${READ_SIZE_GUARD_WARN:-}" ] && [ "$LINES" -gt "$READ_SIZE_GUARD_WARN" ]; then
  hint "ACHTUNG: $NAME hat $LINES Zeilen - ueber der gesetzten Zeilenschwelle READ_SIZE_GUARD_WARN=$READ_SIZE_GUARD_WARN. Besser: Read mit offset/limit auf den relevanten Abschnitt, oder Grep mit Pattern."
fi

if [ "$TOKENS" -gt "$WARN_TOK" ]; then
  hint "ACHTUNG: Voll-Read von $NAME kostet geschaetzt $TOKENS Tokens. Ab $WARN_TOK Tokens verlangt die CLAUDE.md-Regel einen Teil-Read: Read mit offset/limit auf den relevanten Abschnitt, oder Grep mit Pattern."
fi

exit 0
