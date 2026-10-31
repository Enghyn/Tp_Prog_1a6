import re
from datetime import datetime, timezone
from typing import Literal

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


def normalizar_email_valor(valor: str) -> str:
    """
    Normaliza un email a minúsculas y sin espacios (D3, D4).

    Vive acá para que el login y el alta de personal compartan exactamente la
    misma regla: un email guardado nunca varía por capitalización.
    """
    return valor.strip().lower()


class SolicitudLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return normalizar_email_valor(v)


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


class SolicitudAltaUsuario(BaseModel):
    """
    Contrato de `POST /usuarios` (D3).

    El email se normaliza igual que en el login; el nombre se recorta y no
    puede quedar vacío; la contraseña provisoria exige 8..72 caracteres con
    mayúscula, minúscula y dígito.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        return normalizar_email_valor(valor)

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        recortado = valor.strip()
        if not recortado:
            raise ValueError("El nombre no puede estar vacío")
        return recortado

    @field_validator("password")
    @classmethod
    def validar_complejidad(cls, valor: str) -> str:
        return validar_complejidad_password(valor)


class UsuarioCreado(BaseModel):
    """Respuesta del alta de personal (D3): nunca incluye la contraseña."""

    model_config = ConfigDict(extra="forbid")

    id: int
    email: str
    nombre: str
    activo: bool
    debe_cambiar_password: bool


class AsignacionRolPublica(BaseModel):
    """
    Asignación tal como la ve el administrador (D5).

    `otorgada_por` se expone como `id` del administrador para no navegar la
    relación `otorgado_por_usuario` (regla dura #3). `vigente` la calcula el
    service con un único `ahora` por request.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    rol: str
    desde: datetime
    vence_en: datetime | None
    revocada_en: datetime | None
    otorgada_por: int | None
    vigente: bool


class HistorialRoles(BaseModel):
    """Historial completo de asignaciones de un usuario (D5)."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: int
    asignaciones: list[AsignacionRolPublica]


# Catálogo cerrado de roles: espejo del CHECK `ck_asignacion_rol_valido`.
RolValido = Literal["ADMIN", "RECEPCION", "MECANICO", "CLIENTE"]


class SolicitudAsignacionRol(BaseModel):
    """
    Contrato de `POST /usuarios/{id}/roles` (D6).

    Sólo `rol` y `vence_en`: `otorgada_por` y `desde` los fija el servidor.
    El vencimiento debe traer zona horaria y ser estrictamente futuro; en
    ambos casos Pydantic responde `422 ERROR_VALIDACION`.
    """

    model_config = ConfigDict(extra="forbid")

    rol: RolValido
    vence_en: datetime | None = None

    @field_validator("vence_en")
    @classmethod
    def validar_vencimiento(cls, valor: datetime | None) -> datetime | None:
        if valor is None:
            return None
        if valor.tzinfo is None or valor.tzinfo.utcoffset(valor) is None:
            raise ValueError("El vencimiento debe incluir zona horaria")
        if valor <= datetime.now(timezone.utc):
            raise ValueError("El vencimiento debe ser estrictamente futuro")
        return valor
