from typing import Generic, Sequence, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select

T = TypeVar("T", bound=SQLModel)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, entity_id: int) -> T | None:
        stmt = select(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[T]:
        stmt = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def add(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()


class SoftDeleteRepository(BaseRepository[T]):
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        super().__init__(session, model)

    def _soft_delete_field(self):
        return getattr(self.model, "borrado_en")

    async def get_by_id(self, entity_id: int) -> T | None:
        field = self._soft_delete_field()
        stmt = select(self.model).where(self.model.id == entity_id, field.is_(None))  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[T]:
        field = self._soft_delete_field()
        stmt = select(self.model).where(field.is_(None)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id_including_deleted(self, entity_id: int) -> T | None:
        stmt = select(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def soft_delete(self, entity: T) -> T:
        from datetime import datetime, timezone

        setattr(entity, "borrado_en", datetime.now(timezone.utc))
        self.session.add(entity)
        await self.session.flush()
        return entity
