FROM python:3.12-slim

# Directorio de trabajo en el contenedor
WORKDIR /app

# Prevenir archivos .pyc y habilitar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del proyecto
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente completo
COPY . .

# Exponer el puerto configurado para FastAPI
EXPOSE 8082

# Comando para iniciar la aplicación con Uvicorn en el puerto 8082
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
