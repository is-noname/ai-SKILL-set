#!/bin/bash
# PreToolUse Read: erzwingt die 300-Zeilen-Regel der globalen CLAUDE.md.
#
# Hintergrund: Voll-Reads von Dateien zwischen 300 und 1.000 Zeilen liefen bisher
# ungebremst durch (alte Schwelle: Hinweis ab 1.000, nie blockiert). Token-Review
# 12.08.2026: 98 Voll-Reads = 37,3 Mio. Turn-Kosten, 12,2 % aller Cache-Treffer.
#
# Verhalten:
#   .jsonl/.log        -> harte Sperre (Transcripts, Logs)
#   offset oder limit  -> immer durchlassen, der Read ist bereits begrenzt
#   > WARN  (300)      -> Hinweis via additionalContext
#   > MAX   (600)      -> deny mit Verweis auf Grep / offset/limit
#
# Schwellen: READ_SIZE_GUARD_WARN (Default 300), READ_SIZE_GUARD_MAX (Default 600).
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

# Ausweg-Ventil: ganze Datei wird wirklich gebraucht (z.B. Refactoring ueber ein Modul)
if [ "$READ_SIZE_GUARD_OFF" = "1" ]; then
  exit 0
fi

# Teil-Reads nie behindern - genau die Loesung, die der Guard erzwingen soll
BOUNDED=$(echo "$INPUT" | jq -r 'if (.tool_input.offset // null) != null or (.tool_input.limit // null) != null then "1" else "0" end')
if [ "$BOUNDED" = "1" ]; then
  exit 0
fi

WARN="${READ_SIZE_GUARD_WARN:-300}"
MAX="${READ_SIZE_GUARD_MAX:-600}"

LINES=$(wc -l < "$FILE" 2>/dev/null || echo 0)

if [ "$LINES" -gt "$MAX" ]; then
  jq -n --arg lines "$LINES" --arg file "$(basename "$FILE")" --arg max "$MAX" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Voll-Read von " + $file + " (" + $lines + " Zeilen) blockiert - ab " + $max + " Zeilen kippt das zu viel Kontextlast ins Fenster, die jeder Folge-Turn mitbezahlt. Nutze Grep mit Pattern, um die Stelle zu finden, oder Read mit offset/limit auf den relevanten Abschnitt. Wird die ganze Datei wirklich gebraucht: READ_SIZE_GUARD_OFF=1 setzen.")
    }
  }'
  exit 0
fi

if [ "$LINES" -gt "$WARN" ]; then
  jq -n --arg lines "$LINES" --arg file "$(basename "$FILE")" --arg warn "$WARN" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: ("ACHTUNG: " + $file + " hat " + $lines + " Zeilen. Die CLAUDE.md-Regel verlangt ab " + $warn + " Zeilen einen Teil-Read: Read mit offset/limit auf den relevanten Abschnitt, oder Grep mit Pattern.")
    }
  }'
fi

exit 0
