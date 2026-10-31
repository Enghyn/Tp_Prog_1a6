from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """Async context manager grouping repositories over a single session.

    Commit/rollback are owned here; the session is never closed (owned by
    `get_session`). Repositories only flush.
    """

    def __init__(
        self,
        session: AsyncSession,
        repository_factories: dict[str, Callable[[AsyncSession], Any]] | None = None,
    ) -> None:
        self.session = session
        self._factories = repository_factories or {}
        self._cache: dict[str, Any] = {}

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
        # do not close session

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    def __getattr__(self, name: str) -> Any:
        # lazy repository exposure via factories
        if name.startswith("_"):
            raise AttributeError(name)
        factories = self.__dict__.get("_factories", {})
        if name in factories:
            cache = self.__dict__.get("_cache", {})
            if name not in cache:
                cache[name] = factories[name](self.session)
            return cache[name]
        raise AttributeError(name)