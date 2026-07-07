"""CLI für den Human-in-the-loop-Review von AgentMail-Drafts.

Kein autonomes Senden: `create_draft` legt eine Mail nur als Draft an, dieses
Skript ist der einzige Weg, sie zu bestätigen (send) oder zu verwerfen
(delete). Beide Aktionen fragen interaktiv nach, außer `--yes` ist gesetzt.

Nutzung:
    python3 draft_review.py list
    python3 draft_review.py list --labels izg
    python3 draft_review.py show <draft_id>
    python3 draft_review.py confirm <draft_id>
    python3 draft_review.py reject <draft_id>
"""

from __future__ import annotations

import argparse
import sys

from agentmail_client import AgentMailClient


def cmd_list(client: AgentMailClient, args: argparse.Namespace) -> None:
    labels = args.labels.split(",") if args.labels else None
    result = client.list_drafts(labels=labels, limit=args.limit)
    drafts = result.get("drafts", [])
    if not drafts:
        print("Keine offenen Drafts.")
        return
    for draft in drafts:
        print(
            f"{draft['draft_id']}  to={draft.get('to')}  "
            f"subject={draft.get('subject')!r}  status={draft.get('send_status')}"
        )


def cmd_show(client: AgentMailClient, args: argparse.Namespace) -> None:
    draft = client.get_draft(args.draft_id)
    print(f"draft_id: {draft['draft_id']}")
    print(f"to:       {draft.get('to')}")
    print(f"cc:       {draft.get('cc')}")
    print(f"bcc:      {draft.get('bcc')}")
    print(f"subject:  {draft.get('subject')}")
    print(f"labels:   {draft.get('labels')}")
    print("--- text ---")
    print(draft.get("text") or "(kein text-Body)")


def cmd_confirm(client: AgentMailClient, args: argparse.Namespace) -> None:
    draft = client.get_draft(args.draft_id)
    print(f"Senden an {draft.get('to')} - Betreff {draft.get('subject')!r}")
    if not args.yes and not _confirm("Wirklich senden?"):
        print("Abgebrochen.")
        return
    result = client.send_draft(args.draft_id)
    print(f"Gesendet: message_id={result['message_id']} thread_id={result['thread_id']}")


def cmd_reject(client: AgentMailClient, args: argparse.Namespace) -> None:
    draft = client.get_draft(args.draft_id)
    print(f"Verwerfen: an {draft.get('to')} - Betreff {draft.get('subject')!r}")
    if not args.yes and not _confirm("Wirklich verwerfen (unwiderruflich)?"):
        print("Abgebrochen.")
        return
    client.delete_draft(args.draft_id)
    print("Draft gelöscht, kein Versand.")


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N] ").strip().lower() == "y"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Offene Drafts auflisten")
    p_list.add_argument("--labels", help="Kommagetrennte Labels zum Filtern")
    p_list.add_argument("--limit", type=int, default=None)
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Einen Draft im Detail anzeigen")
    p_show.add_argument("draft_id")
    p_show.set_defaults(func=cmd_show)

    p_confirm = sub.add_parser("confirm", help="Draft bestätigen und versenden")
    p_confirm.add_argument("draft_id")
    p_confirm.add_argument("--yes", action="store_true", help="Ohne Rückfrage senden")
    p_confirm.set_defaults(func=cmd_confirm)

    p_reject = sub.add_parser("reject", help="Draft ablehnen und löschen")
    p_reject.add_argument("draft_id")
    p_reject.add_argument("--yes", action="store_true", help="Ohne Rückfrage löschen")
    p_reject.set_defaults(func=cmd_reject)

    args = parser.parse_args()
    client = AgentMailClient()
    try:
        args.func(client, args)
    except Exception as exc:  # noqa: BLE001 - CLI-Fehlerausgabe, kein Re-raise nötig
        print(f"Fehler: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
