"""Congela el contrato OpenAPI. Un cambio acá tiene que ser una decisión, no un accidente."""

import json
from pathlib import Path

import pytest

from app.main import app

pytestmark = pytest.mark.contract

SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "openapi.json"


def _load_snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_openapi_matches_snapshot():
    current = app.openapi()
    stored = _load_snapshot()

    if current == stored:
        return

    current_paths = set(current.get("paths", {}))
    stored_paths = set(stored.get("paths", {}))
    added = sorted(current_paths - stored_paths)
    removed = sorted(stored_paths - current_paths)
    details = []
    if added:
        details.append(f"rutas nuevas: {added}")
    if removed:
        details.append(f"rutas eliminadas: {removed}")
    if not details:
        details.append("cambió el schema de una ruta existente o los componentes")

    pytest.fail(
        "El contrato OpenAPI cambió respecto del snapshot. "
        + "; ".join(details)
        + ". Si el cambio es deliberado, regenerá tests/contract/snapshots/openapi.json."
    )
