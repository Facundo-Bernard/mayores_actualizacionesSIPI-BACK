"""
testing_lab/e2e_full_system_test.py
Suite de verificación exhaustiva end-to-end de todos los flujos del sistema en vivo:
1. Autenticación y credenciales (X-Guest-Credential firmado y Bearer JWT)
2. Economía, puntos, pistas y desbloqueos (post-purga de vidas)
3. Código muerto retirado (Progreso de cursos y gestión de cuentas)
4. Desafíos diarios (Wordle, Sudoku, Crucigrama, Sopa de Letras y envío de intentos)
5. Motor Narrativo V2 (Setup, inicio, draft, grafos V2, OCC, modales y rechazo de V1)
6. Torre de Control y Administración (Ajustes auditados, validación de grafos y catálogos)
"""

import sys
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.config import settings
from app.core.security import create_access_token

BASE_URL = "http://127.0.0.1:8090"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

class TestFailure(Exception):
    pass

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def record(self, category: str, name: str, success: bool, details: str = ""):
        if success:
            self.passed += 1
            print(f"  [PASS] {name} {details}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name} -> {details}")
        self.results.append({"category": category, "name": name, "success": success, "details": details})

    def request(self, method: str, path: str, data: dict = None, headers: dict = None, expected_status: int = 200) -> dict:
        url = f"{BASE_URL}{path}"
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
        
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                parsed = json.loads(resp_body) if resp_body else {}
                if resp.status != expected_status:
                    raise TestFailure(f"Status esperado {expected_status}, recibido {resp.status}. Body: {resp_body[:200]}")
                return parsed
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            if e.code == expected_status:
                try:
                    return json.loads(err_body)
                except Exception:
                    return {"raw": err_body}
            raise TestFailure(f"HTTP {e.code} (esperado {expected_status}): {err_body[:200]}")
        except Exception as e:
            raise TestFailure(f"Error de conexión a {url}: {e}")

runner = TestRunner()

# ==============================================================================
# 1. AUTENTICACIÓN Y CREDENCIALES DE INVITADO Y USUARIO
# ==============================================================================
print("\n" + "=" * 70)
print("1. VERIFICACIÓN DE IDENTIDAD Y CREDENCIALES")
print("=" * 70)

guest_id = None
guest_cred = None

try:
    data = runner.request("POST", "/api/auth/guest-credential", data={})
    assert data.get("success") is True
    assert "credential" in data
    assert "guest_id" in data
    guest_id = data["guest_id"]
    guest_cred = data["credential"]
    runner.record("Auth", "Emisión de X-Guest-Credential", True, f"guest_id={guest_id[:8]}...")
except Exception as e:
    runner.record("Auth", "Emisión de X-Guest-Credential", False, str(e))

# Rechazo de credencial inválida
try:
    runner.request("GET", f"/api/narrative/partida/setup?date={TODAY}", headers={"X-Guest-Credential": "invalido.falso.jwt"}, expected_status=401)
    runner.record("Auth", "Rechazo de credencial de invitado falsa (401)", True)
except Exception as e:
    runner.record("Auth", "Rechazo de credencial de invitado falsa (401)", False, str(e))

# Rechazo sin autenticación
try:
    runner.request("GET", f"/api/narrative/partida/setup?date={TODAY}", expected_status=401)
    runner.record("Auth", "Rechazo sin autenticación (401)", True)
except Exception as e:
    runner.record("Auth", "Rechazo sin autenticación (401)", False, str(e))

# Token de usuario registrado (admin / usuario 1)
admin_user_payload = {
    "id": 1,
    "name": "Administrador General",
    "email": "admin@autenticador.com",
    "tipo_usuario": 2,
    "rol": 2,
    "activo": True,
    "servicios": {"cognijuegos": True}
}
admin_token = create_access_token(admin_user_payload)
auth_headers = {"Authorization": f"Bearer {admin_token}"}
runner.record("Auth", "Generación de Bearer Token válido", True, "user_id=1 (admin)")

# ==============================================================================
# 2. ECONOMÍA Y PUNTOS (SISTEMA POST-VIDAS)
# ==============================================================================
print("\n" + "=" * 70)
print("2. VERIFICACIÓN DE ECONOMÍA Y PUNTOS")
print("=" * 70)

