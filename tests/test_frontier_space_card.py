from __future__ import annotations

from pathlib import Path


CARD = Path("frontier-space/README.md")
DOCKERFILE = Path("Dockerfile.frontier")


def _frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    assert end > 4
    result: dict[str, str] = {}
    for raw_line in text[4:end].splitlines():
        if not raw_line or raw_line.startswith(" ") or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def test_frontier_space_card_has_valid_provider_metadata() -> None:
    text = CARD.read_text(encoding="utf-8")
    metadata = _frontmatter(text)
    assert metadata["title"] == "SZL Vertical Frontier"
    assert metadata["emoji"] == "🧭"
    assert metadata["sdk"] == "docker"
    assert metadata["app_port"] == "7860"
    assert metadata["pinned"] == "true"
    assert metadata["license"] == "apache-2.0"
    assert 1 <= len(metadata["short_description"]) <= 60


def test_frontier_space_card_preserves_truth_and_safety_boundaries() -> None:
    text = CARD.read_text(encoding="utf-8")
    required = (
        "zero model adapters",
        "zero external\nkernel adapters",
        "zero effectors",
        "SIMULATED_ONLY",
        "Conjecture 1 — OPEN",
        "No proprietary source code",
        "does not\nestablish factual truth, safety, performance, compliance, adoption, funding,\nrevenue, or production authorization",
    )
    for marker in required:
        assert marker in text


def test_frontier_dockerfile_uses_an_exact_dependency_free_closure() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY frontier_app.py ./frontier_app.py" in text
    assert "COPY frontier_fabric ./frontier_fabric" in text
    assert "COPY . ." not in text
    assert "pip install" not in text
    assert "http://127.0.0.1:7860/healthz" in text
    assert 'CMD ["python", "-u", "frontier_app.py"]' in text
