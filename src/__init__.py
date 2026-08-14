# Load startup resilience before the application imports ServerManager.
from . import startup_guard  # noqa: F401
