#!/usr/bin/env bash
# Rückwärtskompatibler Alias. Der Inhalt zog nach setup_global.sh um (deployt mehr
# als nur Tickets: doc-ids, project-identifier, Hook, Konfig-Patch). Bestehende
# Aufrufe/Referenzen auf diesen Namen funktionieren weiter.
#
# Bitte neu auf setup_global.sh umstellen.
exec bash "$(dirname "$0")/setup_global.sh" "$@"
