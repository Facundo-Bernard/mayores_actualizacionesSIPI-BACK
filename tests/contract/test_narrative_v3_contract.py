import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.features.narrative.schemas.v3_contract_schemas import (
    CartaJugador,
    ConsecuenciaNumerica,
    ContinuacionPendiente,
    IniciarPartidaCommand,
    ReciboComandoV3,
    RecompensaRecuperable,
    ResultadoNarrativo,
    ResultadoPendiente,
    RunCommandType,
    SnapshotRunV3,
)
from app.features.narrative.v3_openapi import build_narrative_v3_openapi
from app.main import app

pytestmark = pytest.mark.contract

SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "narrative_v3.openapi.json"
RUNS_PATH = "/api/narrative/v3/runs"
SNAPSHOT_ROUTE = "/api/narrative/v3/runs/{runId}"
COMMANDS_ROUTE = "/api/narrative/v3/runs/{runId}/commands"
RECEIPT_ROUTE = "/api/narrative/v3/runs/{runId}/receipts/{commandId}"


def snapshot_valido(**overrides) -> SnapshotRunV3:
    data = {
        "runId": "run-v3-1",
        "generation": 1,
        "schemaVersion": 1,
        "rulesVersion": "rules-fixture-1",
        "contentVersion": "content-fixture-1",
        "version": 4,
        "motor": "v2",
        "date": "2099-01-01",
        "mesActual": 3,
        "faseActual": "BALANCE_MES",
        "status": "in_progress",
        "gamePolicyVersion": "standard-1",
        "ageAdaptation": "none",
        "corte": [],
        "afinidad": {},
        "inventario": [],
        "tagsActivos": [],
        "recursos": [],
        "contenidoActual": None,
        "comandosPermitidos": ["AVANZAR_MES"],
        "historialMensual": [],
    }
    data.update(overrides)
    return SnapshotRunV3(**data)


def resultado_neutral() -> ResultadoPendiente:
    return ResultadoPendiente(
        resultadoId="resultado-neutral-1",
        alcance="escena",
        texto="La escena concluye sin cambios numéricos.",
        tipoResultado="neutro",
        grafoId="grafo-1",
        nodoId="nodo-final-1",
        consecuencias=[],
    )


def esquema_operacion(spec: dict, path: str, method: str) -> dict:
    return spec["paths"][path][method]


def test_contrato_v3_tiene_snapshot_reproducible_y_no_esta_montado():
    spec = build_narrative_v3_openapi()
    stored = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert spec == stored
    assert spec["info"]["x-contract-status"] == "target-not-published"
    assert not any(path.startswith("/api/narrative/v3") for path in app.openapi()["paths"])


def test_superficie_v3_se_limita_a_creacion_snapshot_comandos_y_recibos():
    spec = build_narrative_v3_openapi()

    assert {
        path: sorted(
            method
            for method in path_item
            if method in {"get", "post", "put", "patch", "delete"}
        )
        for path, path_item in spec["paths"].items()
    } == {
        RUNS_PATH: ["post"],
        SNAPSHOT_ROUTE: ["get"],
        COMMANDS_ROUTE: ["post"],
        RECEIPT_ROUTE: ["get"],
    }
    assert spec["security"] == [{"bearerAuth": []}, {"guestCredential": []}]
    assert spec["components"]["securitySchemes"]["guestCredential"]["name"] == "X-Guest-Credential"


