"""easy-cheese-schemas: the shared document and manifest schemas.

The version-compat layer is the public surface: `load` structures a raw mapping
and reports what it could not read, and `Provenance` says how the payload's
stamp relates to the version this package understands.
"""

from __future__ import annotations

from easy_cheese_schemas.compat import (
    MIN_READABLE,
    SCHEMA_VERSION,
    Loaded,
    Provenance,
    load,
)

__version__ = "0.1.0"

__all__ = [
    "MIN_READABLE",
    "SCHEMA_VERSION",
    "Loaded",
    "Provenance",
    "__version__",
    "load",
]
