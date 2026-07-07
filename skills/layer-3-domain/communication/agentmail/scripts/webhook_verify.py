"""Signatur-Verifizierung für AgentMail-Webhooks (Svix-Standard, stdlib-only).

AgentMail versendet Webhooks über Svix. Statt der `svix`-Bibliothek nutzt dieses
Modul den offenen "Standard Webhooks"-Algorithmus direkt (HMAC-SHA256), um keine
zusätzliche Dependency einzuführen - der Skill bleibt bei `requests` als einziger
Fremdabhängigkeit.

Schema (siehe https://docs.agentmail.to/webhook-verification):
- Header `svix-id`, `svix-timestamp`, `svix-signature` (space-delimited `v1,<base64>`-Paare)
- Signierter Content: "{svix-id}.{svix-timestamp}.{raw_body}"
- Secret liegt als `whsec_<base64>` vor - Präfix abschneiden, Rest base64-dekodieren
- Timestamp-Toleranz: 5 Minuten (Replay-Schutz)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time


class WebhookVerificationError(Exception):
    """Signatur ungültig oder Timestamp außerhalb der Toleranz."""


def verify_signature(
    secret: str,
    payload: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
    tolerance_seconds: int = 300,
) -> None:
    """Wirft WebhookVerificationError bei ungültiger Signatur oder abgelaufenem Timestamp.

    Args:
        secret: Signing-Secret aus dem AgentMail-Dashboard (Format `whsec_...`).
        payload: Roher Request-Body (unverändert, vor jeglichem JSON-Parsing).
        svix_id: Wert des `svix-id`-Headers.
        svix_timestamp: Wert des `svix-timestamp`-Headers (Unix-Sekunden als String).
        svix_signature: Wert des `svix-signature`-Headers (`v1,<base64> v1,<base64> ...`).
        tolerance_seconds: Erlaubte Zeitabweichung, Default 5 Minuten (AgentMail-Default).
    """
    try:
        ts = int(svix_timestamp)
    except (TypeError, ValueError) as exc:
        raise WebhookVerificationError("svix-timestamp fehlt oder ist ungültig") from exc

    if abs(time.time() - ts) > tolerance_seconds:
        raise WebhookVerificationError("svix-timestamp außerhalb der Toleranz (Replay-Schutz)")

    if not secret.startswith("whsec_"):
        raise WebhookVerificationError("Secret hat nicht das erwartete Format 'whsec_...'")
    secret_bytes = base64.b64decode(secret[len("whsec_") :])

    signed_content = f"{svix_id}.{svix_timestamp}.".encode() + payload
    expected = base64.b64encode(
        hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
    ).decode()

    candidates = [part.split(",", 1)[1] for part in svix_signature.split(" ") if "," in part]
    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise WebhookVerificationError("Signatur stimmt mit keinem übermittelten Kandidaten überein")
