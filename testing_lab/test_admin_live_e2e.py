import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))
sys.path.insert(0, BASE_DIR)

import httpx
from app.core.security import create_access_token

BASE_URL = "http://127.0.0.1:8090"

def run_tests():
    print("=== LIVE E2E TEST: ADMIN PANEL & ENGINE DESACOPLADO ===")
    token = create_access_token({"id": 1, "sub": "1", "email": "admin@autenticador.com", "tipo_usuario": 2, "rol": "administrador", "name": "Administrador Central", "activo": True})
    headers = {"Authorization": f"Bearer {token}"}
    print("[OK] Token de Administrador generado con firma JWT valida.")

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # 1. GET /admin/operaciones
        resp_ops = client.get("/api/narrative/admin/operaciones", headers=headers)
        assert resp_ops.status_code == 200, f"Error en /operaciones: {resp_ops.text}"
        ops = resp_ops.json()
        assert len(ops) >= 5, "Debe haber al menos 5 primitivas registradas"
        print(f"[OK] GET /admin/operaciones retornado ({len(ops)} primitivas).")

        # 2. GET /admin/eventos-motor
        resp_evts = client.get("/api/narrative/admin/eventos-motor", headers=headers)
        assert resp_evts.status_code == 200, f"Error en /eventos-motor: {resp_evts.text}"
        evts = resp_evts.json()
        assert any(e["evento_motor"] == "al_obtener" for e in evts)
        assert any(e["evento_motor"] == "inicio_mes" for e in evts)
        print("[OK] GET /admin/eventos-motor retornado.")

        # 3. GET /admin/acciones?universo_id=corte_medieval
        resp_accs = client.get("/api/narrative/admin/acciones?universo_id=corte_medieval", headers=headers)
        assert resp_accs.status_code == 200, f"Error en /acciones: {resp_accs.text}"
        accs = resp_accs.json()
        print(f"[OK] GET /admin/acciones retornado ({len(accs)} acciones en corte_medieval).")

        # 4. POST /admin/acciones (crear accion)
        test_acc_id = "accion_e2e_prueba"
        client.delete(f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval", headers=headers)

        create_payload = {
            "_id": test_acc_id,
            "universo_id": "corte_medieval",
            "nombre": "Accion E2E de Prueba",
            "descripcion": "Verifica mutacion desacoplada desde el panel",
            "primitiva": "modificar_recurso",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1
        }
        resp_cr = client.post("/api/narrative/admin/acciones", json=create_payload, headers=headers)
        assert resp_cr.status_code == 201, f"Error al crear accion: {resp_cr.text}"
        print("[OK] POST /admin/acciones: Accion creada exitosamente.")

        # 5. PUT /admin/acciones con OCC
        resp_occ = client.put(
            f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval",
            json={"nombre": "Accion Editada", "expected_version": 999},
            headers=headers
        )
        assert resp_occ.status_code == 409, "OCC debe rechazar version incorrecta con 409"
        resp_put_ok = client.put(
            f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval",
            json={"nombre": "Accion Editada", "expected_version": 1},
            headers=headers
        )
        assert resp_put_ok.status_code == 200, f"Error al actualizar accion: {resp_put_ok.text}"
        assert resp_put_ok.json()["version"] == 2
        print("[OK] PUT /admin/acciones: OCC verificado (409 rechazo y 200 incremento a v2).")

        # 6. GET /admin/acciones/{id}/usos
        resp_usos = client.get(f"/api/narrative/admin/acciones/{test_acc_id}/usos", headers=headers)
        assert resp_usos.status_code == 200
        assert resp_usos.json()["total_usos"] == 0
        print("[OK] GET /admin/acciones/{id}/usos: Reporta 0 referencias.")

        # 7. GET y PUT /admin/frecuencias
        resp_frec = client.get("/api/narrative/admin/frecuencias?universo_id=corte_medieval", headers=headers)
        assert resp_frec.status_code == 200, f"Error en /frecuencias: {resp_frec.text}"
        frec_data = resp_frec.json()
        items = frec_data["items"]
        v_actual = frec_data["version"]

        resp_frec_occ = client.put(
            "/api/narrative/admin/frecuencias/corte_medieval",
            json={"items": items, "expected_version": 9999},
            headers=headers
        )
        assert resp_frec_occ.status_code == 409, "OCC frecuencias debe responder 409"

        resp_frec_ok = client.put(
            "/api/narrative/admin/frecuencias/corte_medieval",
            json={"items": items, "expected_version": v_actual},
            headers=headers
        )
        assert resp_frec_ok.status_code == 200
        assert resp_frec_ok.json()["version"] == v_actual + 1
        print("[OK] GET y PUT /admin/frecuencias: OCC verificado exitosamente.")

        # 8. GET /admin/frecuencias/{id}/usos
        resp_frec_usos = client.get("/api/narrative/admin/frecuencias/al_obtener/usos?universo_id=corte_medieval", headers=headers)
        assert resp_frec_usos.status_code == 200
        print(f"[OK] GET /admin/frecuencias/al_obtener/usos: {resp_frec_usos.json()['total_usos']} referencias en corte_medieval.")

        # 9. Crear carta con efectos desacoplados multiples
        test_carta_id = "carta_e2e_desacoplada"
        client.delete(f"/api/narrative/admin/cartas/{test_carta_id}", headers=headers)

        carta_payload = {
            "_id": test_carta_id,
            "universo_id": "corte_medieval",
            "categoria": "item",
            "nombre": "Pergamino Real E2E",
            "descripcion": "Carta de prueba con efectos desacoplados y acciones multiples.",
            "imagen": "/assets/narrative/cartas/default.webp",
            "tags": ["e2e_test"],
            "efectos": [
                {
                    "frecuencia_id": "al_obtener",
                    "condiciones": [],
                    "acciones": [
                        {
                            "accion_id": test_acc_id,
                            "parametros": {"clave": "oro", "valor": 35, "tipo_calculo": "fijo"}
                        },
                        {
                            "accion_id": "otorgar_tag",
                            "parametros": {"tag": "e2e_perk_activo"}
                        }
                    ]
                }
            ]
        }

        resp_carta = client.post("/api/narrative/admin/cartas", json=carta_payload, headers=headers)
        assert resp_carta.status_code in (200, 201), f"Error al crear carta: {resp_carta.text}"
        print("[OK] POST /admin/cartas: Carta con acciones desacopladas guardada.")

        # 10. Verificar que ahora la accion reporta 1 uso
        resp_usos_2 = client.get(f"/api/narrative/admin/acciones/{test_acc_id}/usos", headers=headers)
        assert resp_usos_2.status_code == 200
        assert resp_usos_2.json()["total_usos"] == 1, "La accion debe reportar 1 uso tras vincularla"
        print("[OK] Integridad referencial: Accion reporta uso de la carta vinculada.")

        # 11. Intentar eliminar accion referenciada -> debe responder 409
        resp_del_blocked = client.delete(f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval", headers=headers)
        assert resp_del_blocked.status_code == 409, "Eliminar accion en uso debe responder 409"
        print("[OK] Integridad referencial: Eliminacion bloqueada con 409 porque esta en uso.")

        # 12. Cleanup: eliminar carta y luego eliminar accion
        resp_del_carta = client.delete(f"/api/narrative/admin/cartas/{test_carta_id}", headers=headers)
        assert resp_del_carta.status_code in (200, 204)
        resp_del_acc = client.delete(f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval", headers=headers)
        assert resp_del_acc.status_code == 200
        print("[OK] Cleanup completo: Carta y accion eliminadas tras la prueba.")

        # 13. Verificar archivos estaticos del panel admin
        resp_admin_html = client.get("/admin/")
        assert resp_admin_html.status_code == 200
        assert "index-mKOUGd19.js" in resp_admin_html.text
        print("[OK] Admin UI estatico verificado sirviendo el bundle actualizado en /admin/.")

        print("\nTODOS LOS TESTS E2E DEL PANEL Y BACKEND PASARON EXITOSAMENTE.")

if __name__ == "__main__":
    run_tests()
