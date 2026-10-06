"""Permite `python -m nexus_diff` y `python ruta/a/nexus_diff/__main__.py` (lo usa el plugin de opencode)."""

import sys
from pathlib import Path

if __package__ in (None, ""):  # ejecutado como script: el paquete aún no es importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus_diff.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