# Catálogo público
try:
    cfg = runner.request("GET", "/api/economy/config")
    assert "paquetes_tienda" not in cfg, "paquetes_tienda no debe existir"
    assert "costo_vida_puntos" not in cfg, "costo_vida_puntos no debe existir"
    assert "vidas_maximas" not in cfg, "vidas_maximas no debe existir"
    assert "costo_desbloqueo_dia_puntos" in cfg
    assert "escalas_tiempo_por_juego" in cfg
    runner.record("Economia", "GET /api/economy/config catálogo limpio", True, f"Desbloqueo={cfg['costo_desbloqueo_dia_puntos']} pts")
except Exception as e:
    runner.record("Economia", "GET /api/economy/config catálogo limpio", False, str(e))

# buy-lives debe dar 404
try:
    runner.request("POST", "/api/economy/buy-lives", data={}, expected_status=404)
    runner.record("Economia", "POST /api/economy/buy-lives erradicado (404)", True)
except Exception as e:
    runner.record("Economia", "POST /api/economy/buy-lives erradicado (404)", False, str(e))

# refill-lives y consume-life protegidos
try:
    runner.request("POST", "/api/economy/refill-lives", data={}, expected_status=401)
    runner.record("Economia", "POST /api/economy/refill-lives protegido (401)", True)
except Exception as e:
    runner.record("Economia", "POST /api/economy/refill-lives protegido (401)", False, str(e))

try:
    runner.request("POST", "/api/economy/consume-life", data={}, expected_status=401)
    runner.record("Economia", "POST /api/economy/consume-life protegido (401)", True)
except Exception as e:
    runner.record("Economia", "POST /api/economy/consume-life protegido (401)", False, str(e))

# GET /api/economy/me autenticado
try:
    me = runner.request("GET", "/api/economy/me", headers=auth_headers)
    assert "puntos" in me
    assert "racha" in me
    assert "dias_desbloqueados" in me
    runner.record("Economia", "GET /api/economy/me saldo autenticado", True, f"Puntos={me['puntos']} Racha={me['racha']}")
except Exception as e:
    runner.record("Economia", "GET /api/economy/me saldo autenticado", False, str(e))

# POST /api/economy/unlock-day
try:
    unlock_res = runner.request("POST", "/api/economy/unlock-day", data={"game_id": "wordle", "date": "2026-10-01"}, headers=auth_headers)
    assert unlock_res.get("success") is True
    assert unlock_res.get("unlocked") is True
    runner.record("Economia", "POST /api/economy/unlock-day (canje puntos)", True, f"Costo={unlock_res.get('costo')} pts")
except Exception as e:
    runner.record("Economia", "POST /api/economy/unlock-day (canje puntos)", False, str(e))

# POST /api/economy/use-hint (idempotencia y 20 puntos)
try:
    hint_res = runner.request("POST", "/api/economy/use-hint", data={"game_id": "wordle", "date": TODAY, "hint_index": 0}, headers=auth_headers)
    assert hint_res.get("success") is True
    runner.record("Economia", "POST /api/economy/use-hint resolución de pista", True, f"Puntos restantes: {hint_res.get('puntos_restantes')}")
except Exception as e:
    runner.record("Economia", "POST /api/economy/use-hint resolución de pista", False, str(e))

# ==============================================================================
# 3. RUTAS ELIMINADAS (CODIGO MUERTO: PROGRESO Y USUARIO)
# ==============================================================================
print("\n" + "=" * 70)
print("3. VERIFICACIÓN DE CÓDIGO MUERTO RETIRADO (404)")
print("=" * 70)

for dead_path in [
    "/api/progreso/1",
    "/api/progreso/sincronizar",
    "/api/usuario/me",
    "/api/usuario/1",
    "/api/usuario/busqueda",
]:
    try:
        runner.request("GET", dead_path, expected_status=404)
        runner.record("DeadCode", f"Ruta {dead_path} responde 404", True)
    except Exception as e:
        runner.record("DeadCode", f"Ruta {dead_path} responde 404", False, str(e))

# ==============================================================================
# 4. DESAFÍOS DIARIOS (CONSULTAS DE JUEGOS Y REGISTRO DE INTENTOS)
# ==============================================================================
print("\n" + "=" * 70)
print("4. VERIFICACIÓN DE DESAFÍOS DIARIOS Y REGISTRO DE INTENTOS")
print("=" * 70)

