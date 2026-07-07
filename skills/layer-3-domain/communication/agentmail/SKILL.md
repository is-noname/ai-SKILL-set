---
name: agentmail
description: "REST-Client für die AgentMail-API (agentmail.to) — Postfach, Nachrichten und Drafts per Python ansprechen, inkl. Webhook-Empfang und CLI-Review-Flow für Drafts. Nutzen wenn ein Agent E-Mails über AgentMail lesen, ein Draft anlegen, Labels auf Nachrichten setzen oder eingehende Mails per Webhook verarbeiten soll. Kein autonomes Senden — Drafts durchlaufen `draft_review.py` als Human-in-the-loop-Review."
layer: 3
dependencies: []
---

# AgentMail

Dünner REST-Wrapper um die AgentMail-API (`api.agentmail.to/v0`). Deckt Inboxes,
Messages, Threads, Drafts, Webhook-Empfang für eingehende Mails und den
CLI-Review-Flow für Drafts ab.

## Setup

1. API-Key von agentmail.to als `AGENTMAIL_API_KEY` in die Projekt-`.env` legen.
2. Inbox-Adresse als `AGENTMAIL_INBOX` in dieselbe `.env` (z.B. `dein-agent@agentmail.to`).
3. `env.example.txt` in diesem Skill zeigt die erwarteten Variablen.

## Nutzung

```python
from scripts.agentmail_client import AgentMailClient

client = AgentMailClient()  # liest AGENTMAIL_API_KEY / AGENTMAIL_INBOX aus env

client.list_messages(labels=["projekt-x"])
client.create_draft(to=["someone@example.com"], subject="Betreff", text="Inhalt")
client.list_drafts(labels=["projekt-x"])
client.get_draft(draft_id="...")
client.send_draft(draft_id="...")
client.delete_draft(draft_id="...")
client.add_labels(message_id="...", add=["projekt-x", "erledigt"])
```

Alle Methoden werfen bei HTTP-Fehlern `requests.HTTPError` — kein Silent-Fail.
Endpoints/Felder gegen das offizielle OpenAPI-Spec verifiziert
(`github.com/agentmail-to/agentmail-docs`, `current-openapi.json`).

## Label-Konvention (eine gemeinsame Inbox, mehrere Projekte)

Da alle Projekte dieselbe Inbox (`AGENTMAIL_INBOX`) teilen (Free-Tier-Limit), wird
pro Projekt statt einer eigenen Adresse ein Label verwendet:

- Label-Slug = Projekt-Prefix aus `project-identifier.md`, lowercase (z.B. `izg`, `stk`, `wde`).
- Beim Erstellen eines Drafts/Threads für ein Projekt immer dieses Label setzen
  (`add_labels`), damit eingehende Antworten dem Projekt zuordenbar bleiben.
- Zusätzliche Labels (z.B. `erledigt`, `dringend`) sind frei, dürfen den
  Projekt-Slug aber nicht überschreiben (immer per `add`, nie per Replace).

## Webhook-Empfang

AgentMail liefert Webhooks über **Svix** aus (HMAC-SHA256, Standard-Webhooks-Schema).
`scripts/webhook_verify.py` implementiert die Verifizierung selbst (stdlib `hmac`/
`hashlib`/`base64`) statt der `svix`-Bibliothek, damit `requests` die einzige
Fremdabhängigkeit des Skills bleibt. Gegen einen offiziellen Svix-Testvektor
verifiziert.

`scripts/webhook_receiver.py` ist ein minimaler Empfänger auf Basis von
`http.server` (kein Flask/FastAPI nötig):

```bash
cd scripts
AGENTMAIL_WEBHOOK_SECRET=whsec_... AGENTMAIL_WEBHOOK_PORT=8787 python3 webhook_receiver.py
```

Ablauf pro Request:
1. Signatur via `svix-id` / `svix-timestamp` / `svix-signature` prüfen
   (Toleranz 5 Minuten gegen Replay). Ungültige Requests → `401`, kein Parsing.
