#!/usr/bin/env python3
"""Pulls skills and their transitive dependencies into a target project."""

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = REPO_ROOT / "registry.json"
SETS_DIR = REPO_ROOT / "skills" / "sets"


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print("registry.json not found — run scripts/generate_registry.py first", file=sys.stderr)
        sys.exit(1)
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["skills"]


def load_set(set_name: str) -> list[str]:
    path = SETS_DIR / f"{set_name}.json"
    if not path.exists():
        print(f"Set '{set_name}' not found in {SETS_DIR}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["skills"]


def resolve(names: list[str], registry: dict) -> list[str]:
    """Returns skill names in topological install order (deps first)."""
    resolved: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name not in registry:
            print(f"Unknown skill: '{name}'", file=sys.stderr)
            sys.exit(1)
        visited.add(name)
        for dep in registry[name].get("dependencies", []):
            visit(dep)
        resolved.append(name)

    for name in names:
        visit(name)
    return resolved


def pull(
    names: list[str],
    target: Path,
    registry: dict,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[list[str], list[str]]:
    order = resolve(names, registry)
    installed: list[str] = []
    skipped: list[str] = []

    for name in order:
        src = REPO_ROOT / registry[name]["path"]
        dst = target / name

        if dst.exists() and not force:
            skipped.append(name)
            continue

        if not dry_run:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        installed.append(name)

    return installed, skipped


def cmd_pull(args: argparse.Namespace, registry: dict) -> int:
    names: list[str] = list(args.skills)
    if args.set:
        names = load_set(args.set)

    if not names:
        print("No skills specified. Use skill names or --set <name>.", file=sys.stderr)
        return 1

    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)

    installed, skipped = pull(names, target, registry, dry_run=args.dry_run, force=args.force)

    if args.dry_run:
        print("[dry-run] would install:", ", ".join(installed) or "(none)")
        print("[dry-run] would skip (already present):", ", ".join(skipped) or "(none)")
    else:
        if installed:
            print("Installed:", ", ".join(installed))
        if skipped:
            print("Skipped (already present, use --force to overwrite):", ", ".join(skipped))
        if not installed and not skipped:
            print("Nothing to do.")

    return 0


def cmd_update(args: argparse.Namespace, registry: dict) -> int:
    target = Path(args.target)
    if not target.exists():
        print(f"Target '{target}' does not exist — nothing installed.", file=sys.stderr)
        return 1

    installed = [d.name for d in target.iterdir() if d.is_dir()]
    if not installed:
        print("No skills installed.")
        return 0

    outdated: list[str] = []
    unknown: list[str] = []

    for name in sorted(installed):
        if name not in registry:
            unknown.append(name)
            continue
        local_skill = target / name / "SKILL.md"
        repo_skill = REPO_ROOT / registry[name]["path"] / "SKILL.md"
        if not local_skill.exists() or not repo_skill.exists():
            outdated.append(name)
        elif local_skill.read_text(encoding="utf-8") != repo_skill.read_text(encoding="utf-8"):
            outdated.append(name)

    if unknown:
        print("Unknown (not in registry, skipped):", ", ".join(unknown))

    if not outdated:
        print("All skills up to date.")
        return 0

    print("Outdated:", ", ".join(outdated))

    if args.dry_run:
        return 0

    installed_names, _ = pull(outdated, target, registry, force=True)
    print("Updated:", ", ".join(installed_names))
    return 0


def cmd_list(registry: dict) -> int:
    by_layer: dict[int, list] = {}
    for entry in registry.values():
        layer = entry.get("layer") if entry.get("layer") is not None else -1
        by_layer.setdefault(layer, []).append(entry)

    for layer in sorted(by_layer):
        print(f"\nLayer {layer}:")
        for entry in sorted(by_layer[layer], key=lambda e: e["name"]):
            deps = ", ".join(entry["dependencies"]) if entry["dependencies"] else "—"
            print(f"  {entry['name']:<30} {entry['description'][:60]}")
            if entry["dependencies"]:
                print(f"  {'':30} deps: {deps}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull skills from ai-SKILL-set into a project.")
    sub = parser.add_subparsers(dest="cmd")

    p_pull = sub.add_parser("pull", help="Pull skills into target directory")
    p_pull.add_argument("skills", nargs="*", metavar="SKILL", help="Skill names to pull")
    p_pull.add_argument("--set", metavar="NAME", help="Pull a predefined skill set")
    p_pull.add_argument(
        "--target",
        default=".claude/skills",
        metavar="DIR",
        help="Target directory (default: .claude/skills)",
    )
    p_pull.add_argument("--force", action="store_true", help="Overwrite already-installed skills")
    p_pull.add_argument("--dry-run", action="store_true", help="Show what would be installed")

    p_list = sub.add_parser("list", help="List available skills")

    p_update = sub.add_parser("update", help="Update outdated installed skills")
    p_update.add_argument(
        "--target",
        default=".claude/skills",
        metavar="DIR",
        help="Target directory (default: .claude/skills)",
    )
    p_update.add_argument("--dry-run", action="store_true", help="Show what would be updated")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1

    registry = load_registry()

    if args.cmd == "pull":
        return cmd_pull(args, registry)
    if args.cmd == "list":
        return cmd_list(registry)
    if args.cmd == "update":
        return cmd_update(args, registry)
    return 1


if __name__ == "__main__":
    sys.exit(main())
