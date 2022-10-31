"""Zurich Instruments LabOne Python API Utility functions for SHFQA.

WARNING: This module is deprecated. Please use `zhinst-utils.shfqa` instead.
"""
from zhinst.utils.shfqa import *  # noqa: F401

import warnings

warnings.warn(
    "zhinst-deviceutils is deprecated. Please use zhinst-utils instead.",
    DeprecationWarning,
    stacklevel=2,
)
