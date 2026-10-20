import pytest
import httpx


@pytest.mark.anyio
async def test_sso_ticket_complete_lifecycle():
    auth_client = httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0)
    sipi_client = httpx.AsyncClient(base_url="http://127.0.0.1:8082", timeout=10.0)

    try:
        # 1. Login inicial de Administrador en el Autenticador Central
        res_login = await auth_client.post(
            "/auth/login",
            json={"email": "admin@autenticador.com", "password": "999999"}
        )
        assert res_login.status_code == 200
        admin_token = res_login.json()["token"]

        # 2. Generar ticket SSO efímero para saltar a mayoresactualizaciones
        res_ticket = await auth_client.post(
            "/auth/sso/create-ticket",
            json={"servicio": "mayoresactualizaciones"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res_ticket.status_code == 200
        ticket_data = res_ticket.json()
        assert ticket_data["success"] is True
        ticket_code = ticket_data["ticket"]
        assert ticket_code.startswith("sso_tk_")
        assert ticket_data["expiresInSeconds"] == 30

        # 3. Intentar canjear el ticket para un servicio no autorizado (conmijuegos) -> 403
        res_wrong_service = await auth_client.post(
            "/auth/sso/consume-ticket",
            json={"ticket": ticket_code, "servicio": "conmijuegos"}
        )
        assert res_wrong_service.status_code == 403
        assert "Restricción de destino" in res_wrong_service.json()["detail"]

        # Como el intento anterior falló por destino pero NO quemó el ticket o queremos probar el canje limpio,
        # generamos un ticket nuevo para el canje oficial en SIPI-BACK
        res_ticket_2 = await auth_client.post(
            "/auth/sso/create-ticket",
            json={"servicio": "mayoresactualizaciones"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res_ticket_2.status_code == 200
        valid_ticket = res_ticket_2.json()["ticket"]

        # 4. Canjear el ticket en SIPI-BACK (puerto 8082)
        res_redeem = await sipi_client.post(
            "/api/auth/sso/canjear-ticket",
            json={"ticket": valid_ticket}
        )
        assert res_redeem.status_code == 200
        redeem_data = res_redeem.json()
        assert redeem_data["success"] is True
        assert redeem_data["user"]["tipoUsuario"] == 2
        sipi_admin_token = redeem_data["token"]
        assert sipi_admin_token is not None

        # 5. Intentar REUTILIZAR el ticket canjeado -> 401 (descartable / quemado)
        res_reuse = await sipi_client.post(
            "/api/auth/sso/canjear-ticket",
            json={"ticket": valid_ticket}
        )
        assert res_reuse.status_code == 401
        assert "inválido, ya fue utilizado" in res_reuse.json()["detail"]

        # 6. Probar la emisión de ticket de retorno inverso desde SIPI-BACK
        res_return_ticket = await sipi_client.post(
            "/api/auth/sso/crear-ticket-retorno",
            json={"servicioDestino": "autenticador"},
            headers={"Authorization": f"Bearer {sipi_admin_token}"}
        )
        assert res_return_ticket.status_code == 200
        return_ticket_data = res_return_ticket.json()
        assert return_ticket_data["success"] is True
        return_ticket = return_ticket_data["ticket"]
        assert return_ticket.startswith("sso_tk_")
        assert return_ticket_data["servicio"] == "autenticador"

        # 7. Canjear el ticket de retorno en el Autenticador Central (completando el ciclo bidireccional)
        res_consume_return = await auth_client.post(
            "/auth/sso/consume-ticket",
            json={"ticket": return_ticket, "servicio": "autenticador"}
        )
        assert res_consume_return.status_code == 200
        returned_auth_data = res_consume_return.json()
        assert returned_auth_data["success"] is True
        assert returned_auth_data["user"]["tipoUsuario"] == 2
        assert returned_auth_data["token"] is not None

    finally:
        await auth_client.aclose()
        await sipi_client.aclose()
