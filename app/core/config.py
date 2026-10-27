from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/taller_mecanico"
    jwt_secret: str
    access_token_ttl_min: int = 60
    bcrypt_max_concurrency: int = 4
    login_max_intentos: int = 5
    login_ventana_seg: int = 60
    entorno: str = "dev"

    @field_validator("jwt_secret")
    @classmethod
    def validar_jwt_secret(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("JWT_SECRET debe estar configurado y no puede estar vacío")
        return v


configuracion = Configuracion()

# Alias para compatibilidad
Settings = Configuracion
settings = configuracion
