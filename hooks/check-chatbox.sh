#!/bin/bash
# GLOBAL: Agent Chatbox beim Session-Start pruefen
PROJECT_DIR=$(echo "$(cat)" | jq -r '.cwd')
CHATBOX_DIR="$PROJECT_DIR/agent_chatbox"

if [ ! -d "$CHATBOX_DIR" ]; then
  exit 0
fi

# Inbox pruefen
INBOX_COUNT=$(ls "$CHATBOX_DIR/claude/"*.md 2>/dev/null | wc -l)

# Offene Threads pruefen (wo [DONE:claude] fehlt)
OPEN_THREADS=0
for thread in "$CHATBOX_DIR/threads/"*.md; do
  [ -f "$thread" ] || continue
  if ! grep -q '\[DONE:claude\]' "$thread"; then
    OPEN_THREADS=$((OPEN_THREADS + 1))
  fi
done

# Board pruefen
BOARD_COUNT=$(ls "$CHATBOX_DIR/board/"*.md 2>/dev/null | wc -l)

OUTPUT=""
if [ "$INBOX_COUNT" -gt 0 ]; then
  OUTPUT="$OUTPUT\nINBOX: $INBOX_COUNT neue Nachricht(en) in agent_chatbox/claude/"
fi
if [ "$OPEN_THREADS" -gt 0 ]; then
  OUTPUT="$OUTPUT\nTHREADS: $OPEN_THREADS offene(r) Thread(s) ohne [DONE:claude]"
fi
if [ "$BOARD_COUNT" -gt 0 ]; then
  OUTPUT="$OUTPUT\nBOARD: $BOARD_COUNT Eintraege auf dem Board"
fi

if [ -n "$OUTPUT" ]; then
  echo -e "=== AGENT CHATBOX ===$OUTPUT"
else
  echo "Agent Chatbox: Keine neuen Nachrichten."
fi

exit 0
