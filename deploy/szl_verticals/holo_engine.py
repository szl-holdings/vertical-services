"""Pinned, hash-verified three.js r170 WebGPU engine for the holo3d front door.

The bytes are the unmodified upstream ``three@0.170.0/build/three.webgpu.min.js``
(MIT, license header embedded in the file), copied byte-for-byte from
szl-holdings/a11oy ``static/3d/vendor/three/three.webgpu.min.js`` where the same
size and sha256 are pinned in its VENDOR_MANIFEST.md. The build is
self-contained (no import statements), so it needs no other file. It is served
same-origin only; the browser re-hashes it before importing it (see holo3d.py),
and the server refuses to serve it if the pin does not match.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parent / "vendor" / "three.webgpu.min.js"
ENGINE_ROUTE = "/assets/holo/three.webgpu.min.js"
ENGINE_BYTES = 822115
ENGINE_SHA256 = "9d01bb1bae1badb5071d341f76c3569f6118bad126effd425a06611a9d993035"
ENGINE_UPSTREAM = "three@0.170.0/build/three.webgpu.min.js"


def load_pinned_engine(path: Path = ENGINE_PATH) -> bytes | None:
    """Return the engine bytes only when size and sha256 match the pin."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) != ENGINE_BYTES or hashlib.sha256(data).hexdigest() != ENGINE_SHA256:
        return None
    return data
