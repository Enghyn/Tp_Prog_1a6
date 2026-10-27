from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ParametrosPagina(BaseModel):
    pagina: int = Field(default=1, ge=1)
    tamanio: int = Field(default=10, ge=1, le=100)

    # Alias para compatibilidad
    @property
    def page(self) -> int:
        return self.pagina

    @property
    def size(self) -> int:
        return self.tamanio


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    pagina: int
    tamanio: int

    @property
    def page(self) -> int:
        return self.pagina

    @property
    def size(self) -> int:
        return self.tamanio


# Alias para compatibilidad
PageParams = ParametrosPagina
Page = Pagina
