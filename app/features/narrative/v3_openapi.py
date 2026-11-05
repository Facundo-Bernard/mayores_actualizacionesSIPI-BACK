from copy import deepcopy
from typing import NoReturn

from fastapi import FastAPI, Path, Query

from app.features.narrative.schemas.v3_contract_schemas import (
    ErrorResponse,
    IniciarPartidaCommand,
    ReciboComandoV3,
    RunCommand,
    SnapshotRunV3,
)

CONTRACT_TAG = "Narrativo - Contrato V3 (no publicado)"

contract_app = FastAPI(
    title="Contrato objetivo Narrativo V3",
    version="3.0.0-contract",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    openapi_tags=[{"name": CONTRACT_TAG}],
)

ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Credencial ausente o inválida."},
    403: {"model": ErrorResponse, "description": "La run no pertenece al principal autenticado."},
    404: {"model": ErrorResponse, "description": "Run o recibo no encontrado."},
    409: {"model": ErrorResponse, "description": "Conflicto de versión, generación, fase o commandId."},
    422: {"model": ErrorResponse, "description": "Payload o selección inválidos."},
}


def _contract_only() -> NoReturn:
    raise NotImplementedError("OpenAPI objetivo: la implementación pertenece a N1–N6")


@contract_app.post(
    "/api/narrative/v3/runs",
    tags=[CONTRACT_TAG],
    response_model=ReciboComandoV3,
    responses={**ERROR_RESPONSES, 201: {"model": ReciboComandoV3}},
    summary="Crear una run V2 de forma idempotente por principal y fecha",
)
async def crear_run_v3(command: IniciarPartidaCommand) -> NoReturn:
    _contract_only()


@contract_app.get(
    "/api/narrative/v3/runs/{runId}",
    tags=[CONTRACT_TAG],
    response_model=SnapshotRunV3,
    responses=ERROR_RESPONSES,
    summary="Leer un snapshot completo sin ejecutar negocio",
)
async def obtener_snapshot_v3(
    runId: str = Path(min_length=1, max_length=128),
    generation: int = Query(ge=1),
) -> NoReturn:
    _contract_only()


@contract_app.post(
    "/api/narrative/v3/runs/{runId}/commands",
    tags=[CONTRACT_TAG],
    response_model=ReciboComandoV3,
    responses={
        **ERROR_RESPONSES,
        503: {
            "model": ErrorResponse,
            "description": "Resultado del commit incierto; recuperar o reintentar con la misma clave y payload.",
        },
    },
    summary="Confirmar exactamente una transición de una generación de run",
)
async def ejecutar_comando_v3(
    command: RunCommand,
    runId: str = Path(min_length=1, max_length=128),
) -> NoReturn:
    _contract_only()


@contract_app.get(
    "/api/narrative/v3/runs/{runId}/receipts/{commandId}",
    tags=[CONTRACT_TAG],
    response_model=ReciboComandoV3,
    responses=ERROR_RESPONSES,
    summary="Recuperar un recibo confirmado sin repetir efectos ni azar",
)
async def obtener_recibo_v3(
    runId: str = Path(min_length=1, max_length=128),
    commandId: str = Path(min_length=1, max_length=128),
    generation: int = Query(ge=1),
) -> NoReturn:
    _contract_only()


def build_narrative_v3_openapi() -> dict:
    spec = deepcopy(contract_app.openapi())
    spec["info"]["x-contract-status"] = "target-not-published"
    spec["components"]["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        "guestCredential": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Guest-Credential",
            "description": "Credencial de invitado firmada y verificada por el backend.",
        },
    }
    spec["security"] = [{"bearerAuth": []}, {"guestCredential": []}]
    return spec
