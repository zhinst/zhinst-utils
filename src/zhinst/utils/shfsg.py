"""Zurich Instruments LabOne Python API Utility functions for SHFSG."""
import typing as t
from functools import partial

from zhinst.utils import convert_awg_waveform
from zhinst.utils.auto_generate_functions import (
    configure_maker,
    build_docstring_configure,
)
from zhinst.core import ziDAQServer, compile_seqc

SHFSG_MAX_SIGNAL_GENERATOR_WAVEFORM_LENGTH = 98304
SHFSG_SAMPLING_FREQUENCY = 2e9


def load_sequencer_program(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    sequencer_program: str,
    **_,
) -> None:
    """Compiles and loads a program to a specified AWG core.

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
    # start by resetting the sequencer
    daq.syncSetInt(f"/{device_id}/sgchannels/{channel_index}/awg/reset", 1)
    device_type = daq.getString(f"/{device_id}/features/devtype")
    device_options = daq.getString(f"/{device_id}/features/options")
    elf, _ = compile_seqc(
        sequencer_program, device_type, device_options, channel_index, sequencer="sg"
    )
    daq.setVector(f"/{device_id}/sgchannels/{channel_index}/awg/elf/data", elf)
    if not daq.get(f"/{device_id}/sgchannels/{channel_index}/awg/ready"):
        raise RuntimeError(
            "The device did not not switch to into the ready state after the upload."
        )


def enable_sequencer(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    single: t.Union[bool, int] = True,
) -> None:
    """Starts the sequencer of a specific channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer to enable - there
            is one sequencer per channel.
        single: Flag if the sequencer should run in single mode.
    """
    sequencer_path = f"/{device_id}/sgchannels/{channel_index}/awg/"
    daq.setInt(
        sequencer_path + "single",
        int(single),
    )
    if not daq.syncSetInt(sequencer_path + "enable", 1):
        raise RuntimeError(
            "The sequencer could not be enabled. Please ensure that the "
            "sequencer program is loaded and configured correctly."
        )


def upload_commandtable(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    command_table: str,
) -> None:
    """Uploads a command table in the form of a string to the appropriate channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which channel to upload the command
            table to.
        command_table: The command table to be uploaded.
    """
    # upload command table
    daq.setVector(
        f"/{device_id}/sgchannels/{channel_index}/awg/commandtable/data",
        command_table,
    )


def write_to_waveform_memory(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    waveforms: dict,
) -> None:
    """Writes waveforms to the waveform memory of a specified sequencer.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer the waveforms below are
            written to - there is one generator per channel.
        waveforms (dict): Dictionary of waveforms, the key specifies the
            waveform index to which to write the waveforms.
    """
    waveforms_path = f"/{device_id}/sgchannels/{channel_index}/awg/waveform/waves/"
    settings = []

    for slot, waveform in waveforms.items():
        wave_raw = convert_awg_waveform(waveform)
        settings.append((waveforms_path + f"{slot}", wave_raw))

    daq.set(settings)


def get_marker_and_trigger_settings(
    device_id: str,
    channel_index: int,
    *,
    trigger_in_source: str,
    trigger_in_slope: str,
    marker_out_source: str,
) -> t.List[t.Tuple[str, str]]:
    """Provides settings for the trigger inputs and marker outputs of an AWG core.

    This function only gathers all node settings and does not apply the values on the
    device. It is intended to be used by higher-level APIs for simpler integrations.
    Instead of using this function directly, consider calling
    'configure_marker_and_trigger', which will also apply the settings on the device.

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
    # Trigger input
    settings = [
        (
            f"/{device_id}/sgchannels/{channel_index}/awg/auxtriggers/0/channel",
            trigger_in_source,
        ),
        (
            f"/{device_id}/sgchannels/{channel_index}/awg/auxtriggers/0/slope",
            trigger_in_slope,
        ),
        (
            f"/{device_id}/sgchannels/{channel_index}/marker/source",
            marker_out_source,
        ),
    ]

    # Marker output
    return settings


configure_marker_and_trigger = configure_maker(
    get_marker_and_trigger_settings,
    partial(
        build_docstring_configure,
        new_first_line="Configures the trigger inputs and marker outputs of a "
        "specified AWG core.",
    ),
)


def configure_channel(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    enable: int,
    output_range: int,
    center_frequency: float,
    rflf_path: int,
) -> None:
    """Configures the RF input and output of a specified channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index of the used SG channel.
        enable: Whether or not to enable the channel.
        output_range: Maximal range of the signal output power in dbM.
        center_frequency: Center Frequency before modulation.
        rflf_path: Switch between RF and LF paths.
    """
    path = f"/{device_id}/sgchannels/{channel_index}/"
    settings = []

    settings.append((path + "output/range", output_range))
    settings.append((path + "output/rflfpath", rflf_path))
    if rflf_path == 1:
        synth = daq.getInt(path + "synthesizer")
        settings.append(
            (f"/{device_id}/synthesizers/{synth}/centerfreq", center_frequency)
        )
    elif rflf_path == 0:
        settings.append((path + "digitalmixer/centerfreq", center_frequency))
    settings.append((path + "output/on", enable))

    daq.set(settings)


