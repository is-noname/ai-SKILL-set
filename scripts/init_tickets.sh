#!/usr/bin/env bash
# Bootstraps tickets/ folder structure in the given directory (default: current dir).
# Idempotent: kann auf bestehende Projekte erneut angewendet werden, um Counter und
# next_ticket_id.sh nachzurüsten, ohne vorhandene Tickets/PROTOCOL.md zu überschreiben.
# For global agent setup (one-time, per machine) use: bash scripts/setup_global_conventions.sh
# Usage: bash scripts/init_tickets.sh [ziel-pfad] [KUERZEL]
#   KUERZEL (optional): 2-6 Grossbuchstaben. Wird in tickets/PROTOCOL.md als
#   projekt-lokale Laufzeit-Quelle verankert ({PRJ}-Platzhalter wird ersetzt).
#   Fehlt das Argument: bei TTY interaktive Nachfrage, sonst Platzhalter belassen
#   (kein Abbruch). Registry project-identifier.md wird bewusst NICHT angefasst
#   (agent-neutral; siehe IZG-T-045).
TARGET="${1:-.}"

# Projekt-Kuerzel bestimmen: Argument > interaktiv (nur bei TTY) > leer (Platzhalter).
PRJ="$(printf '%s' "${2:-}" | tr '[:lower:]' '[:upper:]')"
if [ -z "$PRJ" ] && [ -t 0 ]; then
  printf 'Projekt-Kuerzel (2-6 Grossbuchstaben, Enter = spaeter eintragen): ' > /dev/tty
  read -r _ans < /dev/tty || _ans=""
  PRJ="$(printf '%s' "$_ans" | tr '[:lower:]' '[:upper:]')"
fi
if [ -n "$PRJ" ] && ! printf '%s' "$PRJ" | grep -qE '^[A-Z]{2,6}$'; then
  echo "Warnung: Kuerzel '$PRJ' ungueltig (erwartet 2-6 Grossbuchstaben). Ignoriert, Platzhalter {PRJ} bleibt." >&2
  PRJ=""
fi

mkdir -p "$TARGET/tickets/open" \
         "$TARGET/tickets/in-progress" \
         "$TARGET/tickets/blocked" \
         "$TARGET/tickets/done"

# Counter nur anlegen wenn fehlend. Startwert 0 genügt — next_ticket_id.sh ist
# selbstheilend und nimmt ohnehin das Maximum aus Counter und realen Tickets.
if [ ! -f "$TARGET/tickets/.counter" ]; then
  echo "0" > "$TARGET/tickets/.counter"
fi

if [ ! -f "$TARGET/tickets/PROTOCOL.md" ]; then
  cat > "$TARGET/tickets/PROTOCOL.md" << 'EOF'
# Tickets

Vollständige Konvention: `tickets.md` im globalen Verzeichnis deines AI-Agenten.

## Lookup-Reihenfolge
1. `in-progress/` — läuft noch was?
2. `open/` — nächste Arbeit
3. `blocked/` — nur wenn Blocker gezielt gelöst werden soll

## Dateiname
`{PRJ}-T-{NNN}_{kurz-beschreibung}.md`
Projekt-Kürzel aus `doc-ids.md` im globalen Agent-Verzeichnis.

## Ticket-ID vergeben
```bash
bash scripts/next_ticket_id.sh {PRJ}
```

## Statuswechsel
`status:`-Feld im Frontmatter ändern — Hook verschiebt die Datei automatisch.
Verlaufseintrag pflegen: wann, warum, was erledigt/offen.
EOF
fi

# Kuerzel in PROTOCOL.md verankern: {PRJ}-Platzhalter durch das echte Kuerzel
# ersetzen. Greift bei frisch erstellter UND bestehender PROTOCOL.md (Nachruesten),
# solange dort noch Platzhalter stehen. PRJ ist auf [A-Z]{2,6} validiert -> sed-sicher.
if [ -n "$PRJ" ] && [ -f "$TARGET/tickets/PROTOCOL.md" ]; then
  sed -i "s/{PRJ}/$PRJ/g" "$TARGET/tickets/PROTOCOL.md"
