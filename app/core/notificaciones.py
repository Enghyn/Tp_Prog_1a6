import asyncio
import logging
from typing import Protocol

from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)


class NotificadorCliente(Protocol):
    def notificar_orden_terminada(self, orden_id: int) -> None:
        ...


class BackgroundTasksNotifier:
    def __init__(self, background_tasks: BackgroundTasks | None = None):
        self.background_tasks = background_tasks

    def notificar_orden_terminada(self, orden_id: int, email: str | None = None, total: float | None = None) -> None:
        if self.background_tasks is not None:
            self.background_tasks.add_task(_enviar_notificacion_orden_terminada, orden_id, email, total)
        else:
            asyncio.create_task(_enviar_notificacion_orden_terminada(orden_id, email, total))


async def _enviar_notificacion_orden_terminada(orden_id: int, email: str | None = None, total: float | None = None) -> None:
    try:
        await asyncio.sleep(0.5)
        logger.info(
            "Notificación enviada para orden terminada",
            extra={"orden_id": orden_id, "email": email, "total": total},
        )
    except Exception as e:
        logger.exception("Error al enviar notificación para orden %s: %s", orden_id, e)


# Alias para compatibilidad
Notificador = NotificadorCliente
NotificadorBackgroundTasks = BackgroundTasksNotifier
enviar_notificacion_orden_terminada = _enviar_notificacion_orden_terminada
