""" Utility functions for versioning checks
"""

from inspect import getfile
from re import match
from functools import wraps

import zhinst.ziPython


def minimum_version(min_version):
    """
     Parameterized decorator to enforce a minimum ziPython version on arbitrary functions.

     Example usage:

     @minimum_version('21.02')
     def shfqa_example(*args):
         ....

     In case the version is not supported, the above function is swapped for throwing one during definition.

     Args:
         min_version (str): ziPython version with format MAJOR.MINOR or MAJOR.MINOR.BUILD
     """

    major_minor_format = bool(match(r"^\d\d\.\d\d$", min_version))
    major_minor_build_format = bool(match(r"^\d\d\.\d\d.\d+$", min_version))

    if major_minor_format:
        min_major, min_minor = map(int, min_version.split("."))
        min_build = 0
    elif major_minor_build_format:
        min_major, min_minor, min_build = map(int, min_version.split("."))
    else:
        raise Exception(
            f"Wrong ziPython version format: {min_version}. Supported format: MAJOR.MINOR or MAJOR.MINOR.BUILD"
        )

    def decorate(function):

        installed_version = zhinst.ziPython.__version__
        major, minor, build = map(int, installed_version.split("."))

        not_supported = (min_major, min_minor, min_build) > (major, minor, build)

        if not_supported:

            @wraps(function)
            def throw(*args, **kwargs):
                *_, file_name = getfile(function).split("/")
                raise Exception(
                    f'Function "{function.__name__}" from file "{file_name}" requires ziPython version '
                    f"{min_version} or higher (current: {installed_version}). Please visit the Zurich Instruments "
                    f"website to update."
                )

            return throw

        return function

    return decorate
