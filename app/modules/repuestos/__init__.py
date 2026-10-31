from .router import router_autenticado

router = router_autenticado
router_publico = router_autenticado
router_autenticado = router_autenticado

__all__ = ["router", "router_publico", "router_autenticado"]