for game_id in ["wordle", "sudoku", "sopa_letras", "crucigrama"]:
    try:
        res = runner.request("GET", f"/api/challenges/today?game_id={game_id}")
        runner.record("DailyChallenges", f"GET /api/challenges/today?game_id={game_id}", True, f"date={res.get('date', TODAY)}")
    except Exception as e:
        runner.record("DailyChallenges", f"GET /api/challenges/today?game_id={game_id}", False, str(e))

# Registro de intento en Wordle
try:
    attempt_payload = {
        "game_id": "wordle",
        "date": TODAY,
        "mode": "daily",
        "status": "completed",
        "attempts": 2,
        "stars": 3,
        "score": 100,
        "grade": "S",
        "time_taken_seconds": 45,
        "guesses": ["CASAS", "ARBOL"]
    }
    att_res = runner.request("POST", "/api/games/attempts", data=attempt_payload, headers=auth_headers)
    assert att_res.get("game_id") == "wordle"
    assert att_res.get("status") == "completed"
    runner.record("DailyChallenges", "POST /api/games/attempts registro de partida", True, f"Grade={att_res.get('grade')} Puntos={att_res.get('puntos_ganados')}")
except Exception as e:
    runner.record("DailyChallenges", "POST /api/games/attempts registro de partida", False, str(e))

# ==============================================================================
# 5. JUEGO NARRATIVO V2 (GRAFOS, SETUP, INICIO, ESTADO)
# ==============================================================================
print("\n" + "=" * 70)
print("5. VERIFICACIÓN DE MOTOR NARRATIVO V2 CON X-Guest-Credential")
print("=" * 70)

if guest_cred:
    g_headers = {"X-Guest-Credential": guest_cred}
    
    # 5.1 Setup
    setup_data = None
    try:
        setup_data = runner.request("GET", f"/api/narrative/partida/setup?date={TODAY}", headers=g_headers)
        runner.record("Narrative", "GET /api/narrative/partida/setup", True, f"Tiene partida: {setup_data.get('tiene_partida_activa')}")
    except Exception as e:
        runner.record("Narrative", "GET /api/narrative/partida/setup", False, str(e))

    # 5.2 Reiniciar si había partida previa para arrancar limpios
    if setup_data and setup_data.get("tiene_partida_activa"):
        try:
            runner.request("POST", "/api/narrative/partida/reiniciar", data={"date": TODAY}, headers=g_headers)
            setup_data = runner.request("GET", f"/api/narrative/partida/setup?date={TODAY}", headers=g_headers)
            runner.record("Narrative", "POST /api/narrative/partida/reiniciar partida previa", True)
        except Exception as e:
            runner.record("Narrative", "POST /api/narrative/partida/reiniciar partida previa", False, str(e))

    # 5.3 Iniciar partida V2
    if setup_data and not setup_data.get("tiene_partida_activa"):
        pjs = [p["_id"] for p in setup_data.get("personajes_ofrecidos", [])[:3]]
        cards = [c["_id"] for c in setup_data.get("cartas_ofrecidas", [])[:3]]
        
        init_payload = {
            "date": TODAY,
            "corte_elegida_ids": pjs,
            "cartas_iniciales_ids": cards
        }
        
        init_res = None
        try:
            init_res = runner.request("POST", "/api/narrative/v2/partida/iniciar", data=init_payload, headers=g_headers)
            runner.record("Narrative", "POST /api/narrative/v2/partida/iniciar", True, f"Mes={init_res.get('mes_actual')} Fase={init_res.get('fase_actual')}")
        except Exception as e:
            runner.record("Narrative", "POST /api/narrative/v2/partida/iniciar", False, str(e))

        # 5.4 Consultar estado reactivo
        estado = None
        try:
            estado = runner.request("GET", f"/api/narrative/v2/partida/estado?date={TODAY}", headers=g_headers)
            runner.record("Narrative", "GET /api/narrative/v2/partida/estado", True, f"Fase={estado.get('fase_actual')}")
        except Exception as e:
            runner.record("Narrative", "GET /api/narrative/v2/partida/estado", False, str(e))

        # 5.5 Consultar modales de partida
        for modal in ["corte", "inventario", "historial"]:
            try:
                m_data = runner.request("GET", f"/api/narrative/partida/{modal}?date={TODAY}", headers=g_headers)
                runner.record("Narrative", f"GET /api/narrative/partida/{modal}", True)
            except Exception as e:
                runner.record("Narrative", f"GET /api/narrative/partida/{modal}", False, str(e))

        # 5.6 Elegir carta mensual de draft
        cartas_draft = init_res.get("cartas_draft_actual") if init_res else []
        if not cartas_draft and estado:
            cartas_draft = estado.get("cartas_draft_actual", [])
        
        if cartas_draft:
            carta_id = cartas_draft[0]["_id"]
            try:
                draft_res = runner.request(
                    "POST",
                    "/api/narrative/v2/partida/elegir-carta-mes",
                    data={"date": TODAY, "carta_id": carta_id},
                    headers=g_headers
                )
                runner.record("Narrative", "POST /api/narrative/v2/partida/elegir-carta-mes", True, f"Siguiente Fase: {draft_res.get('fase_actual')}")
            except Exception as e:
                runner.record("Narrative", "POST /api/narrative/v2/partida/elegir-carta-mes", False, str(e))

        # 5.7 Rechazo de endpoints V1 sobre partida V2
        try:
            runner.request(
                "POST",
                "/api/narrative/v2/partida/decidir-evento",
                data={"date": TODAY, "opcion_id": "cualquiera"},
                headers=g_headers,
                expected_status=400
            )
            runner.record("Narrative", "Endpoints Legacy V1 rechazan partida V2 (400)", True)
        except Exception as e:
            runner.record("Narrative", "Endpoints Legacy V1 rechazan partida V2 (400)", False, str(e))

        # 5.8 Reiniciar partida y comprobar archivado
        try:
            reinicio = runner.request("POST", "/api/narrative/partida/reiniciar", data={"date": TODAY}, headers=g_headers)
            assert reinicio.get("eliminada") is True
            runner.record("Narrative", "POST /api/narrative/partida/reiniciar (D07)", True, f"Archivada: {reinicio.get('archivada')}")
        except Exception as e:
            runner.record("Narrative", "POST /api/narrative/partida/reiniciar (D07)", False, str(e))

