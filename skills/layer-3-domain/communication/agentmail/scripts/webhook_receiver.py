"""Lokaler Webhook-Empfänger für AgentMail-Events (stdlib-only, kein Flask).

Nimmt POST-Requests unter /webhook entgegen, verifiziert die Svix-Signatur
und ordnet `message.received`-Events per Thread-Label einem Projekt zu.
Draft-Erstellung/Review als Reaktion auf eingehende Mails ist NICHT Teil
dieses Skripts - siehe IZG-T-059.

Start:
    python3 webhook_receiver.py

Benötigt AGENTMAIL_WEBHOOK_SECRET (Format `whsec_...`) in der env, siehe
env.example.txt. Für lokale Entwicklung mit ngrok siehe SKILL.md.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from project_routing import load_known_slugs, route_by_labels
from webhook_verify import WebhookVerificationError, verify_signature

DEFAULT_PORT = 8787


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler-API)
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)

        try:
            secret = os.environ["AGENTMAIL_WEBHOOK_SECRET"]
            verify_signature(
                secret=secret,
                payload=payload,
                svix_id=self.headers.get("svix-id", ""),
                svix_timestamp=self.headers.get("svix-timestamp", ""),
                svix_signature=self.headers.get("svix-signature", ""),
            )
        except WebhookVerificationError as exc:
            print(f"[webhook] abgelehnt: {exc}", file=sys.stderr)
            self.send_response(401)
            self.end_headers()
            return

        event = json.loads(payload)
        self._handle_event(event)

        self.send_response(200)
        self.end_headers()

    def _handle_event(self, event: dict) -> None:
        event_type = event.get("event_type", "")
        if not event_type.startswith("message.received"):
            print(f"[webhook] Event ignoriert: {event_type}")
            return

        thread = event.get("thread", {})
        labels = thread.get("labels", [])
        known_slugs = load_known_slugs()
        project_slug = route_by_labels(labels, known_slugs)

        message = event.get("message", {})
        if project_slug is None:
            print(
                f"[webhook] {event_type}: kein Projekt-Label gefunden "
                f"(labels={labels!r}) - von {message.get('from')!r}, "
                f"Betreff {message.get('subject')!r} -> unassigned"
            )
        else:
            print(
                f"[webhook] {event_type}: Projekt '{known_slugs[project_slug]}' "
                f"(Label '{project_slug}') - von {message.get('from')!r}, "
                f"Betreff {message.get('subject')!r}"
            )

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # Standard-Logging von BaseHTTPRequestHandler unterdrücken, siehe print() oben


def main() -> None:
    port = int(os.environ.get("AGENTMAIL_WEBHOOK_PORT", DEFAULT_PORT))
    if "AGENTMAIL_WEBHOOK_SECRET" not in os.environ:
        raise SystemExit("AGENTMAIL_WEBHOOK_SECRET fehlt in der env - siehe env.example.txt")

    server = ThreadingHTTPServer(("127.0.0.1", port), WebhookHandler)
    print(f"[webhook] höre auf http://127.0.0.1:{port}/webhook")
    server.serve_forever()


if __name__ == "__main__":
    main()
