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
    print("=== LIVE E2E TEST: ADMIN PANEL, MUTAR ESTADO & CONDICIONES APARICION ===")
    token = create_access_token({"id": 1, "sub": "1", "email": "admin@autenticador.com", "tipo_usuario": 2, "rol": "administrador", "name": "Administrador Central", "activo": True})
    headers = {"Authorization": f"Bearer {token}"}
    print("[OK] Token de Administrador generado con firma JWT valida.")

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # 1. GET /admin/operaciones (debe incluir mutar_estado)
        resp_ops = client.get("/api/narrative/admin/operaciones", headers=headers)
        assert resp_ops.status_code == 200, f"Error en /operaciones: {resp_ops.text}"
        ops = resp_ops.json()
        assert any(op["primitiva"] == "mutar_estado" for op in ops), "Debe incluir la primitiva 'mutar_estado'"
        print(f"[OK] GET /admin/operaciones retornado ({len(ops)} primitivas, incluye mutar_estado).")

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
        assert any(a["primitiva"] == "mutar_estado" for a in accs), "Debe existir al menos una acción con primitiva mutar_estado"
        print(f"[OK] GET /admin/acciones retornado ({len(accs)} acciones en corte_medieval).")

        # 4. POST /admin/acciones (crear accion con mutar_estado)
        test_acc_id = "accion_e2e_mutar_estado"
        client.delete(f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval", headers=headers)

        create_payload = {
            "_id": test_acc_id,
            "universo_id": "corte_medieval",
            "nombre": "Accion E2E Mutar Estado",
            "descripcion": "Verifica mutación matemática genérica",
            "primitiva": "mutar_estado",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1
        }
        resp_cr = client.post("/api/narrative/admin/acciones", json=create_payload, headers=headers)
        assert resp_cr.status_code == 201, f"Error al crear accion: {resp_cr.text}"
        print("[OK] POST /admin/acciones: Accion con mutar_estado creada exitosamente.")

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
        print("[OK] GET /admin/acciones/{id}/usos: Reporta 0 referencias iniciales.")

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

        # 8. POST /admin/cartas con condiciones_aparicion y mutar_estado
        test_carta_id = "carta_e2e_mutar_cond"
        client.delete(f"/api/narrative/admin/cartas/{test_carta_id}", headers=headers)

        carta_payload = {
            "_id": test_carta_id,
            "universo_id": "corte_medieval",
            "categoria": "bonus",
            "nombre": "Bendición Real Multiplicativa",
            "descripcion": "Multiplica los recursos si el oro >= 60.",
            "imagen": "/assets/narrative/cartas/default.webp",
            "tags": ["e2e_test"],
            "condiciones_aparicion": [
                {
                    "tipo": "comparar_recurso",
                    "clave": "oro",
                    "operador": ">=",
                    "valor": 50
                }
            ],
            "efectos": [
                {
                    "frecuencia_id": "al_obtener",
                    "condiciones": [],
                    "acciones": [
                        {
                            "accion_id": test_acc_id,
                            "parametros": {
                                "ruta": "recursos.oro",
                                "operacion_matematica": "multiplicar",
                                "valor": 1.5
                            }
                        }
                    ]
                }
            ]
        }

        resp_carta = client.post("/api/narrative/admin/cartas", json=carta_payload, headers=headers)
        assert resp_carta.status_code in (200, 201), f"Error al crear carta: {resp_carta.text}"
        data_carta = resp_carta.json()
        assert len(data_carta.get("condiciones_aparicion", [])) == 1
        print("[OK] POST /admin/cartas: Carta con condiciones_aparicion y mutar_estado guardada.")

        # 9. POST /admin/personajes con condiciones_aparicion
        test_pj_id = "pj_e2e_condicional"
        client.delete(f"/api/narrative/admin/personajes/{test_pj_id}", headers=headers)

        pj_payload = {
            "_id": test_pj_id,
            "universo_id": "corte_medieval",
            "nombre": "Almirante del Norte E2E",
            "titulo": "Señor de los Mares",
            "imagen": "/assets/narrative/personajes/default.webp",
            "descripcion": "Personaje con condiciones de aparicion.",
            "afinidad_inicial": 55,
            "pros": ["Gran flota"],
            "cons": ["Costoso"],
            "tags": ["maritimo"],
            "condiciones_aparicion": [
                {
                    "tipo": "tiene_tag",
                    "tag": "puerto_abierto"
                }
            ],
            "efectos": []
        }

        resp_pj = client.post("/api/narrative/admin/personajes", json=pj_payload, headers=headers)
        assert resp_pj.status_code in (200, 201), f"Error al crear personaje: {resp_pj.text}"
        data_pj = resp_pj.json()
        assert len(data_pj.get("condiciones_aparicion", [])) == 1
        print("[OK] POST /admin/personajes: Personaje con condiciones_aparicion guardado.")

        # 10. Integridad referencial: Verificar uso reportado por la carta
        resp_usos_2 = client.get(f"/api/narrative/admin/acciones/{test_acc_id}/usos", headers=headers)
        assert resp_usos_2.status_code == 200
        assert resp_usos_2.json()["total_usos"] == 1
        print("[OK] Integridad referencial: Accion mutar_estado reporta uso de la carta.")

        # 11. Intentar eliminar accion referenciada -> debe responder 409
        resp_del_blocked = client.delete(f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval", headers=headers)
        assert resp_del_blocked.status_code == 409, "Eliminar accion en uso debe responder 409"
        print("[OK] Integridad referencial: Eliminacion bloqueada con 409 porque esta en uso.")

        # 12. Cleanup: eliminar carta, personaje y accion
        resp_del_carta = client.delete(f"/api/narrative/admin/cartas/{test_carta_id}", headers=headers)
        assert resp_del_carta.status_code in (200, 204)
        resp_del_pj = client.delete(f"/api/narrative/admin/personajes/{test_pj_id}", headers=headers)
        assert resp_del_pj.status_code in (200, 204)
        resp_del_acc = client.delete(f"/api/narrative/admin/acciones/{test_acc_id}?universo_id=corte_medieval", headers=headers)
        assert resp_del_acc.status_code == 200
        print("[OK] Cleanup completo: Carta, personaje y accion eliminados tras la prueba.")

        # 13. Verificar archivos estáticos del panel admin
        resp_admin_html = client.get("/admin/")
        assert resp_admin_html.status_code == 200
        assert "/admin/assets/index-" in resp_admin_html.text
        print("[OK] Admin UI estático verificado sirviendo el bundle compilado en /admin/.")

        print("\n=== TODOS LOS TESTS E2E DEL PANEL Y BACKEND PASARON EXITOSAMENTE (13/13) ===")

if __name__ == "__main__":
    run_tests()
