from typing import Optional, List
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Servidor
    PORT: int = 8087
    HOST: str = "0.0.0.0"

    # Base de datos MongoDB (Desglosada o Directa)
    MONGO_HOST: Optional[str] = None
    MONGO_PORT: Optional[int] = 27017
    MONGO_ROOT_USER: Optional[str] = None
    MONGO_ROOT_PASSWORD: Optional[str] = None
    MONGO_AUTH_SOURCE: str = "admin"
    MONGO_DB_NAME: Optional[str] = None

    MONGO_URI: Optional[str] = None
    MONGODB_URL: Optional[str] = None
    MONGODB_DB_NAME: str = "cognijuegos_db"

    @property
    def mongodb_connection_url(self) -> str:
        """
        Construye la URL autenticada de conexión a MongoDB.
        Prioriza la configuración desglosada explícita (MONGO_HOST, MONGO_ROOT_USER, etc.),
        seguida de MONGO_URI o MONGODB_URL.
        """
        if self.MONGO_HOST:
            port = self.MONGO_PORT or 27017
            auth_source = self.MONGO_AUTH_SOURCE or "admin"
            db_name = self.effective_db_name
            if self.MONGO_ROOT_USER and self.MONGO_ROOT_PASSWORD:
                user_esc = quote_plus(self.MONGO_ROOT_USER)
                pass_esc = quote_plus(self.MONGO_ROOT_PASSWORD)
                return f"mongodb://{user_esc}:{pass_esc}@{self.MONGO_HOST}:{port}/{db_name}?authSource={auth_source}"
            return f"mongodb://{self.MONGO_HOST}:{port}/{db_name}"
        if self.MONGO_URI:
            return self.MONGO_URI
        if self.MONGODB_URL:
            return self.MONGODB_URL
        return "mongodb://localhost:27017"

    @property
    def effective_db_name(self) -> str:
        return self.MONGO_DB_NAME or self.MONGODB_DB_NAME or "cognijuegos_db"

    # JWT & Seguridad (Obligatorio desde .env, debe coincidir con Autenticador)
    JWT_SECRET: str = ""
    JWT_SECRET_FALLBACK: Optional[str] = None
    JWT_EXPIRATION_DAYS: int = 180
    FRONTEND_URL: str = "http://localhost:5173"

    # Microservicio Autenticador Central (SSOT)
    AUTH_SERVICE_URL: str = "http://localhost:8000"
    SERVICE_KEY: str = "cognijuegos"

    # Dominios autorizados para CORS (Sin comodines *)
    CORS_ORIGINS: str = (
        "https://cognijuegos.asistodo.com.ar,"
        "https://autenticacion.asistodo.com.ar,"
        "https://mayoresactualizaciones.asistodo.com.ar,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL:
            fe_url = self.FRONTEND_URL.rstrip("/")
            if fe_url and fe_url not in origins:
                origins.append(fe_url)
        if self.AUTH_SERVICE_URL:
            auth_url = self.AUTH_SERVICE_URL.rstrip("/")
            if auth_url and auth_url not in origins:
                origins.append(auth_url)
        return origins

    # Validación server-side de resultados por juego (Fase 2). Off hasta observar.
    GRADING_ENFORCE_WORDLE: bool = False
    GRADING_ENFORCE_SOPA: bool = False
    GRADING_ENFORCE_SUDOKU: bool = False
    GRADING_ENFORCE_CRUCIGRAMA: bool = False

    # Siembra del contenido V2 al arrancar. Opt-in hasta completar el dry-run de readiness.
    SEED_NARRATIVE_V2: bool = False

    # RAE API (Wordle / Desafíos)
    RAE_API_KEY: Optional[str] = None

    # Correo SMTP / Brevo (Opcional)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    MAIL_FROM: Optional[str] = None
    MAIL_FROM_NAME: str = "Mayores Actualizaciones"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
