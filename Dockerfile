FROM python:3.12-slim

# 1. Crear usuario de sistema sin privilegios
RUN useradd -m -r -u 10001 -s /bin/bash appuser

# Directorio de trabajo en el contenedor
WORKDIR /app

# Prevenir archivos .pyc y habilitar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del proyecto
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente completo y ceder la propiedad a appuser
COPY . .
RUN chown -R appuser:appuser /app

# Conmutar a usuario no-root
USER appuser

# Exponer el puerto configurado para FastAPI
EXPOSE 8082

# Comando para iniciar la aplicación con Uvicorn en el puerto 8082
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
