"""The Zurich Instruments Device Utils (zhinst-deviceutils).

WARNING: This module is deprecated. Please use `zhinst-utils` instead.
"""
import warnings

warnings.warn(
    "zhinst-deviceutils is deprecated. Please use zhinst-utils instead.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from zhinst.utils._version import version as __version__
except ModuleNotFoundError:
    pass
