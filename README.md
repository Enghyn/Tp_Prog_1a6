# API Taller Mecánico

API REST para la gestión de un taller mecánico desarrollada con FastAPI, SQLModel y PostgreSQL.

## Tecnologías

- Python 3.12
- FastAPI 0.111
- SQLModel 0.0.24
- SQLAlchemy 2.0 (async)
- PostgreSQL 16
- Alembic 1.13
- asyncpg 0.30

## Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus valores
```

## Ejecución

```bash
uvicorn main:app --reload
```

La API estará disponible en `http://localhost:8000`
Documentación interactiva en `http://localhost:8000/docs`

## Pruebas

```bash
pytest
```

## Estructura del Proyecto

Ver [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md) para más detalles.
