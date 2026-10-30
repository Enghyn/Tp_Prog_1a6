from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ParametrosPagina(BaseModel):
    pagina: int = Field(default=1, ge=1)
    tamanio: int = Field(default=10, ge=1, le=100)

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


class PageParams(ParametrosPagina):
    """English compatibility constructor for the pagination contract."""

    def __init__(self, *, page: int = 1, size: int = 10, **data: object) -> None:
        super().__init__(pagina=page, tamanio=size, **data)


class Page(Pagina[T], Generic[T]):
    """English compatibility model with English input/output field names."""

    def __init__(
        self,
        *,
        items: list[T],
        total: int,
        page: int | None = None,
        size: int | None = None,
        **data: object,
    ) -> None:
        super().__init__(
            items=items,
            total=total,
            pagina=page if page is not None else data.pop("pagina", None),
            tamanio=size if size is not None else data.pop("tamanio", None),
            **data,
        )

    def model_dump(self, *args: object, **kwargs: object) -> dict[str, object]:
        data = super().model_dump(*args, **kwargs)
        data["page"] = data.pop("pagina")
        data["size"] = data.pop("tamanio")
        return data
