import pytest
import httpx
import time

@pytest.mark.anyio
async def test_auth_microservice_flow():
    # Usamos una IP sintética única por ejecución de test para evitar colisiones con el rate limiter de 60s
    test_ip = f"192.168.99.{int(time.time()) % 250}"
    client_headers = {"X-Forwarded-For": test_ip}

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8082", timeout=10.0, headers=client_headers) as client:
        # 1. Health check
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "UP"

        # 2. Login con PIN válido y con permisos activos (Marta González)
        res_marta = await client.post("/api/auth/ingresar-codigo", json={"codigoAcceso": "123456"})
        assert res_marta.status_code == 200
        data_marta = res_marta.json()
        assert data_marta["success"] is True
        assert data_marta["user"]["name"] == "Marta González"
        assert data_marta["user"]["id"] == 2
        token_marta = data_marta["token"]
        assert token_marta is not None

        # 3. Verificar token emitido por el Autenticador
        res_verif = await client.post("/api/auth/verificar-token", json={"token": token_marta})
        assert res_verif.status_code == 200
        assert res_verif.json()["valid"] is True

        # 4. Login con usuario sin permiso para mayoresactualizaciones (Roberto Méndez)
        res_roberto = await client.post("/api/auth/ingresar-codigo", json={"codigoAcceso": "654321"})
        assert res_roberto.status_code == 403
        assert "no tiene habilitado el servicio" in res_roberto.json()["detail"]

        # 5. Login con cuenta suspendida (Elena Gómez)
        res_elena = await client.post("/api/auth/ingresar-codigo", json={"codigoAcceso": "112233"})
        assert res_elena.status_code == 403
        assert "inactiva" in res_elena.json()["detail"].lower()

        # 6. Login de Operador de Sistemas (Admin Central)
        res_admin = await client.post(
            "/api/auth/login-sistemas",
            json={"email": "admin@autenticador.com", "password": "admin"}
        )
        if res_admin.status_code != 200:
            res_admin = await client.post(
                "/api/auth/login-sistemas",
                json={"email": "admin@autenticador.com", "password": "999999"}
            )
        assert res_admin.status_code == 200
        assert res_admin.json()["success"] is True
        token_admin = res_admin.json()["token"]

        # 7. Acceso a endpoints administrativos con token de admin
        res_users = await client.get("/usuario", headers={"Authorization": f"Bearer {token_admin}"})
        assert res_users.status_code == 200
        assert "total" in res_users.json()

        # 8. Registro de nuevo usuario alumno delegando al Autenticador Central
        test_email = f"test_gateway_{int(time.time())}@ejemplo.com"
        res_reg = await client.post(
            "/api/auth/register",
            json={"name": "Usuario Gateway Test", "email": test_email}
        )
        assert res_reg.status_code == 200
        reg_data = res_reg.json()
        assert reg_data["success"] is True
        assert reg_data["user"]["email"] == test_email
        assert reg_data["user"]["codigoAcceso"] is not None
        assert reg_data["token"] is not None