2. Bei `message.received*`-Events: `thread.labels` gegen die Projekt-Prefixe aus
   `project-identifier.md` abgleichen (`scripts/project_routing.py`) und das
   Ergebnis loggen.

**Grenze der Label-Routing-Strategie:** Funktioniert nur für Antworten in einem
Thread, der bereits ein Projekt-Label trägt (weil der Agent es beim Draft/Send
gesetzt hat, siehe Label-Konvention oben). Eine komplett neue eingehende Mail
(kein bestehender Thread) hat noch kein Label — landet als `unassigned` im Log.
Zuordnung so einer Mail zu einem Projekt ist bewusst nicht automatisiert
(Scope-Grenze dieses Tickets).

### Lokales Entwicklungs-Setup (ngrok)

AgentMail braucht eine öffentlich erreichbare URL, auch im Free-Tier lokal nur
über einen Tunnel möglich:

```bash
# Terminal 1: Receiver starten
cd scripts && AGENTMAIL_WEBHOOK_SECRET=whsec_... python3 webhook_receiver.py

# Terminal 2: Tunnel aufbauen
ngrok http 8787
```

Die von ngrok ausgegebene `https://...ngrok-free.app`-URL + `/webhook` im
AgentMail-Dashboard als Webhook-Endpoint eintragen, gewünschte Events
abonnieren (mind. `message.received`), das dort erzeugte Signing-Secret
(`whsec_...`) in die `.env` als `AGENTMAIL_WEBHOOK_SECRET` übernehmen.
Bei jedem Neustart von ngrok ändert sich die URL (Free-Tier) — im Dashboard
nachpflegen.

## Draft-Review-Flow (Human-in-the-loop)

`create_draft` legt eine Mail nur als Draft an — versendet wird ausschließlich
über den Review-CLI `scripts/draft_review.py`:

```bash
cd scripts
python3 draft_review.py list                  # offene Drafts auflisten
python3 draft_review.py list --labels izg     # nach Projekt-Label filtern
python3 draft_review.py show <draft_id>       # Inhalt vollständig anzeigen
python3 draft_review.py confirm <draft_id>    # Rückfrage, dann Versand
python3 draft_review.py reject <draft_id>     # Rückfrage, dann Löschen (kein Versand)
```

`confirm`/`reject` fragen interaktiv nach (`[y/N]`), außer `--yes` ist gesetzt.
Kein Draft wird ohne diese explizite Bestätigung versendet oder gelöscht.

## Redaction personenbezogener Daten

`scripts/redact.py` entfernt Name/E-Mail-Adresse des Inbox-Besitzers aus allem,
was der Client zurückgibt (`list_messages`, `list_threads`, `list_drafts`,
`get_draft`) sowie aus dem Webhook-Log (`webhook_receiver.py`) — Anrede,
Signatur und Adressfelder eingeschlossen.

Konfiguration ausschließlich über `.env` (`OWNER_NAME`, `OWNER_EMAILS`,
kommagetrennte Varianten, siehe `env.example.txt`). Diese Datei direkt im
Editor pflegen, nicht im Chat mit dem Agenten nennen — der Agent liest die
Werte nie, er verifiziert höchstens (per Skript) ob die Felder gesetzt sind,
nie deren Inhalt. Redaction ist reiner String-Ersatz auf allen Textfeldern der
JSON-Antwort — keine Named-Entity-Erkennung. Trifft nur exakt eingetragene
Varianten; wer als "Max M." statt "Max Mustermann" unterschreibt, entkommt der
Regel, wenn diese Variante nicht in `OWNER_NAME` steht.

## Offene Punkte (bewusst nicht Teil dieses Skills)

- Routing komplett neuer (nicht Reply-)Mails ohne Projekt-Label ist ungelöst,
  siehe "Grenze der Label-Routing-Strategie" oben.
- Rate-Limits und Custom-Domain-Verfügbarkeit im Free-Tier weiterhin ungeklärt.
