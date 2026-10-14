from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Servidor
    PORT: int = 8082
    HOST: str = "0.0.0.0"
    
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "mayores_actualizaciones"
    
    # JWT & Seguridad
    JWT_SECRET: str = "c2VjcmV0LWtleS1mb3ItbWF5b3Jlcy1hY3R1YWxpemFjaW9uZXMtYmFja2VuZC0yMDI2LXNpcGk="
    JWT_EXPIRATION_DAYS: int = 180
    FRONTEND_URL: str = "http://localhost:5173"
    
    # SMTP / Brevo
    SMTP_HOST: str = "smtp-relay.brevo.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "bac8ec001@smtp-brevo.com"
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = "nfernandezcoopya@gmail.com"
    MAIL_FROM_NAME: str = "Mayores Actualizaciones"
    
    # Administrador por defecto
    ADMIN_DEFAULT_EMAIL: str = "admin@sistemas.com"
    ADMIN_DEFAULT_PASSWORD: str = "admin123"
    ADMIN_DEFAULT_NAME: str = "Operador Sistemas"
    
    # RAE API
    RAE_API_KEY: Optional[str] = ""

    # MySQL (solo para script ETL)
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_DATABASE: str = "prueba2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
