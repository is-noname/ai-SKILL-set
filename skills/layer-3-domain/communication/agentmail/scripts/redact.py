"""Entfernt Namen/Adressen des Inbox-Besitzers aus AgentMail-Daten.

Varianten kommen aus OWNER_NAME / OWNER_EMAILS in der env (siehe
env.example.txt) - dort direkt eingetragen, nie im Chat mit dem Agenten
genannt. So sieht der Agent die Klartext-Werte nie, auch nicht beim
Lesen von Nachrichten, Drafts oder Webhook-Events. Siehe SKILL.md
"Redaction personenbezogener Daten".
"""

from __future__ import annotations

import os
import re


def _patterns_from_env(var: str) -> list[re.Pattern]:
    raw = os.environ.get(var, "")
    terms = [t.strip() for t in raw.split(",") if t.strip()]
    return [re.compile(re.escape(t), re.IGNORECASE) for t in terms]


def _redact_value(value, patterns: list[re.Pattern], placeholder: str):
    if isinstance(value, str):
        for pat in patterns:
            value = pat.sub(placeholder, value)
        return value
    if isinstance(value, dict):
        return {k: _redact_value(v, patterns, placeholder) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v, patterns, placeholder) for v in value]
    return value


class Redactor:
    """Liest OWNER_NAME/OWNER_EMAILS einmalig aus der env und wendet sie an."""

    def __init__(self) -> None:
        self._email_patterns = _patterns_from_env("OWNER_EMAILS")
        self._name_patterns = _patterns_from_env("OWNER_NAME")

    def __call__(self, data):
        data = _redact_value(data, self._email_patterns, "[OWNER_EMAIL]")
        data = _redact_value(data, self._name_patterns, "[OWNER_NAME]")
        return data
