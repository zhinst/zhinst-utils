"""Zurich Instruments LabOne Python API Utility functions for SHFQC.

WARNING: This module is deprecated. Please use `zhinst-utils.shfqc` instead.
"""
from zhinst.utils.shfqc import *  # noqa: F401

import warnings

warnings.warn(
    "zhinst-deviceutils is deprecated. Please use zhinst-utils instead.",
    DeprecationWarning,
    stacklevel=2,
)
