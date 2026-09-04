#!/usr/bin/env python3
"""Install the Killinchu canonical runtime contract into vertical-services."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "killinchu_runtime_contract.py"
CONTRACT = ROOT / "contracts" / "killinchu-runtime-convergence.v1.json"
DOC = ROOT / "docs" / "KILLINCHU_RUNTIME_CONVERGENCE.md"
TEST = ROOT / "tests" / "test_killinchu_runtime_convergence.py"
README = ROOT / "README.md"
START = "# SZL-KILLINCHU-RUNTIME-CONVERGENCE:v1:START"
END = "# SZL-KILLINCHU-RUNTIME-CONVERGENCE:v1:END"

MODULE_SOURCE = r'''"""Canonical Killinchu runtime identity for the combined vertical service.

The existing Sentra and Vessels engines remain available as compatibility
routes. This module makes their one product authority explicit and does not
claim a downstream runtime is live merely because source code is present.
"""
from __future__ import annotations

from typing import Any

CANONICAL_PRODUCT = "killinchu"
LOCKED_FORMULA_IDS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
LAMBDA_STATUS = "CONJECTURE_1_ADVISORY"
COMPATIBILITY = {
    "sentra": {"lobe": "aegis", "role": "defensive_and_cyber_intelligence"},
    "vessels": {"lobe": "vessels", "role": "maritime_intelligence"},
}


def architecture() -> dict[str, Any]:
    return {
        "schema": "szl.vertical-services.killinchu/v1",
        "canonical_product": CANONICAL_PRODUCT,
        "lobes": {
            "aegis": {
                "role": "defensive_and_cyber_intelligence",
                "compatibility_prefix": "/sentra",
                "standalone_product": False,
            },
            "vessels": {
                "role": "maritime_intelligence",
                "compatibility_prefix": "/vessels",
                "standalone_product": False,
            },
        },
        "locked_formula_ids": list(LOCKED_FORMULA_IDS),
        "lambda_status": LAMBDA_STATUS,
        "human_authority_required": True,
        "receipt_required": True,
        "destructive_or_offensive_autonomy": False,
        "effectors": "SIMULATED_UNLESS_INDEPENDENTLY_PROVED",
        "source_state": "SOFTWARE",
        "runtime_state": "REACHABLE_ONLY_WHEN_THIS_ENDPOINT_ANSWERS",
    }


def lobe(lobe_id: str) -> dict[str, Any]:
    normalized = str(lobe_id or "").strip().lower()
    aliases = {"aegis": "aegis", "sentra": "aegis", "vessels": "vessels"}
    if normalized not in aliases:
        raise ValueError(f"unknown Killinchu lobe: {lobe_id!r}")
    canonical = aliases[normalized]
    doc = architecture()["lobes"][canonical]
    return {
        "schema": "szl.vertical-services.killinchu-lobe/v1",
        "canonical_product": CANONICAL_PRODUCT,
        "lobe": canonical,
        "role": doc["role"],
        "standalone_product": False,
        "source_state": "SOFTWARE",
        "runtime_state": "REACHABLE_ONLY_WHEN_THIS_ENDPOINT_ANSWERS",
    }


def compatibility_headers(path: str) -> dict[str, str]:
    normalized = str(path or "").lower()
    for prefix, row in COMPATIBILITY.items():
        if normalized == f"/{prefix}" or normalized.startswith(f"/{prefix}/"):
            return {
                "X-SZL-Canonical-Product": CANONICAL_PRODUCT,
                "X-SZL-Product-Lobe": row["lobe"],
                "X-SZL-Standalone-Product": "false",
            }
    return {}
'''

TEST_SOURCE = r'''from __future__ import annotations

import unittest

from killinchu_runtime_contract import (
    CANONICAL_PRODUCT,
    COMPATIBILITY,
    LAMBDA_STATUS,
    LOCKED_FORMULA_IDS,
    architecture,
    compatibility_headers,
    lobe,
)


class KillinchuRuntimeConvergenceTest(unittest.TestCase):
    def test_one_canonical_product(self) -> None:
        self.assertEqual(CANONICAL_PRODUCT, "killinchu")
        doc = architecture()
        self.assertEqual(doc["canonical_product"], "killinchu")
        self.assertEqual(set(doc["lobes"]), {"aegis", "vessels"})
        self.assertTrue(all(row["standalone_product"] is False for row in doc["lobes"].values()))

    def test_authority_boundary_is_exact(self) -> None:
        self.assertEqual(LOCKED_FORMULA_IDS, ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"))
        self.assertEqual(LAMBDA_STATUS, "CONJECTURE_1_ADVISORY")
        doc = architecture()
        self.assertTrue(doc["human_authority_required"])
        self.assertTrue(doc["receipt_required"])
        self.assertFalse(doc["destructive_or_offensive_autonomy"])
        self.assertEqual(doc["effectors"], "SIMULATED_UNLESS_INDEPENDENTLY_PROVED")

    def test_compatibility_routes_disclose_lobe_and_canonical_product(self) -> None:
        expected = {"sentra": "aegis", "vessels": "vessels"}
        self.assertEqual({key: row["lobe"] for key, row in COMPATIBILITY.items()}, expected)
        for prefix, lobe_id in expected.items():
            headers = compatibility_headers(f"/{prefix}/healthz")
            self.assertEqual(headers["X-SZL-Canonical-Product"], "killinchu")
            self.assertEqual(headers["X-SZL-Product-Lobe"], lobe_id)
            self.assertEqual(headers["X-SZL-Standalone-Product"], "false")
        self.assertEqual(compatibility_headers("/terra/healthz"), {})

    def test_lobe_aliases_do_not_create_products(self) -> None:
        self.assertEqual(lobe("aegis")["lobe"], "aegis")
        self.assertEqual(lobe("sentra")["lobe"], "aegis")
        self.assertEqual(lobe("vessels")["lobe"], "vessels")
        for alias in ("aegis", "sentra", "vessels"):
            self.assertFalse(lobe(alias)["standalone_product"])
        with self.assertRaises(ValueError):
            lobe("unknown")

    def test_runtime_wording_is_response_scoped(self) -> None:
        self.assertEqual(
            architecture()["runtime_state"],
            "REACHABLE_ONLY_WHEN_THIS_ENDPOINT_ANSWERS",
        )


if __name__ == "__main__":
    unittest.main()
'''

ROUTES = r'''

# SZL-KILLINCHU-RUNTIME-CONVERGENCE:v1:START
from killinchu_runtime_contract import architecture as _szl_killinchu_architecture
from killinchu_runtime_contract import compatibility_headers as _szl_killinchu_headers
from killinchu_runtime_contract import lobe as _szl_killinchu_lobe


@{app}.middleware("http")
async def szl_killinchu_product_identity(request, call_next):
    """Label compatibility responses without changing their domain payload."""
    response = await call_next(request)
    for key, value in _szl_killinchu_headers(request.url.path).items():
        response.headers[key] = value
    return response


@{app}.get("/killinchu/architecture", tags=["Killinchu"])
def szl_killinchu_architecture():
    """Read the canonical source contract; endpoint reachability is not model truth."""
    return _szl_killinchu_architecture()


@{app}.get("/killinchu/aegis/healthz", tags=["Killinchu"])
def szl_killinchu_aegis_lobe():
    return _szl_killinchu_lobe("aegis")


@{app}.get("/killinchu/vessels/healthz", tags=["Killinchu"])
def szl_killinchu_vessels_lobe():
    return _szl_killinchu_lobe("vessels")
# SZL-KILLINCHU-RUNTIME-CONVERGENCE:v1:END
'''

README_BLOCK = '''<!-- SZL-KILLINCHU-RUNTIME-CONVERGENCE:v1 -->
> **Defense convergence:** Killinchu is the canonical defense product. The existing `/sentra` engine is its Aegis defensive/cyber lobe; `/vessels` is its maritime lobe. Compatibility responses disclose `X-SZL-Canonical-Product`, `X-SZL-Product-Lobe`, and `X-SZL-Standalone-Product: false`. Source and routes remain preserved; product authority is unified.
'''


def choose_entrypoint() -> tuple[Path, str]:
    assignment = re.compile(r"(?m)^([A-Za-z_]\w*)\s*=\s*FastAPI\s*\(")
    excluded = {".git", ".venv", "venv", "node_modules", "tests", "tools"}
    candidates: list[tuple[int, Path, str]] = []
    for path in ROOT.rglob("*.py"):
        if any(part in excluded for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = assignment.search(text)
        if not match:
            continue
        score = 0
        rel = path.relative_to(ROOT).as_posix().lower()
        if rel in {"app.py", "main.py", "server.py", "src/app.py", "src/main.py"}:
            score += 30
        if "/sentra/healthz" in text and "/vessels/healthz" in text:
            score += 25
        if "vertical" in text.lower():
            score += 8
        if "@app." in text or "uvicorn" in text.lower():
            score += 4
        candidates.append((score, path, match.group(1)))
    if not candidates:
        raise RuntimeError("no FastAPI application found; refusing an unmounted convergence")
    candidates.sort(key=lambda row: (row[0], -len(str(row[1]))), reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise RuntimeError("ambiguous FastAPI application: " + ", ".join(str(row[1].relative_to(ROOT)) for row in candidates[:4]))
    return candidates[0][1], candidates[0][2]


def write_files() -> None:
    for path in (MODULE, CONTRACT, DOC, TEST):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite: {path.relative_to(ROOT)}")
    MODULE.write_text(MODULE_SOURCE, encoding="utf-8")
    CONTRACT.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT.write_text(json.dumps({
        "schema": "szl.vertical-services.killinchu/v1",
        "canonical_product": "killinchu",
        "lobes": {
            "aegis": {"compatibility_prefix": "/sentra", "standalone_product": False},
            "vessels": {"compatibility_prefix": "/vessels", "standalone_product": False},
        },
        "formula_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
        "lambda_status": "CONJECTURE_1_ADVISORY",
        "human_authority_required": True,
        "receipt_required": True,
        "destructive_or_offensive_autonomy": False,
        "effectors": "SIMULATED_UNLESS_INDEPENDENTLY_PROVED",
        "compatibility_source_preserved": True,
    }, indent=2) + "\n", encoding="utf-8")
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("""# Killinchu runtime convergence\n\nThe combined vertical runtime keeps the Sentra and Vessels engines as compatibility routes while assigning both to one canonical product authority: Killinchu. Sentra is the Aegis defensive/cyber lobe; Vessels is the maritime lobe.\n\nCompatibility routes preserve payloads and history and add response headers that disclose canonical product and lobe identity. New read-only Killinchu routes expose the source contract. Their reachability is not a model-quality, data-quality, or downstream-availability claim.\n""", encoding="utf-8")
    TEST.parent.mkdir(parents=True, exist_ok=True)
    TEST.write_text(TEST_SOURCE, encoding="utf-8")


def patch_readme() -> None:
    text = README.read_text(encoding="utf-8")
    if "SZL-KILLINCHU-RUNTIME-CONVERGENCE:v1" in text:
        raise RuntimeError("README convergence marker already present")
    lines = text.splitlines(keepends=True)
    at = 1 if lines and lines[0].startswith("#") else 0
    lines.insert(at, "\n" + README_BLOCK + "\n")
    README.write_text("".join(lines), encoding="utf-8")


def mount() -> Path:
    path, app = choose_entrypoint()
    text = path.read_text(encoding="utf-8")
    if START in text or "/killinchu/architecture" in text:
        raise RuntimeError("runtime convergence already mounted")
    path.write_text(text.rstrip() + ROUTES.format(app=app) + "\n", encoding="utf-8")
    return path


def main() -> int:
    write_files()
    patch_readme()
    entry = mount()
    print(entry.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
