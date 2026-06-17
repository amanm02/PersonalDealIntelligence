"""Checkout-time import shim for the src-layout package.

Editable installs use ``src/pdi`` directly. This shim lets commands such as
``python -m pdi.storage`` work from a fresh checkout before installation.
"""

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "pdi"

if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))
