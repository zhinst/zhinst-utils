"""Zurich Instruments LabOne Python API Utility functions for SHFSG.

WARNING: This module is deprecated. Please use `zhinst-utils.shfsg` instead.
"""

from zhinst.utils.shfsg import *  # noqa: F401

import warnings

warnings.warn(
    "zhinst-deviceutils is deprecated. Please use zhinst-utils instead.",
    DeprecationWarning,
    stacklevel=2,
)
