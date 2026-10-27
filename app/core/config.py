from typing import Optional
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Servidor
    PORT: int = 8082
    HOST: str = "0.0.0.0"

    # Base de datos MongoDB (Directa o Desglosada)
    MONGODB_URL: Optional[str] = None
    MONGODB_DB_NAME: str = "mayores_actualizaciones"

    MONGO_HOST: Optional[str] = None
    MONGO_PORT: Optional[int] = 27017
    MONGO_ROOT_USER: Optional[str] = None
    MONGO_ROOT_PASSWORD: Optional[str] = None
    MONGO_AUTH_SOURCE: str = "admin"
    MONGO_DB_NAME: Optional[str] = None

    @property
    def mongodb_connection_url(self) -> str:
        """
        Construye la URL autenticada si se definen las variables desglosadas
        (MONGO_HOST, MONGO_ROOT_USER, etc.), o utiliza MONGODB_URL si está presente.
        """
        if self.MONGO_HOST:
            port = self.MONGO_PORT or 27017
            auth_source = self.MONGO_AUTH_SOURCE or "admin"
            if self.MONGO_ROOT_USER and self.MONGO_ROOT_PASSWORD:
                user_esc = quote_plus(self.MONGO_ROOT_USER)
                pass_esc = quote_plus(self.MONGO_ROOT_PASSWORD)
                return f"mongodb://{user_esc}:{pass_esc}@{self.MONGO_HOST}:{port}/?authSource={auth_source}"
            return f"mongodb://{self.MONGO_HOST}:{port}"
        return self.MONGODB_URL or "mongodb://localhost:27017"

    @property
    def effective_db_name(self) -> str:
        return self.MONGO_DB_NAME or self.MONGODB_DB_NAME

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
