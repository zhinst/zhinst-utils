from unittest.mock import MagicMock

from zhinst.utils.auto_generate_functions import (
    _cut_section_out,
    build_docstring_configure,
    configure_maker,
)

EXAMPLE_DOCSTRING = """Compiles and loads a program to a specified AWG core.

    This function is composed of 4 steps:
        1. Reset the awg core to ensure a clean state.
        2. Compile the sequencer program with the offline compiler.
        3. Upload the compiled binary elf file.
        4. Validate that the upload was successful and the awg core is ready
           again.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer to upload - there
            is one sequencer per channel.
        sequencer_program: Sequencer program to be uploaded.

    Raises:
        RuntimeError: If the Upload was not successfully or the device could not
            process the sequencer program.
    """

EXAMPLE_DOCSTRING2 = """Provides a list of settings for the trigger inputs and marker outputs of a specified AWG core.

    This function only gathers all node settings and does not apply the values on the
    device.
    It is intended to be used by higher-level APIs for simpler integrations.
    Instead of using it, consider calling 'configure_marker_and_trigger' instead.

    Args:
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'
        channel_index: Index of the used SG channel.
        trigger_in_source: Alias for the trigger input used by the
            sequencer. For a list of available values use:
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/awg/auxtriggers/0/channel")
        trigger_in_slope: Alias for the slope of the input trigger used
            by sequencer. For a list of available values use
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/awg/auxtriggers/0/slope")
            or `available_trigger_inputs` in zhinst.toolkit
        marker_out_source: Alias for the marker output source used by the
            sequencer. For a list of available values use
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/marker/source")
            or `available_trigger_slopes` in zhinst.toolkit
    """


def test_cut_section_out():
    args_section = _cut_section_out("Args", EXAMPLE_DOCSTRING)
    raises_section = _cut_section_out("Raises", EXAMPLE_DOCSTRING)

    non_existing_section = _cut_section_out("NonExisting", EXAMPLE_DOCSTRING)

    assert non_existing_section == ""

    assert (
        args_section
        == """    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer to upload - there
            is one sequencer per channel.
        sequencer_program: Sequencer program to be uploaded.

"""
    )

    assert (
        args_section + raises_section
        == """    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer to upload - there
            is one sequencer per channel.
        sequencer_program: Sequencer program to be uploaded.

    Raises:
        RuntimeError: If the Upload was not successfully or the device could not
            process the sequencer program.
"""
    )


def test_build_docstring_configure():
    generated_docstring = build_docstring_configure(
        EXAMPLE_DOCSTRING2,
        "Configures the trigger inputs and marker outputs of a specified AWG core.",
    )
    assert (
        generated_docstring
        == """Configures the trigger inputs and marker outputs of a specified AWG core.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'
        channel_index: Index of the used SG channel.
        trigger_in_source: Alias for the trigger input used by the
            sequencer. For a list of available values use:
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/awg/auxtriggers/0/channel")
        trigger_in_slope: Alias for the slope of the input trigger used
            by sequencer. For a list of available values use
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/awg/auxtriggers/0/slope")
            or `available_trigger_inputs` in zhinst.toolkit
        marker_out_source: Alias for the marker output source used by the
            sequencer. For a list of available values use
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/marker/source")
            or `available_trigger_slopes` in zhinst.toolkit
"""
    )


def test_configure_maker():
    def get_settings(arg1: int, kwarg1: int = 0):
        """simple settings function"""
        return [("setting1", arg1 + kwarg1)]

    configure_func = configure_maker(get_settings, lambda x: "wrapped " + x)

    assert configure_func.__doc__ == """wrapped simple settings function"""

    daq = MagicMock()
    configure_func(daq, 5, kwarg1=3)
    daq.set.assert_called_once_with([("setting1", 8)])
