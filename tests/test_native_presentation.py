"""Public presentation embeds exact artwork without gaining runtime authority."""
from __future__ import annotations

import ast
import base64
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "deploy/szl_verticals/presentation.py"


def constants():
    tree = ast.parse(OWNER.read_text())
    assert all(isinstance(node, (ast.Expr, ast.Assign)) for node in tree.body)
    return {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)}


def test_embedded_native_tokens_and_icon_are_exact():
    values = constants()
    manifest = json.loads((ROOT / "docs/NATIVE_PRESENTATION.json").read_text())
    assets = {item["name"]: item for item in manifest["assets"]}
    assert hashlib.sha256(values["NATIVE_TOKENS_CSS"].encode()).hexdigest() == assets["kanchay-tokens"]["sha256"]
    images = []

    class ImageParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "img":
                images.append(dict(attrs))

    ImageParser().feed(values["NATIVE_ICON_HTML"])
    assert len(images) == 1
    image = images[0]
    assert image["width"] == image["height"] == "32"
    assert image["alt"] == ""
    data = base64.b64decode(image["src"].removeprefix("data:image/svg+xml;base64,"), validate=True)
    assert hashlib.sha256(data).hexdigest() == assets["orbit-v2-icon-32"]["sha256"]


def test_existing_container_copies_the_shared_presentation_owner():
    dockerfile = (ROOT / "deploy/Dockerfile").read_text()
    assert "COPY deploy/szl_verticals/" in dockerfile
    for path in ("deploy/app.py", "deploy/szl_verticals/frontier.py", "deploy/szl_verticals/showcase.py"):
        text = (ROOT / path).read_text()
        assert "{NATIVE_ICON_HTML}" in text
        assert "{NATIVE_TOKENS_CSS}" in text
        assert "{NATIVE_INTERFACE_CSS}" in text
