import asyncio
import logging
import pytest
from fastapi import BackgroundTasks
from app.core.notificaciones import BackgroundTasksNotifier


@pytest.mark.asyncio
async def test_notificacion_se_ejecuta_y_loguea(caplog):
    background_tasks = BackgroundTasks()
    notifier = BackgroundTasksNotifier(background_tasks)
    
    with caplog.at_level(logging.INFO):
        notifier.notificar_orden_terminada(orden_id=123, email="cliente@test.com", total=1500.0)
        # Ejecutar tareas en background
        for task in background_tasks.tasks:
            await task.func(*task.args, **task.kwargs)
    
    assert any("orden terminada" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_notificacion_no_bloquea_respuesta():
    background_tasks = BackgroundTasks()
    notifier = BackgroundTasksNotifier(background_tasks)
    
    # Agendar debe ser inmediato
    notifier.notificar_orden_terminada(orden_id=456)
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_fallo_en_tarea_no_altera_respuesta():
    from app.core import notificaciones
    
    async def tarea_con_error(orden_id, email=None, total=None):
        raise ValueError("Error simulado")
    
    original = notificaciones._enviar_notificacion_orden_terminada
    notificaciones._enviar_notificacion_orden_terminada = tarea_con_error
    
    try:
        background_tasks = BackgroundTasks()
        notifier = BackgroundTasksNotifier(background_tasks)
        notifier.notificar_orden_terminada(orden_id=789)
        for task in background_tasks.tasks:
            await task.func(*task.args, **task.kwargs)  # No debe lanzar excepción
        assert True
    finally:
        notificaciones._enviar_notificacion_orden_terminada = original
