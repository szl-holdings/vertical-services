#!/usr/bin/env python3
"""Converge the shared vertical runtime on the public Killinchu boundary.

The six internal engines remain independently testable.  Public product
identity is different: Aegis is the resilience portfolio name and Sentra is the
Defend component engine inside ``SZLHOLDINGS/killinchu``.  This transformation
is exact, idempotent, and refuses source drift instead of silently applying a
partial rewrite.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "deploy" / "szl_verticals" / "profiles.py"
APP = ROOT / "deploy" / "app.py"


def replace_once(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        if old in text:
            raise RuntimeError(f"both old and new contracts are present in {path}")
        return False
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one exact contract in {path.relative_to(ROOT)}; found {count}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def update_profiles() -> bool:
    changed = False
    replacements = (
        (
            '        "product": "Aegis / Sentra",',
            '        "product": "Killinchu / Defend",',
        ),
        (
            '        "public_space": "SZLHOLDINGS/sentra",',
            '        "public_space": "SZLHOLDINGS/killinchu",\n'
            '        "public_route": "/defend",\n'
            '        "component_engine": "Sentra",\n'
            '        "portfolio_name": "Aegis",',
        ),
        (
            '            "title": "Aegis Immune Cell",',
            '            "title": "Killinchu Defend Plane",',
        ),
        (
            '            "kicker": "AEGIS / SENTRA",',
            '            "kicker": "KILLINCHU / DEFEND",',
        ),
        (
            '            "archetype": "enterprise cyber command",',
            '            "archetype": "cyber-physical resilience command",',
        ),
        (
            '            "signature_view": "Attack path → immune gate → human review",',
            '            "signature_view": "Attack path → bounded proposal → human approval",',
        ),
        (
            '''        "consolidation": {
            "aegis_status": "ENTERPRISE_EXPERIENCE",
            "sentra_status": "CANONICAL_RUNTIME",
            "immune_status": "CONSOLIDATED_ORGAN",
            "immune_compatibility_alias": "/api/verticals/immune",
            "aegis_compatibility_alias": "/api/verticals/aegis",
            "effectors": "DISABLED",
        },''',
            '''        "consolidation": {
            "public_product": "KILLINCHU",
            "public_runtime": "SZLHOLDINGS/killinchu",
            "public_route": "/defend",
            "aegis_status": "PORTFOLIO_NAME",
            "sentra_status": "COMPONENT_ENGINE",
            "standalone_sentra_space": "RETIRE_AFTER_LIVE_PARITY",
            "immune_status": "COMPATIBILITY_ALIAS_MIGRATION_REQUIRED",
            "immune_compatibility_alias": "/api/verticals/immune",
            "aegis_compatibility_alias": "/api/verticals/aegis",
            "effectors": "DISABLED",
            "human_approval_required": True,
        },''',
        ),
        (
            '        "canonical_repository": "szl-holdings/counsel",',
            '        "canonical_repository": "szl-holdings/a11oy/verticals/counsel",',
        ),
    )
    for old, new in replacements:
        changed = replace_once(PROFILES, old, new) or changed
    return changed


def update_app() -> bool:
    changed = False
    replacements = (
        (
            '''        "purpose": (
            "Aegis cyber command, deny-by-default policy gates, Immune-organ "
            "inspection, threat evidence, and signed verdicts"
        ),
        "public_home": "SZLHOLDINGS/sentra",
        "experience": "/experience/aegis",
        "intelligence": "/intelligence/aegis",
        "aliases": ["aegis", "immune"],''',
            '''        "purpose": (
            "Killinchu Defend plane: Aegis portfolio context, Sentra defensive "
            "control, deny-by-default gates, threat evidence, bounded proposals, "
            "independent approval, simulated rehearsal, rollback, and receipts"
        ),
        "public_home": "SZLHOLDINGS/killinchu",
        "public_route": "https://szlholdings-killinchu.hf.space/defend",
        "experience": "https://szlholdings-killinchu.hf.space/defend",
        "component_experience": "/experience/aegis",
        "intelligence": "/intelligence/aegis",
        "component_engine": "sentra",
        "portfolio_name": "Aegis",
        "aliases": ["aegis", "immune"],''',
        ),
        (
            '        "aegis_canonical_runtime": "sentra",\n'
            '        "immune_canonical_runtime": "sentra",',
            '        "aegis_canonical_runtime": "killinchu/defend",\n'
            '        "sentra_component_runtime": "killinchu/defend",\n'
            '        "immune_compatibility_runtime": "sentra",\n'
            '        "immune_migration_state": "MIGRATION_REQUIRED",',
        ),
    )
    for old, new in replacements:
        changed = replace_once(APP, old, new) or changed
    return changed


def main() -> int:
    changed: list[str] = []
    if update_profiles():
        changed.append(str(PROFILES.relative_to(ROOT)))
    if update_app():
        changed.append(str(APP.relative_to(ROOT)))

    profiles = PROFILES.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    forbidden = {
        "deploy/szl_verticals/profiles.py": "SZLHOLDINGS/sentra",
        "deploy/app.py": '"public_home": "SZLHOLDINGS/sentra"',
    }
    for label, token in forbidden.items():
        text = profiles if label.endswith("profiles.py") else app
        if token in text:
            raise RuntimeError(f"retired public identity remains in {label}: {token}")

    print("KILLINCHU PRODUCT BOUNDARY CONVERGED", sorted(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
