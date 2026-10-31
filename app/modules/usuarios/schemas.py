import re
import email_validator

if "local" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES = [
        d for d in email_validator.SPECIAL_USE_DOMAIN_NAMES if d != "local"
    ]

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


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


def validar_complejidad_password(valor: str) -> str:
    """
    Exige al menos una mayúscula ASCII, una minúscula ASCII y un dígito (D7).

    Vive en `schemas.py` y no en `seguridad.py` para no mezclar validación de
    contrato con el módulo criptográfico. No normaliza: devuelve el valor tal cual.
    """
    if re.search(r"[A-Z]", valor) is None:
        raise ValueError("La contraseña debe incluir al menos una mayúscula")
    if re.search(r"[a-z]", valor) is None:
        raise ValueError("La contraseña debe incluir al menos una minúscula")
    if re.search(r"[0-9]", valor) is None:
        raise ValueError("La contraseña debe incluir al menos un dígito")
    return valor


class SolicitudCambioPassword(BaseModel):
    """
    Contrato de `POST /auth/cambiar-password` (D7).

    Las contraseñas no se normalizan con `strip`: los espacios son parte del
    secreto y deben compararse tal cual.
    """

    model_config = ConfigDict(extra="forbid")

    password_actual: str = Field(min_length=1, max_length=72)
    password_nueva: str = Field(min_length=8, max_length=72)

    @field_validator("password_nueva")
    @classmethod
    def validar_complejidad(cls, valor: str) -> str:
        return validar_complejidad_password(valor)

    @model_validator(mode="after")
    def validar_distinta_de_la_actual(self) -> "SolicitudCambioPassword":
        if self.password_nueva == self.password_actual:
            raise ValueError("La contraseña nueva debe ser distinta de la actual")
        return self


class RespuestaCambioPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str = "Contraseña actualizada"
