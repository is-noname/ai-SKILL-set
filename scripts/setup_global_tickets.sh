#!/usr/bin/env bash
# Rückwärtskompatibler Alias. Der Inhalt lebt in setup_global_conventions.sh (deployt
# mehr als nur Tickets: doc-ids, project-identifier, Hook, Konfig-Patch). Bestehende
# Aufrufe/Referenzen auf diesen Namen funktionieren weiter.
#
# Bitte neu auf setup_global_conventions.sh umstellen.
exec bash "$(dirname "$0")/setup_global_conventions.sh" "$@"