def get_pulse_modulation_settings(
    device_id: str,
    channel_index: int,
    *,
    enable: int,
    osc_index: int = 0,
    osc_frequency: float = 100e6,
    phase: float = 0.0,
    global_amp: float = 0.5,
    gains: tuple = (1.0, -1.0, 1.0, 1.0),
    sine_generator_index: int = 0,
) -> t.List[t.Union[t.Tuple[str, int], t.Tuple[str, float]]]:
    """Provides a list of settings for the pulse modulation.

    This function only gathers all node settings and does not apply the values on the
    device. It is intended to be used by higher-level APIs for simpler integrations.
    Instead of using this function directly, consider calling
    'configure_pulse_modulation', which will also apply the settings on the device.

    Provides settings which would configure the sine generator to digitally modulate
    the AWG output, for generating single sideband AWG signals.

    Args:
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'
        channel_index: Index of the used SG channel.
        enable: Enables modulation.
        osc_index: Selects which oscillator to use.
        osc_frequency: Oscillator frequency used to modulate the AWG
            outputs. (default = 100e6)
        phase: Sets the oscillator phase. (default = 0.0)
        global_amp: Global scale factor for the AWG outputs. (default = 0.5)
        gains: Sets the four amplitudes used for single sideband
            generation. default values correspond to upper sideband with a
            positive oscillator frequency. (default = (1.0, -1.0, 1.0, 1.0))
        sine_generator_index: Selects which sine generator to use on a given
            channel.
    """
    path = f"/{device_id}/sgchannels/{channel_index}/"
    settings = [
        (path + f"sines/{sine_generator_index}/oscselect", osc_index),
        (path + f"sines/{sine_generator_index}/phaseshift", phase),
        (path + f"oscs/{osc_index}/freq", osc_frequency),
        (path + "awg/modulation/enable", enable),
        (path + "awg/outputamplitude", global_amp),
        (path + "awg/outputs/0/gains/0", gains[0]),
        (path + "awg/outputs/0/gains/1", gains[1]),
        (path + "awg/outputs/1/gains/0", gains[2]),
        (path + "awg/outputs/1/gains/1", gains[3]),
    ]

    return settings


configure_pulse_modulation = configure_maker(
    get_pulse_modulation_settings,
    partial(
        build_docstring_configure,
        new_first_line="""Configure the pulse modulation.

    Configures the sine generator to digitally modulate the AWG output, for
    generating single sideband AWG signals.""",
    ),
)


def get_sine_generation_settings(
    device_id: str,
    channel_index: int,
    *,
    enable: int,
    osc_index: int = 0,
    osc_frequency: float = 100e6,
    phase: float = 0.0,
    gains: tuple = (0.0, 1.0, 1.0, 0.0),
    sine_generator_index: int = 0,
) -> t.List[t.Tuple[str, t.Any]]:
    """Provides a list of settings for the sine generator output of a specified channel.

    This function only gathers all node settings and does not apply the values on the
    device. It is intended to be used by higher-level APIs for simpler integrations.
    Instead of using this function directly, consider calling
    'configure_sine_generation', which will also apply the settings on the device.

    Provides settings which would configure the sine generator output of a specified
    channel for generating continuous wave signals without the AWG.

    Args:
        device_id: SHFSG device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index of the used SG channel.
        enable: Enables the sine generator output.
        osc_index: Selects which oscillator to use.
        osc_frequency: Oscillator frequency used by the sine generator.
            (default = 100e6)
        phase: Sets the oscillator phase. (default = 0.0)
        gains: Sets the four amplitudes used for single sideband.
            generation. default values correspond to upper sideband with a
            positive oscillator frequency. gains are set in this order:
            I/sin, I/cos, Q/sin, Q/cos
            (default = (0.0, 1.0, 1.0, 0.0))
        sine_generator_index: Selects which sine generator to use on a given
            channel.
    """
    path = f"/{device_id}/sgchannels/{channel_index}/sines/{sine_generator_index}/"
    settings = [
        (path + "i/enable", enable),
        (path + "q/enable", enable),
        (path + "i/sin/amplitude", gains[0]),
        (path + "i/cos/amplitude", gains[1]),
        (path + "q/sin/amplitude", gains[2]),
        (path + "q/cos/amplitude", gains[3]),
        (path + "oscselect", osc_index),
        (
            f"/{device_id}/sgchannels/{channel_index}/oscs/{osc_index}/freq",
            osc_frequency,
        ),
        (path + "phaseshift", phase),
    ]

    return settings


configure_sine_generation = configure_maker(
    get_sine_generation_settings,
    partial(
        build_docstring_configure,
        new_first_line="""Configures the sine generator output of a specified channel.

    Configures the sine generator output of a specified channel for generating
    continuous wave signals without the AWG.""",
    ),
)
