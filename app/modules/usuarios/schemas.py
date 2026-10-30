from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SolicitudLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return v.strip().lower()


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    email: str
    nombre: str
    debe_cambiar_password: bool


class TokenInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iat: str
    exp: int


class RespuestaSesion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: UsuarioPublico
    roles: list[str]
    token: TokenInfo


class RespuestaLogout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str = "Sesión cerrada"
