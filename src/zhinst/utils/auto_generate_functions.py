"""Zurich Instruments LabOne Python API functions for automatic code generation."""
import re
import typing as t

from zhinst.core import ziDAQServer

_DAQ_ARG = (
    """        daq: Instance of a Zurich Instruments API session"""
    + """ connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
"""
)


def build_docstring_configure(old_docstring: str, new_first_line: str) -> str:
    """Builds a good docstring for a configure-func.

    Assumes Google-style docstring, e.g. sections are named Args, Returns, ...

    Args:
        old_docstring: docstring of wrapped get_settings function
        new_first_line: defines how the first line of the created docstring will look
            like
    """
    return (
        new_first_line
        + "\n\n"
        + _cut_section_out("Args", old_docstring, include_body=False)
        + _DAQ_ARG
        + _cut_section_out("Args", old_docstring, include_header=False)
        + "".join(
            [
                _cut_section_out(section, old_docstring)
                for section in ["Warning", "Raises", "Returns"]
            ]
        )
    )


def _cut_section_out(
    section_name: str,
    docstring: str,
    include_body: bool = True,
    include_header: bool = True,
) -> str:
    """Cuts a specific part out of a Google-style docstring.

    Args:
        section_name: Name of the section to cut out. Should match Google-style sections
            names, such as `Args`, `Returns` or `Raises`
        docstring: Documentation-string in which to search for section
        include_body: Specifies whether everything but the line with the section name
            should be included in the result
        include_header: Specifies whether the line with the section name should be
            included in the result

    """
    indentation_pattern = rf"^(?P<indentation>[ ]*){section_name}:"
    indentation_match = re.search(
        indentation_pattern, docstring, re.MULTILINE | re.VERBOSE
    )
    if not indentation_match:
        return ""
    indentation_depth = len(indentation_match.group("indentation"))

    pattern = (
        r"(?P<header>([ ]*)"  # group of leading whitespaces in front of section_name
        rf"{section_name}:\n)"  # anchor at section_name line
        r"(?P<args>"  # named group of content
        r"((?![ ]{,"
        rf"{indentation_depth}"
        r"}\w)"  # look if next line has <= indentation as section_name-line
        r".*\n"  # consume a line
        r")*)"  # loop
    )
    match = re.search(pattern, docstring, re.VERBOSE)
    if not match:
        return ""

    section = ""
    if include_header:
        section += match.group("header")
    if include_body:
        section += match.group("args")
    return section


def configure_maker(
    get_setting_func: t.Callable[..., t.List[t.Tuple[str, t.Any]]],
    build_docstring_from_old_one: t.Callable[[str], str],
) -> t.Callable[[ziDAQServer, t.Any], None]:
    """Creates a wrapper which applies the settings provided by a given function.

    Args:
        get_setting_func: Function which provides a list of settings for a device.
        build_docstring_from_old_one: Function for dynamically creating a helpful
            docstring out of the one from the get_settings_func

    Returns:
        Function which applies all the settings that the get_settings_func provides
    """

    def configure_func(daq: ziDAQServer, *args, **kwargs) -> None:
        settings = get_setting_func(*args, **kwargs)
        daq.set(settings)

    configure_func.__doc__ = (
        build_docstring_from_old_one(get_setting_func.__doc__)
        if get_setting_func.__doc__ is not None
        else ""
    )
    configure_func.__module__ = get_setting_func.__module__
    return configure_func
