"""Congela el contrato OpenAPI. Un cambio acá tiene que ser una decisión, no un accidente."""

import json
from pathlib import Path

import pytest

from app.main import app

pytestmark = pytest.mark.contract

SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "openapi.json"
DEPRECATED_TAG = "Narrativo - Legacy V1 (Deprecado)"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


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


def test_openapi_tags_agrupan_activos_y_dejan_deprecados_al_final():
    spec = app.openapi()
    declared_tags = [tag["name"] for tag in spec.get("tags", [])]
    operations = [
        operation
        for path_item in spec["paths"].values()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    ]
    used_tags = {
        tag
        for operation in operations
        for tag in operation.get("tags", [])
    }

    assert len(declared_tags) == len(set(declared_tags))
    assert set(declared_tags) == used_tags
    assert all(len(operation.get("tags", [])) == 1 for operation in operations)

    deprecated_operations = [
        operation for operation in operations if operation.get("deprecated") is True
    ]
    assert deprecated_operations
    assert all(
        operation["tags"] == [DEPRECATED_TAG] for operation in deprecated_operations
    )
    assert all(
        DEPRECATED_TAG not in operation["tags"]
        for operation in operations
        if operation.get("deprecated") is not True
    )
    assert declared_tags[-1] == DEPRECATED_TAG

    expected_relative_order = [
        "Estado",
        "Autenticación",
        "Narrativo - Flujo de Juego",
        "Narrativo - CRUD Universos",
        "Narrativo - CRUD Personajes",
        "Narrativo - CRUD Cartas",
        "Narrativo - CRUD Eventos V2",
        "Narrativo - CRUD Conversaciones V2",
        "Narrativo - CRUD Eventos Especiales V2",
        DEPRECATED_TAG,
    ]
    assert set(expected_relative_order).issubset(declared_tags)
    positions = [declared_tags.index(tag) for tag in expected_relative_order]
    assert positions == sorted(positions)
