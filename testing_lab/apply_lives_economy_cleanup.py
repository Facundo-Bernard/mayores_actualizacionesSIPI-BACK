"""
Script para aplicar la limpieza del sistema de vidas y mini-tienda en backend:
- Elimina BuyLivesRequest, BuyLivesResponse y TiendaPaquete
- Remueve /api/economy/buy-lives del router
- Remueve buy_lives de lives.py y service.py
- Remueve costo_vida_puntos, paquetes_tienda y vidas_maximas de config.py y schemas.py
- Limpia tests en test_economy_fase1.py
"""

import os
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMAS_PATH = os.path.join(BASE_DIR, "app", "features", "economy", "schemas.py")
CONFIG_PATH = os.path.join(BASE_DIR, "app", "features", "economy", "config.py")
LIVES_PATH = os.path.join(BASE_DIR, "app", "features", "economy", "lives.py")
ROUTER_PATH = os.path.join(BASE_DIR, "app", "features", "economy", "router.py")
SERVICE_PATH = os.path.join(BASE_DIR, "app", "features", "economy", "service.py")
TESTS_PATH = os.path.join(BASE_DIR, "tests", "contract", "test_economy_fase1.py")

def clean_schemas():
    with open(SCHEMAS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Remove TiendaPaquete
    content = re.sub(
        r"class TiendaPaquete\(BaseModel\):.*?(?=class EscalaCalificacionTiempo)",
        "",
        content,
        flags=re.DOTALL
    )

    # 2. Clean EconomyConfigResponse
    content = re.sub(
        r"    costo_vida_puntos: int = Field\(50, ge=1, description=\"[^\"]*\"\)\n",
        "",
        content
    )
    content = re.sub(
        r"    paquetes_tienda: List\[TiendaPaquete\] = Field\(default_factory=list, description=\"[^\"]*\"\)\n",
        "",
        content
    )
    content = re.sub(
        r"    vidas_maximas: Optional\[int\] = Field\(None, description=\"[^\"]*\"\)\n",
        "",
        content
    )

    # 3. Clean EconomyConfigUpdateRequest
    content = re.sub(
        r"    costo_vida_puntos: Optional\[int\] = Field\(None, ge=1, description=\"[^\"]*\"\)\n",
        "",
        content
    )
    content = re.sub(
        r"    paquetes_tienda: Optional\[List\[TiendaPaquete\]\] = None\n",
        "",
        content
    )
    content = re.sub(
        r"    vidas_maximas: Optional\[int\] = None\n",
        "",
        content
    )

    # 4. Remove BuyLivesRequest and BuyLivesResponse
    content = re.sub(
        r"class BuyLivesRequest\(BaseModel\):.*?(?=class RefillLivesResponse)",
        "",
        content,
        flags=re.DOTALL
    )

    with open(SCHEMAS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] schemas.py actualizado.")

def clean_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove TiendaPaquete from imports
    content = re.sub(r",\s*TiendaPaquete", "", content)

    # Remove fields from DEFAULT_ECONOMY_CONFIG
    content = re.sub(r"    \"costo_vida_puntos\": 50,\n", "", content)
    content = re.sub(r"    \"vidas_maximas\": None,\n", "", content)
    content = re.sub(
        r"    \"paquetes_tienda\": \[\s*\{.*?\}\s*\],\n",
        "",
        content,
        flags=re.DOTALL
    )

    # In get_economy_config(): remove paquetes parsing and params
    content = re.sub(
        r"    paquetes = \[TiendaPaquete\(\*\*p\) for p in doc\.get\(\"paquetes_tienda\", \[\]\)\]\n",
        "",
        content
    )
    content = re.sub(
        r"        costo_vida_puntos=int\(doc\.get\(\"costo_vida_puntos\", 50\)\),\n",
        "",
        content
    )
    content = re.sub(
        r"        paquetes_tienda=paquetes,\n",
        "",
        content
    )
    content = re.sub(
        r"        vidas_maximas=doc\.get\(\"vidas_maximas\"\),\n",
        "",
        content
    )

    # In update_economy_config(): remove update_fields for costo_vida_puntos, paquetes_tienda, vidas_maximas
    content = re.sub(
        r"    if req\.costo_vida_puntos is not None:\s*update_fields\[\"costo_vida_puntos\"\] = max\(1, req\.costo_vida_puntos\)\n",
        "",
        content
    )
    content = re.sub(
        r"    if req\.paquetes_tienda is not None:\s*update_fields\[\"paquetes_tienda\"\] = \[p\.model_dump\(\) for p in req\.paquetes_tienda\]\n",
        "",
        content
    )
    content = re.sub(
        r"    if req\.vidas_maximas is not None:\s*update_fields\[\"vidas_maximas\"\] = req\.vidas_maximas\n",
        "",
        content
    )

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] config.py actualizado.")

def clean_lives():
    with open(LIVES_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove BuyLives imports
    content = re.sub(r"    BuyLivesRequest,\n", "", content)
    content = re.sub(r"    BuyLivesResponse,\n", "", content)

    # Remove buy_lives function
    content = re.sub(
        r"async def buy_lives\(user_id: int, req: BuyLivesRequest\) -> BuyLivesResponse:.*?(?=async def refill_lives)",
        "",
        content,
        flags=re.DOTALL
    )

    with open(LIVES_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] lives.py actualizado.")

def clean_router():
    with open(ROUTER_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove BuyLives from imports
    content = re.sub(r"    BuyLivesRequest,\n", "", content)
    content = re.sub(r"    BuyLivesResponse,\n", "", content)
    content = re.sub(r"    buy_lives,\n", "", content)

    # Remove buy_lives endpoint
    content = re.sub(
        r"@router\.post\(\s*\"/api/economy/buy-lives\",.*?(?=@router\.post\(\s*\"/api/economy/refill-lives\")",
        "",
        content,
        flags=re.DOTALL
    )

    with open(ROUTER_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] router.py actualizado.")

def clean_service():
    with open(SERVICE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove buy_lives
    content = re.sub(r"    buy_lives,\n", "", content)

    with open(SERVICE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] service.py actualizado.")

def clean_tests():
    with open(TESTS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove test_buy_lives_applies_vidas_maximas_atomically and test_buy_lives_ignores_legacy_direct_quantity
    content = re.sub(
        r"@pytest\.mark\.asyncio\s*async def test_buy_lives_applies_vidas_maximas_atomically\(.*?(?=@pytest\.mark\.asyncio\s*async def test_admin_adjust_is_atomic_and_audited)",
        "",
        content,
        flags=re.DOTALL
    )

    with open(TESTS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] test_economy_fase1.py actualizado.")

if __name__ == "__main__":
    clean_schemas()
    clean_config()
    clean_lives()
    clean_router()
    clean_service()
    clean_tests()
