#!/usr/bin/env python3
"""Apply the one-product Killinchu public taxonomy to Vertical Services.

Sentra remains an independently testable internal engine. Aegis remains the
portfolio label. Neither owns a separate public Hugging Face front door; the
public home for the entire cyber-resilience family is Killinchu.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one occurrence, found {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"UPDATED {path.relative_to(ROOT)}")


def main() -> None:
    profiles = ROOT / "deploy" / "szl_verticals" / "profiles.py"
    app = ROOT / "deploy" / "app.py"
    intelligence = ROOT / "deploy" / "szl_verticals" / "intelligence.py"
    tests = ROOT / "tests" / "test_intelligence_fabric.py"
    readme = ROOT / "README.md"

    replace_exact(
        profiles,
        '    "real-estate": "terra",\n',
        '    "real-estate": "terra",\n    "defend": "sentra",\n',
    )
    replace_exact(profiles, '        "product": "Aegis / Sentra",', '        "product": "Killinchu Defend",')
    replace_exact(profiles, '        "public_space": "SZLHOLDINGS/sentra",', '        "public_space": "SZLHOLDINGS/killinchu",')
    replace_exact(profiles, '            "title": "Aegis Immune Cell",', '            "title": "Killinchu Defend Plane",')
    replace_exact(profiles, '            "kicker": "AEGIS / SENTRA",', '            "kicker": "KILLINCHU / DEFEND",')
    replace_exact(
        profiles,
        '            "aegis_status": "ENTERPRISE_EXPERIENCE",\n',
        '            "public_product": "Killinchu",\n'
        '            "public_space": "SZLHOLDINGS/killinchu",\n'
        '            "public_tab": "/defend",\n'
        '            "aegis_status": "PORTFOLIO_NAME",\n',
    )
    replace_exact(
        profiles,
        '            "sentra_status": "CANONICAL_RUNTIME",',
        '            "sentra_status": "INTERNAL_ENGINE",',
    )

    replace_exact(
        app,
        "Aegis and Immune resolve to the\nSentra cyber runtime; PURIQ resolves to Finance; the aliases do not create\nduplicate state or competing execution authority.",
        "Aegis, Sentra, and Immune resolve to one internal defensive engine whose\npublic product home is Killinchu; PURIQ resolves to Finance. These aliases do\nnot create duplicate state, Spaces, or competing execution authority.",
    )
    replace_exact(
        app,
        '        "public_home": "SZLHOLDINGS/sentra",',
        '        "public_home": "SZLHOLDINGS/killinchu",',
    )
    replace_exact(
        app,
        '        "experience": "/experience/aegis",\n        "intelligence": "/intelligence/aegis",\n        "aliases": ["aegis", "immune"],',
        '        "experience": "/experience/aegis",\n'
        '        "intelligence": "/intelligence/aegis",\n'
        '        "public_tab": "https://szlholdings-killinchu.hf.space/defend",\n'
        '        "engine_status": "INTERNAL_CAPABILITY_PLANE",\n'
        '        "aliases": ["aegis", "immune", "defend"],',
    )
    replace_exact(
        app,
        '        "aegis_canonical_runtime": "sentra",\n        "immune_canonical_runtime": "sentra",',
        '        "aegis_internal_engine": "sentra",\n'
        '        "sentra_public_home": "SZLHOLDINGS/killinchu",\n'
        '        "aegis_public_home": "SZLHOLDINGS/killinchu",\n'
        '        "immune_internal_engine": "sentra",',
    )
    replace_exact(
        app,
        '        badge = " · VESSELS CONSOLIDATED HERE" if engine == "killinchu" else ""',
        '        if engine == "killinchu":\n'
        '            badge = " · PUBLIC DEFENSE + MARITIME HOME"\n'
        '        elif engine == "sentra":\n'
        '            badge = " · INTERNAL ENGINE · PUBLIC HOME KILLINCHU"\n'
        '        else:\n'
        '            badge = ""',
    )

    replace_exact(
        intelligence,
        '"""Model and kernel fabric for the six canonical SZL verticals.',
        '"""Model and kernel fabric for six internal SZL vertical engines.',
    )
    replace_exact(
        intelligence,
        '    "sentra": {\n        "primary_job":',
        '    "sentra": {\n'
        '        "public_product": "Killinchu",\n'
        '        "public_tab": "/defend",\n'
        '        "engine_status": "INTERNAL_CAPABILITY_PLANE",\n'
        '        "primary_job":',
    )

    replace_exact(
        tests,
        '        "aegis": "sentra",\n        "immune": "sentra",',
        '        "aegis": "sentra",\n'
        '        "immune": "sentra",\n'
        '        "defend": "sentra",',
    )

    note = """

## Public product topology

The service contains six independently testable engines, but it does not create
six competing public product homes. **Killinchu is the sole public home for the
Aegis/Sentra/Immune cyber-resilience family**. `sentra` remains the internal
engine key; `aegis`, `immune`, and `defend` are compatibility aliases. The
independent public vertical Spaces are Killinchu, Terra, PRISM Counsel, PURIQ
Finance, Lyte, and David Leads. `vertical-services` is shared runtime
infrastructure, not another customer-facing vertical.
"""
    text = readme.read_text(encoding="utf-8")
    marker = "## Public product topology"
    if marker not in text:
        readme.write_text(text.rstrip() + note + "\n", encoding="utf-8")
        print("UPDATED README.md")
    elif text.count(marker) != 1:
        raise SystemExit("README public product topology marker is ambiguous")


if __name__ == "__main__":
    main()
