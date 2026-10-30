"""Application modules and their SQLModel registrations."""

# Register every table before any session can flush ORM objects.  Several domain
# models reference tables owned by another module, so selective imports leave
# SQLModel.metadata incomplete and cause NoReferencedTableError at flush time.
from app.modules.usuarios import models as _usuarios_models  # noqa: F401
from app.modules.clientes import models as _clientes_models  # noqa: F401
from app.modules.repuestos import models as _repuestos_models  # noqa: F401
from app.modules.ordenes import models as _ordenes_models  # noqa: F401
