"""Dünner REST-Client für die AgentMail-API (https://api.agentmail.to/v0).

Deckt Inboxes, Messages, Threads und Drafts ab. Kein Webhook-Empfang, kein
Draft-Review-Flow - siehe SKILL.md für den Scope.
"""

from __future__ import annotations

import os

import requests

from redact import Redactor

BASE_URL = "https://api.agentmail.to/v0"


class AgentMailClient:
    """Client für die AgentMail-API, eine gemeinsame Inbox pro Account.

    Redaction: Antworten aus Lese-Endpunkten (list_messages, list_threads,
    list_drafts, get_draft) werden vor der Rückgabe von OWNER_NAME/OWNER_EMAILS
    (aus der env, siehe env.example.txt) befreit. Damit sieht der Agent nie den
    echten Namen/die echte Adresse des Inbox-Besitzers, egal in welcher Mail
    sie auftauchen (Anrede, Signatur, Adressfelder). Siehe SKILL.md.
    """

    def __init__(self, api_key: str | None = None, inbox: str | None = None) -> None:
        self.api_key = api_key or os.environ["AGENTMAIL_API_KEY"]
        self.inbox = inbox or os.environ["AGENTMAIL_INBOX"]
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"
        self._redact = Redactor()

    def _url(self, path: str) -> str:
        return f"{BASE_URL}/inboxes/{self.inbox}{path}"

    def list_inboxes(self, limit: int | None = None, page_token: str | None = None) -> dict:
        params = {"limit": limit, "page_token": page_token}
        resp = self._session.get(f"{BASE_URL}/inboxes", params=_clean(params))
        resp.raise_for_status()
        return resp.json()

    def list_messages(
        self,
        labels: list[str] | None = None,
        subject: str | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> dict:
        params = {"labels": labels, "subject": subject, "limit": limit, "page_token": page_token}
        resp = self._session.get(self._url("/messages"), params=_clean(params))
        resp.raise_for_status()
        return self._redact(resp.json())

    def list_threads(
        self,
        subject: str | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> dict:
        params = {"subject": subject, "limit": limit, "page_token": page_token}
        resp = self._session.get(self._url("/threads"), params=_clean(params))
        resp.raise_for_status()
        return self._redact(resp.json())

    def send_message(
        self,
        to: list[str],
        subject: str,
        text: str | None = None,
        html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> dict:
        body = _clean({"to": to, "cc": cc, "bcc": bcc, "subject": subject, "text": text, "html": html})
        resp = self._session.post(self._url("/messages/send"), json=body)
        resp.raise_for_status()
        return resp.json()

    def create_draft(
        self,
        to: list[str],
        subject: str,
        text: str | None = None,
        html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> dict:
        body = _clean({"to": to, "cc": cc, "bcc": bcc, "subject": subject, "text": text, "html": html})
        resp = self._session.post(self._url("/drafts"), json=body)
        resp.raise_for_status()
        return resp.json()

    def list_drafts(
        self,
        labels: list[str] | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> dict:
        params = {"labels": labels, "limit": limit, "page_token": page_token}
        resp = self._session.get(self._url("/drafts"), params=_clean(params))
        resp.raise_for_status()
        return self._redact(resp.json())

    def get_draft(self, draft_id: str) -> dict:
        resp = self._session.get(self._url(f"/drafts/{draft_id}"))
        resp.raise_for_status()
        return self._redact(resp.json())

    def delete_draft(self, draft_id: str) -> None:
        resp = self._session.delete(self._url(f"/drafts/{draft_id}"))
        resp.raise_for_status()

    def send_draft(self, draft_id: str) -> dict:
        resp = self._session.post(self._url(f"/drafts/{draft_id}/send"), json={})
        resp.raise_for_status()
        return resp.json()

    def add_labels(self, message_id: str, add: list[str]) -> dict:
        resp = self._session.patch(self._url(f"/messages/{message_id}"), json={"add_labels": add})
        resp.raise_for_status()
        return resp.json()

    def remove_labels(self, message_id: str, remove: list[str]) -> dict:
        resp = self._session.patch(self._url(f"/messages/{message_id}"), json={"remove_labels": remove})
        resp.raise_for_status()
        return resp.json()


def _clean(params: dict) -> dict:
    return {k: v for k, v in params.items() if v is not None}