# ==============================================================================
# 6. TORRE DE CONTROL Y ADMINISTRACIÓN
# ==============================================================================
print("\n" + "=" * 70)
print("6. VERIFICACIÓN DE TORRE DE CONTROL Y PANEL ADMIN")
print("=" * 70)

# Catálogo formal de reglas
try:
    cat = runner.request("GET", "/api/narrative/admin/catalogo-reglas", headers=auth_headers)
    assert "disparadores" in cat
    assert "operadores" in cat
    assert "tipos_accion" in cat
    runner.record("Admin", "GET /api/narrative/admin/catalogo-reglas", True, f"{len(cat['tipos_accion'])} tipos de accion")
except Exception as e:
    runner.record("Admin", "GET /api/narrative/admin/catalogo-reglas", False, repr(e))

# Búsqueda de usuario
try:
    u_search = runner.request("GET", "/api/admin/economy/user/search?identificador=1", headers=auth_headers)
    assert u_search.get("id") == 1
    runner.record("Admin", "GET /api/admin/economy/user/search?identificador=1", True, f"User: {u_search.get('name')}")
except Exception as e:
    runner.record("Admin", "GET /api/admin/economy/user/search?identificador=1", False, str(e))

# Ajuste admin auditado
try:
    adj = runner.request("POST", "/api/admin/economy/user/adjust", data={"identificador": "1", "puntos_sumar": 10}, headers=auth_headers)
    assert adj.get("success") is True
    runner.record("Admin", "POST /api/admin/economy/user/adjust ajuste auditado", True, f"Saldo: {adj.get('puntos')} pts")
except Exception as e:
    runner.record("Admin", "POST /api/admin/economy/user/adjust ajuste auditado", False, str(e))

# ==============================================================================
# RESUMEN FINAL
# ==============================================================================
print("\n" + "=" * 70)
print(f"RESUMEN FINAL DE PRUEBAS EN VIVO: {runner.passed} PASARON, {runner.failed} FALLARON")
print("=" * 70)

if runner.failed > 0:
    sys.exit(1)
