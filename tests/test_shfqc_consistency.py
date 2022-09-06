from unittest.mock import patch
import zhinst.utils.shfqc as shfqc
import inspect
from copy import copy

# Function in zhinst.utils.shfqc not imported from another module
IGNORED_SHFQC = []
# Function in zhinst.utils.shfqa not ported to zhinst.utils.shfqc
IGNORED_SHFQA = []
# Function in zhinst.utils.shfsg not ported to zhinst.utils.shfqc
IGNORED_SHFSG = []


def test_shfqc_consistency():
    """Test if the SHFQC device utils are consistent with SHFQA/SHFSG.

    All functions from the SHFQA and SHFSG device utils must also be available
    within the SHFQC device utils. Exceptions from this rule must be hard coded
    in ``IGNORED_SHFQA``, ``IGNORED_SHFSG``.

    This functions loops through all functions in the SHFQC device utils and
    checks if they have the same interface than the repective SHFQA/SHFSG
    function. Functions that are not forwarded to SHFQA/SHFSG must be hard coded
    in ``IGNORED_SHFQC``
    """

    # Collect all relevant functions
    shfqa_function_names = [
        name
        for name, f in shfqc.shfqa.__dict__.items()
        if inspect.isfunction(f)
        and f.__module__ == "zhinst.utils.shfqa.shfqa"
        and name not in IGNORED_SHFQA
    ]
    shfsg_function_names = [
        name
        for name, f in shfqc.shfsg.__dict__.items()
        if inspect.isfunction(f)
        and f.__module__ == "zhinst.utils.shfsg"
        and name not in IGNORED_SHFSG
    ]
    shfqc_functions = [
        f
        for name, f in shfqc.__dict__.items()
        if inspect.isfunction(f)
        and f.__module__ == "zhinst.utils.shfqc.shfqc"
        and name not in IGNORED_SHFQC
    ]

    for function in shfqc_functions:
        # Create dummy kwarg list for the function (does not need to match
        # the type or anything since we mock the underlying function anyway)
        parameter = {
            param: None for param in inspect.signature(function).parameters.keys()
        }

        # Some functions are parametized to work for bith qa and sg channel
        calls = [parameter]
        if "channel_type" in parameter:
            calls.append(copy(parameter))
            calls[0]["channel_type"] = "sg"
            calls[1]["channel_type"] = "qa"

        # Patch SHFQA an SHFSG, call function and remove the called function
        # from the respective list.
        for kwargs in calls:
            with patch("zhinst.utils.shfqc.shfqc.shfqa", autospec=True) as shfqa, patch(
                "zhinst.utils.shfqc.shfqc.shfsg", autospec=True
            ) as shfsg:
                function(**kwargs)
                if len(shfqa.method_calls) > 0:
                    shfqa_function_names.remove(shfqa.method_calls[0][0])
                if len(shfsg.method_calls) > 0:
                    shfsg_function_names.remove(shfsg.method_calls[0][0])

    # If the lists are empty it means all functions have been called
    assert len(shfqa_function_names) == 0
    assert len(shfsg_function_names) == 0