fi

mkdir -p "$TARGET/scripts"

# next_ticket_id.sh immer (neu) schreiben, damit Bestandsprojekte die aktuelle
# selbstheilende Logik bekommen.
cat > "$TARGET/scripts/next_ticket_id.sh" << 'EOF'
#!/usr/bin/env bash
# Gibt die nächste Ticket-ID aus und aktualisiert den Zähler.
# Selbstheilend: nimmt das Maximum aus dem Zähler UND den bereits existierenden
# Tickets dieses Präfixes (über alle Status-Ordner). Damit gibt es genau eine
# Quelle der Wahrheit — egal ob der Counter fehlt, driftet oder das Projekt
# nachträglich gebootstrappt wurde.
# Usage: bash scripts/next_ticket_id.sh IZG
set -euo pipefail
PREFIX="${1:-PRJ}"
TICKETS_DIR="$(cd "$(dirname "$0")/.." && pwd)/tickets"
COUNTER_FILE="$TICKETS_DIR/.counter"

if [ ! -d "$TICKETS_DIR" ]; then
  echo "Fehler: $TICKETS_DIR nicht gefunden. init_tickets.sh ausführen." >&2
  exit 1
fi

# Atomares Increment: exklusiver Lock serialisiert Lesen-Rechnen-Schreiben.
# Ohne das bekämen zwei gleichzeitig laufende Agenten (Claude/Gemini/Codex)
# dieselbe ID. flock hält den Lock über fd 9 bis Skriptende. Fehlt flock,
# läuft es ohne Lock weiter (selbstheilende max_existing-Logik fängt Drift ab).
if command -v flock >/dev/null 2>&1; then
  exec 9>"$COUNTER_FILE.lock"
  flock 9
fi

# Zählerwert (0 wenn Datei fehlt oder nicht-numerisch; Nicht-Ziffern werden
# entfernt, daher kein Crash bei kaputtem Counter)
counter=0
if [ -f "$COUNTER_FILE" ]; then
  c="$(tr -dc '0-9' < "$COUNTER_FILE")"
  [ -n "$c" ] && counter=$((10#$c))
fi

# Höchste bereits vergebene Nummer für dieses Präfix über alle Ordner.
# || true: leeres grep liefert Exit 1 und würde unter pipefail das Skript beim
# allerersten Ticket (noch keine Treffer) abbrechen.
max_existing="$(grep -rhoE "^id: ${PREFIX}-T-[0-9]+" "$TICKETS_DIR" 2>/dev/null \
  | grep -oE '[0-9]+$' | sort -n | tail -1 || true)"
max_existing=$((10#${max_existing:-0}))

floor=$counter
[ "$max_existing" -gt "$floor" ] && floor=$max_existing

next=$((floor + 1))
echo "$next" > "$COUNTER_FILE"

printf "%s-T-%03d\n" "$PREFIX" "$next"
EOF

chmod +x "$TARGET/scripts/next_ticket_id.sh"

SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
DEST="$(cd "$TARGET/scripts" && pwd)/init_tickets.sh"
if [ "$SELF" != "$DEST" ]; then
  cp "$0" "$TARGET/scripts/init_tickets.sh"
  chmod +x "$TARGET/scripts/init_tickets.sh"
fi

if [ -n "$PRJ" ]; then
  echo "tickets/ ready in $TARGET (Kuerzel $PRJ in PROTOCOL.md verankert, scripts deployed)"
else
  echo "tickets/ ready in $TARGET (Kuerzel nicht gesetzt, Platzhalter {PRJ} bleibt, scripts deployed)"
  echo "Hinweis: Kuerzel nachtragen via 'bash scripts/init_tickets.sh $TARGET KUERZEL' oder {PRJ} in tickets/PROTOCOL.md manuell ersetzen." >&2
fi
