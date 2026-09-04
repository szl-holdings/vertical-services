from __future__ import annotations

from html.parser import HTMLParser

from frontier_fabric.catalog import VERTICALS
from frontier_fabric.showcase import render_showcase_index, render_vertical_showcase


class _DocumentProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.scripts_with_src = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        data = dict(attrs)
        self.tags.append((tag, data))
        if data.get("id"):
            self.ids.add(str(data["id"]))
        if tag == "a" and data.get("href"):
            self.links.append(str(data["href"]))
        if tag == "script" and data.get("src"):
            self.scripts_with_src += 1


def _probe(document: str) -> _DocumentProbe:
    parser = _DocumentProbe()
    parser.feed(document)
    parser.close()
    return parser


def test_index_links_every_vertical() -> None:
    document = render_showcase_index()
    probe = _probe(document)
    assert "Ten products" in document
    for vertical in VERTICALS:
        assert f"./{vertical.id}" in probe.links
        assert vertical.display_name in document
    assert "prefers-reduced-motion" in document


def test_every_vertical_concept_is_semantic_responsive_and_dependency_free() -> None:
    for vertical in VERTICALS:
        document = render_vertical_showcase(vertical.id)
        probe = _probe(document)

        assert document.startswith("<!doctype html>")
        assert f'data-vertical="{vertical.id}"' in document
        assert 'name="viewport"' in document
        assert 'href="#main"' in document
        assert "main" in probe.ids
        assert "prefers-reduced-motion" in document
        assert "min-width:44px" in document
        assert "aria-live=\"polite\"" in document
        assert probe.scripts_with_src == 0
        assert "http://" not in document
        assert "https://" not in document
        assert vertical.operator_outcome in document
        assert vertical.unmet_need in document
        assert vertical.differentiator in document
        assert vertical.effect_mode.value in document
        assert vertical.public_actuation.value in document


def test_each_vertical_has_distinct_stage_markup() -> None:
    pages = {vertical.id: render_vertical_showcase(vertical.id) for vertical in VERTICALS}
    stage_fragments = {}
    for vertical_id, document in pages.items():
        start = document.index('<section class="stage')
        end = document.index("</section>", start) + len("</section>")
        stage_fragments[vertical_id] = document[start:end]

    assert len(set(stage_fragments.values())) == len(VERTICALS)
    expected_markers = {
        "a11oy": "Decision trajectory",
        "hatun": "Temporal council",
        "killinchu": "SIMULATE ONLY",
        "sentra": "Exposure nervous system",
        "lyte": "Causal trace river",
        "puriq-finance": "Thesis evidence graph",
        "terra": "Parcel strata",
        "prism-counsel": "Matter argument command",
        "living-anatomy": "Living system body",
        "szl-atlas": "Evidence atlas",
    }
    for vertical_id, marker in expected_markers.items():
        assert marker in stage_fragments[vertical_id]


def test_killinchu_public_concept_is_synthetic_and_simulation_only() -> None:
    document = render_vertical_showcase("killinchu")
    assert "synthetic" in document.lower()
    assert "historical planning" in document.lower()
    assert "public effectors disabled" in document.lower()
    assert "SIMULATED_ONLY" in document
    assert "SIMULATE ONLY" in document


def test_frontend_contract_exposes_evidence_at_the_decision() -> None:
    for vertical in VERTICALS:
        document = render_vertical_showcase(vertical.id)
        for evidence_item in vertical.evidence_contract:
            assert evidence_item in document
        for module in vertical.experience_modules:
            assert module in document
        for signature in vertical.theme.signature_modules:
            assert signature in document
