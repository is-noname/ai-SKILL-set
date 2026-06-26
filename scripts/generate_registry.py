#!/usr/bin/env python3
"""Scans skills/ for SKILL.md files and writes registry.json to repo root."""

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
REGISTRY_OUT = REPO_ROOT / "registry.json"

LAYER_DIRS = {
    0: "layer-0-core",
    1: "layer-1-base",
    2: "layer-2-main",
    3: "layer-3-domain",
    4: "layer-4-project",
}


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown. Returns empty dict if none."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    raw = match.group(1)
    result: dict = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        # Handle JSON-ish arrays: ["a", "b"]
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            result[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()] if inner else []
        elif val.lower() == "true":
            result[key] = True
        elif val.lower() == "false":
            result[key] = False
        elif val.isdigit():
            result[key] = int(val)
        else:
            result[key] = val.strip('"').strip("'")
    return result


def infer_layer(skill_path: Path) -> int | None:
    """Derive layer from parent directory name."""
    for layer, dirname in LAYER_DIRS.items():
        if dirname in skill_path.parts:
            return layer
    return None


def _has_cycle(name: str, skills: dict, visited: set, stack: set) -> list[str] | None:
    visited.add(name)
    stack.add(name)
    for dep in skills.get(name, {}).get("dependencies", []):
        if dep not in skills:
            continue
        if dep not in visited:
            result = _has_cycle(dep, skills, visited, stack)
            if result is not None:
                return [name] + result
        elif dep in stack:
            return [name, dep]
    stack.discard(name)
    return None


def validate(skills: dict) -> list[str]:
    errors: list[str] = []
    for name, entry in skills.items():
        layer = entry.get("layer")
        deps = entry.get("dependencies", [])

        if layer is None:
            errors.append(f"{name}: missing 'layer'")
            continue

        for dep in deps:
            if dep not in skills:
                errors.append(f"{name}: dependency '{dep}' not found in registry")
                continue
            dep_layer = skills[dep].get("layer")
            if dep_layer is not None and dep_layer > layer:
                errors.append(
                    f"{name} (layer {layer}): dependency '{dep}' is layer {dep_layer} — "
                    f"upward dependency not allowed"
                )

        if layer == 0 and deps:
            errors.append(f"{name}: layer-0 skills must have no dependencies (found: {deps})")

    visited: set = set()
    for name in skills:
        if name not in visited:
            cycle = _has_cycle(name, skills, visited, set())
            if cycle:
                errors.append(f"circular dependency detected: {' → '.join(cycle)}")

    return errors


def main() -> int:
    skill_files = sorted(SKILLS_DIR.rglob("SKILL.md"))
    if not skill_files:
        print("No SKILL.md files found.", file=sys.stderr)
        return 1

    skills: dict = {}
    parse_errors: list[str] = []
    skipped_outside: list[str] = []

    for skill_file in skill_files:
        text = skill_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        name = fm.get("name")
        if not name:
            parse_errors.append(f"{skill_file.relative_to(REPO_ROOT)}: missing 'name' in frontmatter")
            continue

        inferred_layer = infer_layer(skill_file)
        rel = skill_file.parent.relative_to(REPO_ROOT)

        # Nur Skills innerhalb der layer-*-Verzeichnisse gehören in die geteilte Registry.
        # Alles unter projects/, sets/ etc. ist projekt-/profilspezifisch und darf nicht
        # pullbar werden.
        if inferred_layer is None:
            if "layer" in fm:
                parse_errors.append(
                    f"{name}: liegt außerhalb skills/layer-*/ ({rel}), deklariert aber "
                    f"layer={fm['layer']} — nicht registriert. Nach layer-N/ verschieben "
                    f"oder das layer-Feld entfernen."
                )
            else:
                skipped_outside.append(f"{name} ({rel})")
            continue

        layer = fm.get("layer", inferred_layer)

        if "layer" in fm and fm["layer"] != inferred_layer:
            parse_errors.append(
                f"{name}: frontmatter layer={fm['layer']} conflicts with directory layer={inferred_layer}"
            )
            layer = inferred_layer

        skills[name] = {
            "name": name,
            "description": fm.get("description", ""),
            "layer": layer,
            "dependencies": fm.get("dependencies", []),
            "path": str(skill_file.parent.relative_to(REPO_ROOT)),
        }
        if fm.get("disable-model-invocation"):
            skills[name]["disable-model-invocation"] = True

    validation_errors = validate(skills)
    all_errors = parse_errors + validation_errors

    registry = {
        "generated": date.today().isoformat(),
        "skills": skills,
    }

    REGISTRY_OUT.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"registry.json written — {len(skills)} skills")

    if skipped_outside:
        print(f"\nSkipped (außerhalb skills/layer-*/, nicht registriert):")
        for entry in skipped_outside:
            print(f"  - {entry}")

    if all_errors:
        print("\nValidation errors:")
        for err in all_errors:
            print(f"  ! {err}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
