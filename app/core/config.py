from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Servidor
    PORT: int = 8082
    HOST: str = "0.0.0.0"

    # Base de datos MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "mayores_actualizaciones"

    # JWT & Seguridad (Obligatorio desde .env, debe coincidir con Autenticador)
    JWT_SECRET: str
    JWT_EXPIRATION_DAYS: int = 180
    FRONTEND_URL: str = "http://localhost:5173"

    # Microservicio Autenticador Central (SSOT)
    AUTH_SERVICE_URL: str = "http://localhost:8000"

    # RAE API (Wordle / Desafíos)
    RAE_API_KEY: Optional[str] = None

    # Correo SMTP / Brevo (Opcional)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    MAIL_FROM: Optional[str] = None
    MAIL_FROM_NAME: str = "Mayores Actualizaciones"

    # Administrador por defecto para seed inicial
    ADMIN_DEFAULT_EMAIL: str = "admin@sistemas.com"
    ADMIN_DEFAULT_PASSWORD: str = "admin123"
    ADMIN_DEFAULT_NAME: str = "Operador Sistemas"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
