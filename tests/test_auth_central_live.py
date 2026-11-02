import pytest
import httpx
import uuid
from app.core.config import settings

LIVE_AUTH_URL = "https://autenticacion.asistodo.com.ar"
LOCAL_BACKEND_URL = f"http://127.0.0.1:{settings.PORT}"
VITE_FRONTEND_URL = "http://127.0.0.1:5174"


@pytest.mark.anyio
async def test_live_central_auth_microservice_direct():
    """Verifica conectividad y contratos directamente contra el microservicio central."""
    async with httpx.AsyncClient(base_url=LIVE_AUTH_URL, timeout=10.0) as client:
        # 1. Healthcheck
        r_health = await client.get("/health")
        assert r_health.status_code == 200
        data_health = r_health.json()
        assert data_health["status"] == "ok"
        assert data_health["service"] == "autenticador-central"

        # 2. Validar acceso con PIN 123456
        r_pin = await client.post(
            "/auth/validar-acceso",
            json={"codigoAcceso": "123456", "servicio": "mayoresactualizaciones"}
        )
        assert r_pin.status_code == 200
        data_pin = r_pin.json()
        assert data_pin["success"] is True
        assert data_pin["allowed"] is True
        assert data_pin["user"]["codigoAcceso"] == "123456"
        assert data_pin["token"] is not None

        # 3. Validar acceso con PIN inválido
        r_invalid = await client.post(
            "/auth/validar-acceso",
            json={"codigoAcceso": "000000", "servicio": "mayoresactualizaciones"}
        )
        assert r_invalid.status_code == 200
        data_invalid = r_invalid.json()
        assert data_invalid["allowed"] is False

        # 4. Login operador
        r_login = await client.post(
            "/auth/login",
            json={"email": "admin@autenticador.com", "password": "123456", "servicio": "mayoresactualizaciones"}
        )
        assert r_login.status_code == 200
        data_login = r_login.json()
        assert data_login["success"] is True
        assert data_login["user"]["tipoUsuario"] == 2


@pytest.mark.anyio
async def test_backend_local_delegated_auth():
    """Verifica el flujo completo de autenticación local delegando al Autenticador Central."""
    client_headers = {"X-Forwarded-For": f"10.0.0.{uuid.uuid4().int % 200 + 10}"}

    async with httpx.AsyncClient(base_url=LOCAL_BACKEND_URL, timeout=12.0, headers=client_headers) as client:
        # 1. Login por código PIN
        r_code = await client.post("/api/auth/ingresar-codigo", json={"codigo": "123456"})
        assert r_code.status_code == 200
        data_code = r_code.json()
        assert data_code["success"] is True
        assert "token" in data_code
        assert data_code["user"]["codigoAcceso"] == "123456"
        token = data_code["token"]

        # 2. Verificar token JWT
        r_verif = await client.post("/api/auth/verificar-token", json={"token": token})
        assert r_verif.status_code == 200
        data_verif = r_verif.json()
        assert data_verif["success"] is True
        assert data_verif["valid"] is True

        # 3. Login de operador
        r_admin = await client.post(
            "/api/auth/login-sistemas",
            json={"email": "admin@autenticador.com", "password": "123456"}
        )
        assert r_admin.status_code == 200
        data_admin = r_admin.json()
        assert data_admin["success"] is True
        assert data_admin["user"]["tipoUsuario"] == 2
        admin_token = data_admin["token"]

        # 4. Probar ruta protegida con token Bearer
        r_protected = await client.get("/usuario?limit=1", headers={"Authorization": f"Bearer {admin_token}"})
        assert r_protected.status_code == 200

        # 5. Registrar nuevo alumno delegando al microservicio
        unique_suffix = uuid.uuid4().hex[:6]
        nuevo_email = f"alumno_test_{unique_suffix}@asistodo.com.ar"
        r_reg = await client.post(
            "/api/auth/register",
            json={"name": f"Alumno Test {unique_suffix}", "email": nuevo_email}
        )
        assert r_reg.status_code == 200
        data_reg = r_reg.json()
        assert data_reg["success"] is True
        assert "user" in data_reg
        nuevo_pin = data_reg["user"]["codigoAcceso"]
        assert len(nuevo_pin) == 6

        # 6. Ingresar inmediatamente con el nuevo PIN
        r_new_login = await client.post("/api/auth/ingresar-codigo", json={"codigo": nuevo_pin})
        assert r_new_login.status_code == 200
        data_new_login = r_new_login.json()
        assert data_new_login["success"] is True
        assert data_new_login["user"]["email"] == nuevo_email


@pytest.mark.anyio
async def test_vite_proxy_auth():
    """Verifica que el proxy de Vite en puerto 5174 enrute la autenticación transparentemente."""
    client_headers = {"X-Forwarded-For": f"10.0.1.{uuid.uuid4().int % 200 + 10}"}

    async with httpx.AsyncClient(base_url=VITE_FRONTEND_URL, timeout=12.0, headers=client_headers) as client:
        r_vite = await client.post("/api/auth/ingresar-codigo", json={"codigo": "123456"})
        assert r_vite.status_code == 200
        data_vite = r_vite.json()
        assert data_vite["success"] is True
        assert data_vite["user"]["codigoAcceso"] == "123456"

pytestmark = pytest.mark.live
