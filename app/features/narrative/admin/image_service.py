"""
image_service.py
Servicio de optimización y procesamiento de imágenes para la Torre de Control.
Convierte formatos JPG/PNG a WebP con redimensionamiento proporcional por categoría.
"""

import os
import re
import uuid
import io
import logging
from PIL import Image
from fastapi import UploadFile, HTTPException
from typing import Dict, Any

logger = logging.getLogger(__name__)

CATEGORIAS_VALIDAS = {
    "universos",
    "personajes",
    "cartas",
    "eventos",
    "resultados",
    "conversaciones",
    "finalizaciones"
}

DIMENSIONES_MAX = {
    "universos": (1200, 600),
    "personajes": (600, 750),
    "cartas": (450, 630),
    "eventos": (900, 500),
    "resultados": (900, 500),
    "conversaciones": (900, 500),
    "finalizaciones": (900, 500)
}

async def procesar_y_guardar_imagen_narrativa(
    file: UploadFile,
    categoria: str
) -> Dict[str, Any]:
    """
    Procesa un archivo de imagen subido, lo redimensiona según su categoría
    y lo comprime en formato WebP con calidad 82 en la carpeta estática correspondiente.
    """
    cat_lower = categoria.lower().strip()
    if cat_lower not in CATEGORIAS_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Categoría '{categoria}' inválida. Debe ser una de: {sorted(list(CATEGORIAS_VALIDAS))}"
        )

    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo enviado está vacío.")

    try:
        img = Image.open(io.BytesIO(contenido))
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"No se pudo decodificar la imagen: {ex}")

    max_size = DIMENSIONES_MAX.get(cat_lower, (900, 500))
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    nombre_original = os.path.splitext(file.filename or "imagen")[0]
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", nombre_original).strip("_").lower()[:30]
    uuid_tag = uuid.uuid4().hex[:6]
    nombre_final = f"{slug}_{uuid_tag}.webp"

    dir_destino = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "narrative", cat_lower)
    )
    os.makedirs(dir_destino, exist_ok=True)
    ruta_guardado = os.path.join(dir_destino, nombre_final)

    try:
        img.save(ruta_guardado, "WEBP", quality=82, method=6)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Error al guardar la imagen en disco: {ex}")

    url_relativa = f"/assets/narrative/{cat_lower}/{nombre_final}"
    tamano_kb = round(os.path.getsize(ruta_guardado) / 1024, 1)

    return {
        "success": True,
        "url": url_relativa,
        "filename": nombre_final,
        "categoria": cat_lower,
        "size_kb": tamano_kb,
        "dimensions": f"{img.width}x{img.height}"
    }
