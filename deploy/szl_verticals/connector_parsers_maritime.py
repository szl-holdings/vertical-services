"""NOAA maritime metadata normalizer."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Mapping

from fastapi import HTTPException

def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_xml_text(root: ET.Element, names: set[str]) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) in names and element.text and element.text.strip():
            return element.text.strip()
    return None


def _parse_noaa(raw: bytes, _: Mapping[str, Any]) -> dict[str, Any]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise HTTPException(502, "NOAA InPort XML could not be parsed") from exc
    urls: list[str] = []
    for element in root.iter():
        name = _local_name(element.tag)
        text = (element.text or "").strip()
        if name in {"download-url", "url", "online-resource"} and text.startswith("https://"):
            urls.append(text)
    return {
        "catalog_item_id": _first_xml_text(root, {"catalog-item-id"}),
        "title": _first_xml_text(root, {"title"}),
        "status": _first_xml_text(root, {"status"}),
        "publication_date": _first_xml_text(root, {"publication-date"}),
        "time_frame_start": _first_xml_text(root, {"start-date"}),
        "time_frame_end": _first_xml_text(root, {"end-date"}),
        "abstract": (_first_xml_text(root, {"abstract"}) or "")[:2000],
        "distribution_urls": list(dict.fromkeys(urls))[:20],
        "data_mode": "HISTORICAL_OFFICIAL_AIS",
        "live_ais_claimed": False,
    }
