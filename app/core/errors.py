class ErrorAplicacion(Exception):
    def __init__(self, detalle: str, codigo: str, codigo_http: int = 400):
        self.detail = detalle
        self.detalle = detalle
        self.codigo = codigo
        self.status_code = codigo_http
        self.codigo_http = codigo_http
        super().__init__(detalle)


class ConflictoError(ErrorAplicacion):
    def __init__(self, detalle: str = "Conflicto", codigo: str = "CONFLICTO"):
        super().__init__(detalle, codigo, codigo_http=409)


class NoEncontradoError(ErrorAplicacion):
    def __init__(self, detalle: str = "No encontrado", codigo: str = "NO_ENCONTRADO"):
        super().__init__(detalle, codigo, codigo_http=404)


class ProhibidoError(ErrorAplicacion):
    def __init__(self, detalle: str = "Prohibido", codigo: str = "PROHIBIDO"):
        super().__init__(detalle, codigo, codigo_http=403)


class NoAutenticadoError(ErrorAplicacion):
    def __init__(self, detalle: str = "No autenticado", codigo: str = "NO_AUTENTICADO"):
        super().__init__(detalle, codigo, codigo_http=401)


class ReglaNegocioError(ErrorAplicacion):
    def __init__(self, detalle: str = "Regla de negocio violada", codigo: str = "REGLA_NEGOCIO"):
        super().__init__(detalle, codigo, codigo_http=422)


class DemasiadasPeticionesError(ErrorAplicacion):
    def __init__(self, detalle: str = "Demasiadas peticiones", codigo: str = "DEMASIADAS_PETICIONES", reintentar_despues: int | None = None):
        super().__init__(detalle, codigo, codigo_http=429)
        self.retry_after = reintentar_despues
        self.reintentar_despues = reintentar_despues


# Alias para compatibilidad
AppError = ErrorAplicacion