def test_comandos_son_discriminados_y_excluyen_el_motor_plano_v1():
    spec = build_narrative_v3_openapi()
    schema = esquema_operacion(spec, COMMANDS_ROUTE, "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]

    assert schema["discriminator"]["propertyName"] == "type"
    assert set(schema["discriminator"]["mapping"]) == {
        "ELEGIR_CARTA_MENSUAL",
        "AVANZAR_NODO",
        "CONTINUAR_RESULTADO",
        "AVANZAR_MES",
        "REINICIAR_PARTIDA",
    }
    assert "DECIDIR_EVENTO" not in json.dumps(spec)
    assert "RESPONDER_CONVERSACION" not in json.dumps(spec)

    for component_ref in schema["discriminator"]["mapping"].values():
        component_name = component_ref.rsplit("/", 1)[-1]
        component = spec["components"]["schemas"][component_name]
        assert {"commandId", "generation", "expectedVersion", "type", "payload"}.issubset(
            component["required"]
        )
        assert "commandHash" not in component["properties"]
        assert not {"userId", "user_id", "principal"}.intersection(component["properties"])


def test_creacion_rechaza_duplicados_iniciales():
    create_schema = build_narrative_v3_openapi()["components"]["schemas"]["IniciarPartidaCommand"]
    assert {"commandId", "date", "type", "payload"}.issubset(create_schema["required"])

    payload = {
        "commandId": "create-1",
        "date": "2099-01-01",
        "type": "INICIAR_PARTIDA",
        "payload": {
            "corteElegidaIds": ["pj-a", "pj-a", "pj-b"],
            "cartasInicialesIds": ["carta-a", "carta-b", "carta-c"],
        },
    }

    with pytest.raises(ValidationError, match="no admiten duplicados"):
        IniciarPartidaCommand(**payload)


def test_inventario_conserva_copias_como_instancias_distintas():
    carta = CartaJugador(id="carta-a", categoria="item", nombre="Carta", descripcion="Visible")

    snapshot = snapshot_valido(
        inventario=[
            {"instanceId": "instancia-1", "carta": carta},
            {"instanceId": "instancia-2", "carta": carta},
        ]
    )

    assert [item.carta.id for item in snapshot.inventario] == ["carta-a", "carta-a"]
    assert [item.instanceId for item in snapshot.inventario] == ["instancia-1", "instancia-2"]

    with pytest.raises(ValidationError, match="instanceId debe ser único"):
        snapshot_valido(
            inventario=[
                {"instanceId": "instancia-1", "carta": carta},
                {"instanceId": "instancia-1", "carta": carta},
            ]
        )


def test_resultado_neutral_y_continuacion_son_recuperables_en_snapshot_y_recibo():
    resultado = resultado_neutral()
    snapshot = snapshot_valido(
        version=5,
        resultadoPendiente=resultado,
        continuacionPendiente=ContinuacionPendiente(resultadoId=resultado.resultadoId),
        comandosPermitidos=[RunCommandType.CONTINUAR_RESULTADO],
    )
    recibo = ReciboComandoV3(
        runId=snapshot.runId,
        generation=snapshot.generation,
        commandId="command-5",
        type="AVANZAR_NODO",
        commandHash="hash-canonico-del-servidor",
        previousVersion=4,
        version=5,
        snapshot=snapshot,
        consecuencias=[],
        resultado=ResultadoNarrativo(**resultado.model_dump(exclude={"consecuencias", "recompensa"})),
    )

    assert recibo.snapshot.resultadoPendiente.texto == resultado.texto
    assert recibo.snapshot.resultadoPendiente.consecuencias == []
    assert recibo.snapshot.continuacionPendiente.resultadoId == resultado.resultadoId
    assert recibo.snapshot.comandosPermitidos == [RunCommandType.CONTINUAR_RESULTADO]


def test_continuacion_no_puede_quedar_huerfana():
    with pytest.raises(ValidationError, match="deben coexistir"):
        snapshot_valido(resultadoPendiente=resultado_neutral())

    with pytest.raises(ValidationError, match="CONTINUAR_RESULTADO requiere"):
        snapshot_valido(comandosPermitidos=[RunCommandType.CONTINUAR_RESULTADO])


def test_componentes_publicos_no_exponen_azar_ni_contenido_futuro():
    spec = build_narrative_v3_openapi()
    forbidden = {
        "desenlaces",
        "siguiente_nodo",
        "nodo_raiz",
        "nodos",
        "seed",
        "rngState",
        "peso",
        "peso_base",
        "conversaciones",
        "probabilidad",
    }

    def visit(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                assert key not in forbidden
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(spec["components"]["schemas"])


def test_consecuencias_conservan_clamp_y_aritmetica_confirmada():
    data = {
        "consecuenciaId": "consecuencia-1",
        "origen": {"tipo": "carta", "origenId": "carta-a", "instanceId": "instancia-1"},
        "tipo": "recurso",
        "atributo": "oro",
        "antes": 95,
        "deltaSolicitado": 10,
        "deltaAplicado": 5,
        "despues": 100,
    }

    consequence = ConsecuenciaNumerica(**data)
    assert consequence.deltaSolicitado == 10
    assert consequence.deltaAplicado == 5
    assert consequence.despues == 100

    with pytest.raises(ValidationError, match=r"antes \+ deltaAplicado"):
        ConsecuenciaNumerica(**{**data, "despues": 105})


def test_recompensa_distingue_ledger_de_economia_local():
    local = RecompensaRecuperable(rewardId="reward-1", puntos=100, canal="local")
    assert local.liquidacion is None

    with pytest.raises(ValidationError, match="ledger exige"):
        RecompensaRecuperable(rewardId="reward-2", puntos=100, canal="ledger")

    with pytest.raises(ValidationError, match="economía local"):
        RecompensaRecuperable(
            rewardId="reward-3",
            puntos=100,
            canal="local",
            liquidacion={"estado": "liquidada"},
        )


def test_errores_cubren_autenticacion_propiedad_conflicto_y_commit_incierto():
    spec = build_narrative_v3_openapi()
    command_responses = esquema_operacion(spec, COMMANDS_ROUTE, "post")["responses"]

    assert {"401", "403", "404", "409", "422", "503"}.issubset(command_responses)
    assert command_responses["503"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
    assert "misma clave" in command_responses["503"]["description"]
    error_codes = set(spec["components"]["schemas"]["ErrorCode"]["enum"])
    assert {
        "validation_error",
        "unauthenticated",
        "forbidden",
        "version_conflict",
        "generation_conflict",
        "command_reused",
        "command_outcome_unknown",
    }.issubset(error_codes)
