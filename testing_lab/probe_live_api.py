"""
testing_lab/probe_live_api.py
Realiza pruebas HTTP dinámicas reales contra el servidor FastAPI activo en http://127.0.0.1:8090
para verificar:
1. Introspección completa de OpenAPI (rutas activas por tag).
2. Comprobación funcional de rutas de cursos (/progreso).
3. Comprobación funcional de rutas de usuario (/usuario).
4. Comprobación de rutas de narrativa V1 vs V2.
5. Comprobación de endpoints de juegos y economía.
"""

import urllib.request
import urllib.error
import json
import os

BASE_URL = "http://127.0.0.1:8090"

def fetch(path, method="GET", data=None, headers=None):
    url = f"{BASE_URL}{path}"
    req_headers = {"User-Agent": "TestingLabProbe/1.0"}
    if headers:
        req_headers.update(headers)
    
    encoded_data = None
    if data is not None:
        if isinstance(data, dict):
            encoded_data = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, str):
            encoded_data = data.encode("utf-8")

    req = urllib.request.Request(url, data=encoded_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
            try:
                parsed_json = json.loads(body)
            except Exception:
                parsed_json = body
            return response.status, parsed_json, dict(response.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed_json = json.loads(body)
        except Exception:
            parsed_json = body
        return e.code, parsed_json, dict(e.headers)
    except Exception as e:
        return 0, str(e), {}

def main():
    print(f"=== PROBE LIVE API: {BASE_URL} ===\n")
    
    # 1. Obtener OpenAPI
    status, openapi, _ = fetch("/openapi.json")
    if status != 200 or not isinstance(openapi, dict):
        print(f"ERROR: No se pudo obtener /openapi.json (Status: {status})")
        return

    paths = openapi.get("paths", {})
    title = openapi.get("info", {}).get("title")
    version = openapi.get("info", {}).get("version")
    print(f"OpenAPI cargado exitosamente: '{title}' v{version} - Total endpoints: {len(paths)}\n")

    # Clasificar endpoints por tags y familias
    endpoints_by_tag = {}
    deprecated_endpoints = []
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                tags = details.get("tags", ["Untagged"])
                is_deprecated = details.get("deprecated", False)
                summary = details.get("summary", "")
                
                for t in tags:
                    endpoints_by_tag.setdefault(t, []).append({
                        "method": method.upper(),
                        "path": path,
                        "summary": summary,
                        "deprecated": is_deprecated
                    })
                if is_deprecated:
                    deprecated_endpoints.append({
                        "method": method.upper(),
                        "path": path,
                        "summary": summary
                    })

    print("--- ENDPOINTS POR FAMILIA / TAG EN EL SERVIDOR VIVO ---")
    for tag, ep_list in sorted(endpoints_by_tag.items()):
        print(f"Tag: [{tag}] ({len(ep_list)} endpoints)")
        for ep in ep_list:
            depr_marker = " [DEPRECATED]" if ep["deprecated"] else ""
            print(f"  {ep['method']:<6} {ep['path']}{depr_marker}")

    # 2. Pruebas reales de endpoints candidatos a eliminación
    print("\n--- PRUEBAS REALES HTTP ---")
    
    # A. Cursos (/progreso)
    print("\n1. Probando rutas de CURSOS (/progreso):")
    status_p1, body_p1, _ = fetch("/progreso/obtenerUsuario/1")
    print(f"  GET /progreso/obtenerUsuario/1 -> Status: {status_p1} (Respuesta: {body_p1})")
    
    status_p2, body_p2, _ = fetch("/progreso/crear", method="POST", data={"usuarioId": 1, "cursoId": 999})
    print(f"  POST /progreso/crear -> Status: {status_p2} (Respuesta: {body_p2})")

    # B. Estados de usuario (/usuario)
    print("\n2. Probando rutas de ESTADOS DE USUARIO (/usuario):")
    status_u1, body_u1, _ = fetch("/usuario")
    print(f"  GET /usuario -> Status: {status_u1} (Respuesta: {body_u1})")

    status_u2, body_u2, _ = fetch("/usuario/estados")
    print(f"  GET /usuario/estados -> Status: {status_u2}")
    if isinstance(body_u2, dict) and "estados" in body_u2:
        print(f"    Total estados devueltos: {len(body_u2['estados'])}")

    # C. Narrativa V1 vs V2
    print("\n3. Probando rutas de NARRATIVA V1 (Planos/Deprecados):")
    status_n1, body_n1, _ = fetch("/api/narrative/partida/evento-actual?date=2026-11-05")
    print(f"  GET /api/narrative/partida/evento-actual -> Status: {status_n1} (Respuesta: {body_n1})")

    status_n2, body_n2, _ = fetch("/api/narrative/v2/partida/decidir-evento", method="POST", data={"date": "2026-11-05", "opcion_id": "op_1"})
    print(f"  POST /api/narrative/v2/partida/decidir-evento -> Status: {status_n2} (Respuesta: {body_n2})")

    # D. Rutas de Juegos Clásicos y Economía (Vigentes)
    print("\n4. Probando rutas VIGENTES de Juegos y Economía:")
    status_e1, body_e1, _ = fetch("/api/economy/config")
    print(f"  GET /api/economy/config -> Status: {status_e1} (Success: {isinstance(body_e1, dict) and 'calificaciones' in body_e1})")

    status_c1, body_c1, _ = fetch("/api/challenges/today?game=wordle")
    print(f"  GET /api/challenges/today?game=wordle -> Status: {status_c1}")

    # Guardar reporte
    output_path = os.path.join(os.path.dirname(__file__), "live_api_probe_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "endpoints_by_tag": endpoints_by_tag,
            "deprecated_endpoints": deprecated_endpoints
        }, f, indent=2)
    print(f"\nReporte live exportado a: {output_path}")

if __name__ == "__main__":
    main()
