#!/usr/bin/env python3
"""Holt Claude zugewiesene User Stories/Tasks/Issues aus Taiga, kompakt formatiert.

Experimentelles Skript (noch kein Skill) - siehe IZG-T-079.
Credentials aus .env (TAIGA_URL, TAIGA_USERNAME, TAIGA_PASSWORD).
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


def load_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    values.setdefault("TAIGA_URL", os.environ.get("TAIGA_URL", "http://localhost:9000"))
    values.setdefault("TAIGA_USERNAME", os.environ.get("TAIGA_USERNAME", ""))
    values.setdefault("TAIGA_PASSWORD", os.environ.get("TAIGA_PASSWORD", ""))
    return values


def api_request(base_url: str, path: str, auth_token: str | None = None, method: str = "GET", body: dict | None = None):
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if auth_token:
        req.add_header("Authorization", f"Bearer {auth_token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"API-Fehler {e.code} bei {path}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def login(base_url: str, username: str, password: str) -> tuple[str, int]:
    result = api_request(
        base_url, "/api/v1/auth",
        body={"type": "normal", "username": username, "password": password},
    )
    return result["auth_token"], result["id"]


def fetch_assigned(base_url: str, token: str, project_id: int, endpoint: str, user_id: int) -> list[dict]:
    return api_request(base_url, f"/api/v1/{endpoint}?project={project_id}&assigned_to={user_id}", auth_token=token)


def format_item(item: dict) -> str:
    status = item.get("status_extra_info", {}).get("name", "?")
    due = item.get("due_date") or ""
    due_part = f" | faellig={due}" if due else ""
    return f"#{item['ref']} {item['subject']} | status={status}{due_part}"


def main() -> None:
    env = load_env()
    if not env["TAIGA_USERNAME"] or not env["TAIGA_PASSWORD"]:
        print("TAIGA_USERNAME/TAIGA_PASSWORD fehlen in .env", file=sys.stderr)
        sys.exit(1)

    base_url = env["TAIGA_URL"]
    token, user_id = login(base_url, env["TAIGA_USERNAME"], env["TAIGA_PASSWORD"])
    projects = api_request(base_url, "/api/v1/projects", auth_token=token)

    for project in projects:
        pid, pname = project["id"], project["name"]
        rows = []
        for endpoint in ("userstories", "tasks", "issues"):
            rows.extend(fetch_assigned(base_url, token, pid, endpoint, user_id))
        if not rows:
            continue
        print(f"\n## {pname} ({project['slug']})")
        for item in rows:
            print(format_item(item))


if __name__ == "__main__":
    main()
