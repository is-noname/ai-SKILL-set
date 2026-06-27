#!/usr/bin/env bash
# Rückwärtskompatibler Alias. Umbenannt zu setup_global_conventions.sh, damit der
# Name die Domäne zeigt (Konventions-Bündel) und nicht mit setup_global_hooks.sh
# (Guard-Hook-Deployer) verwechselt wird. Bestehende Aufrufe/Referenzen auf diesen
# Namen funktionieren weiter.
#
# Bitte neu auf setup_global_conventions.sh umstellen.
exec bash "$(dirname "$0")/setup_global_conventions.sh" "$@"
