"""Configuración de la aplicación.

Re-exporta la configuración canónica de `configuracion.py` para cumplir con la
estructura obligatoria del TP (`app/core/config.py`) sin duplicar la definición.
"""

from app.core.configuracion import *  # noqa: F401, F403
from app.core.configuracion import (
    Configuracion,
    configuracion,
    Settings,
    settings,
)

# Alias de compatibilidad con la convención del enunciado.
Config = Configuracion
config = configuracion
