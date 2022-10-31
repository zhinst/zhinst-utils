"""Zurich Instruments LabOne Python API Utility functions for SHFQA."""

import time

import numpy as np
from zhinst.utils.utils import wait_for_state_change
from zhinst.core import AwgModule, ziDAQServer, compile_seqc

SHFQA_MAX_SIGNAL_GENERATOR_WAVEFORM_LENGTH = 4 * 2**10
SHFQA_MAX_SIGNAL_GENERATOR_CARRIER_COUNT = 16
SHFQA_SAMPLING_FREQUENCY = 2e9


def max_qubits_per_channel(daq: ziDAQServer, device_id: str) -> int:
    """Returns the maximum number of supported qubits per channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
    """
    return len(daq.listNodes(f"/{device_id}/qachannels/0/readout/integration/weights"))


def load_sequencer_program(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    sequencer_program: str,
    *,
    awg_module: AwgModule = None,
    timeout: float = 10,
) -> None:
    """Compiles and loads a program to a specified sequencer.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying to which sequencer the program below is
            uploaded - there is one sequencer per channel.
        sequencer_program: Sequencer program to be uploaded.
        awg_module: The standalone AWG compiler is used instead. .. deprecated:: 22.08
        timeout: Maximum time to wait for the compilation on the device in
            seconds.
    """
    # start by resetting the sequencer
    daq.syncSetInt(
        f"/{device_id}/qachannels/{channel_index}/generator/reset",
        1,
    )
    wait_for_state_change(
        daq,
        f"/{device_id}/qachannels/{channel_index}/generator/ready",
        0,
        timeout=timeout,
    )

    device_type = daq.getString(f"/{device_id}/features/devtype")
    device_options = daq.getString(f"/{device_id}/features/options")
    elf, _ = compile_seqc(
        sequencer_program, device_type, device_options, channel_index, sequencer="qa"
    )
    daq.setVector(f"/{device_id}/qachannels/{channel_index}/generator/elf/data", elf)

    # wait until the device becomes ready after program upload
    wait_for_state_change(
        daq,
        f"/{device_id}/qachannels/{channel_index}/generator/ready",
        1,
        timeout=timeout,
    )


def configure_scope(
    daq: ziDAQServer,
    device_id: str,
    *,
    input_select: dict,
    num_samples: int,
    trigger_input: str,
    num_segments: int = 1,
    num_averages: int = 1,
    trigger_delay: float = 0.0,
) -> None:
    """Configures the scope for a measurement.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        input_select: Keys (int) map a specific scope channel with a signal
            source (str), e.g. "channel0_signal_input". For a list of available
            values use daq.help(f"/{device_id}/scopes/0/channels/0/inputselect").
        num_samples: Number of samples in the scope shot.
        trigger_input: Specifies the trigger source of the scope acquisition
            - if set to None, the self-triggering mode of the scope becomes
            active, which is useful e.g. for the GUI. For a list of available
            trigger values use daq.help(f"/{device_id}/scopes/0/trigger/channel").
        num_segments: Number of distinct scope shots to be returned after ending
            the acquisition.
        num_averages: Specifies how many times each segment should be averaged
            on hardware; to finish a scope acquisition, the number of issued
            triggers must be equal to num_segments * num_averages.
        trigger_delay: Delay in samples specifying the time between the start of
            data acquisition and reception of a trigger.
    """
    scope_path = f"/{device_id}/scopes/0/"
    settings = []

    settings.append((scope_path + "segments/count", num_segments))
    if num_segments > 1:
        settings.append((scope_path + "segments/enable", 1))
    else:
        settings.append((scope_path + "segments/enable", 0))

    if num_averages > 1:
        settings.append((scope_path + "averaging/enable", 1))
    else:
        settings.append((scope_path + "averaging/enable", 0))

    settings.append((scope_path + "averaging/count", num_averages))

    settings.append((scope_path + "channels/*/enable", 0))
    for channel, selected_input in input_select.items():
        settings.append(
            (scope_path + f"channels/{channel}/inputselect", selected_input)
        )
        settings.append((scope_path + f"channels/{channel}/enable", 1))
        settings.append((scope_path + "trigger/delay", trigger_delay))

        if trigger_input is not None:
            settings.append((scope_path + "trigger/channel", trigger_input))
            settings.append((scope_path + "trigger/enable", 1))
        else:
            settings.append((scope_path + "trigger/enable", 0))

    settings.append((scope_path + "length", num_samples))

    daq.set(settings)


def get_scope_data(daq: ziDAQServer, device_id: str, *, timeout: float = 1.0) -> tuple:
    """Queries the scope for data once it is finished.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        timeout: Maximum time to wait for the scope data in seconds.

    Returns:
        Three-element tuple with:
            * recorded_data (array): Contains an array per scope channel with
                the recorded data.
            * recorded_data_range (array): Full scale range of each scope
                channel.
            * scope_time (array): Relative acquisition time for each point in
                recorded_data in seconds starting from 0.
    """
    # wait until scope has been triggered
    wait_for_state_change(daq, f"/{device_id}/scopes/0/enable", 0, timeout=timeout)

    # read and post-process the recorded data
    recorded_data = [[], [], [], []]
    recorded_data_range = [0.0, 0.0, 0.0, 0.0]
    num_bits_of_adc = 14
    max_adc_range = 2 ** (num_bits_of_adc - 1)

    channels = range(4)
    for channel in channels:
        if daq.getInt(f"/{device_id}/scopes/0/channels/{channel}/enable"):
            path = f"/{device_id}/scopes/0/channels/{channel}/wave"
            data = daq.get(path.lower(), flat=True)
            vector = data[path]

            recorded_data[channel] = vector[0]["vector"]
            averagecount = vector[0]["properties"]["averagecount"]
            scaling = vector[0]["properties"]["scaling"]
            voltage_per_lsb = scaling * averagecount
            recorded_data_range[channel] = voltage_per_lsb * max_adc_range

    # generate the time base
    scope_time = [[], [], [], []]
    decimation_rate = 2 ** daq.getInt(f"/{device_id}/scopes/0/time")
    sampling_rate = SHFQA_SAMPLING_FREQUENCY / decimation_rate  # [Hz]
    for channel in channels:
        scope_time[channel] = (
            np.array(range(0, len(recorded_data[channel]))) / sampling_rate
        )

    return recorded_data, recorded_data_range, scope_time


def enable_sequencer(
    daq: ziDAQServer, device_id: str, channel_index: int, *, single: int
) -> None:
    """Starts the sequencer of a specific channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer to enable - there is one
            sequencer per channel.
        single: 1 - Disable sequencer after finishing execution.
                0 - Restart sequencer after finishing execution.
    """
    generator_path = f"/{device_id}/qachannels/{channel_index}/generator/"
    daq.setInt(
        generator_path + "single",
        single,
    )
    daq.syncSetInt(generator_path + "enable", 1)
    hundred_milliseconds = 0.1
    time.sleep(hundred_milliseconds)


def write_to_waveform_memory(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    waveforms: dict,
    *,
    clear_existing: bool = True,
) -> None:
    """Writes pulses to the waveform memory of a specified generator.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which generator the waveforms below are
            written to - there is one generator per channel.
        waveforms: Dictionary of waveforms, the key specifies the slot to which
            to write the value which is a complex array containing the waveform
            samples.
        clear_existing: Specify whether to clear the waveform memory before the
            present upload.
    """
    generator_path = f"/{device_id}/qachannels/{channel_index}/generator/"

    if clear_existing:
        daq.syncSetInt(generator_path + "clearwave", 1)

    settings = []
    for slot, waveform in waveforms.items():
        settings.append((generator_path + f"waveforms/{slot}/wave", waveform))

    daq.set(settings)


def start_continuous_sw_trigger(
    daq: ziDAQServer, device_id: str, *, num_triggers: int, wait_time: float
) -> None:
    """Issues a specified number of software triggers.

    Issues a specified number of software triggers with a certain wait time in
    between. The function guarantees reception and proper processing of all
    triggers by the device, but the time between triggers is non-deterministic
    by nature of software triggering.

    Warning:
        Only use this function for prototyping and/or cases without strong
        timing requirements.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        num_triggers: Number of triggers to be issued.
        wait_time: Time between triggers in seconds.
    """
    min_wait_time = 0.02
    wait_time = max(min_wait_time, wait_time)
    for _ in range(num_triggers):
        # syncSetInt() is a blocking call with non-deterministic execution time that
        # imposes a minimum time between two software triggers.
        daq.syncSetInt(f"/{device_id}/system/swtriggers/0/single", 1)
        time.sleep(wait_time)


def enable_scope(
    daq: ziDAQServer, device_id: str, *, single: int, acknowledge_timeout: float = 1.0
) -> None:
    """Resets and enables the scope.

    Blocks until the host has received the enable acknowledgment from the
    device.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        single: 0 = continuous mode, 1 = single-shot.
        acknowledge_timeout: Maximum time to wait for diverse acknowledgments
            in the implementation.

            .. versionadded:: 0.1.1
    """
    daq.setInt(f"/{device_id}/scopes/0/single", single)

    path = f"/{device_id}/scopes/0/enable"
    if daq.getInt(path) == 1 and daq.syncSetInt(path, 0) != 0:
        raise RuntimeError(
            f"Failed to disable the scope for device {device_id} before enabling it."
        )
    if daq.syncSetInt(path, 1) != 1:
        raise RuntimeError(f"The scope for device {device_id} could not be enabled")


def configure_weighted_integration(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    weights: dict,
    integration_delay: float = 0.0,
    clear_existing: bool = True,
) -> None:
    """Configures the weighted integration on a specified channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which group of integration units the
            integration weights should be uploaded to - each channel is
            associated with a number of integration units that depend on
            available device options. Please refer to the SHFQA manual for more
            details.
        weights: Dictionary containing the complex weight vectors, where keys
            correspond to the indices of the integration units to be configured.
        integration_delay: Delay in seconds before starting readout.
        clear_existing: Specify whether to set all the integration weights to
            zero before proceeding with the present upload.
    """
    assert len(weights) > 0, "'weights' cannot be empty."

    integration_path = f"/{device_id}/qachannels/{channel_index}/readout/integration/"

    if clear_existing:
        daq.syncSetInt(integration_path + "clearweight", 1)

    settings = []

    for integration_unit, weight in weights.items():
        settings.append((integration_path + f"weights/{integration_unit}/wave", weight))

    integration_length = len(weights[0])
    settings.append((integration_path + "length", integration_length))
    settings.append((integration_path + "delay", integration_delay))

    daq.set(settings)


def configure_result_logger_for_spectroscopy(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    result_length: int,
    num_averages: int = 1,
    averaging_mode: int = 0,
) -> None:
    """Configures a specified result logger for spectroscopy mode.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which result logger to configure - there
            is one result logger per channel.
        result_length: Number of results to be returned by the result logger
        num_averages: Number of averages, will be rounded to 2^n.
        averaging_mode: Select the averaging order of the result, with
            0 = cyclic and 1 = sequential.
    """
    result_path = f"/{device_id}/qachannels/{channel_index}/spectroscopy/result/"
    settings = []

    settings.append((result_path + "length", result_length))
    settings.append((result_path + "averages", num_averages))
    settings.append((result_path + "mode", averaging_mode))

    daq.set(settings)


def configure_result_logger_for_readout(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    result_source: str,
    result_length: int,
    num_averages: int = 1,
    averaging_mode: int = 0,
) -> None:
    """Configures a specified result logger for readout mode.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which result logger to configure - there
            is one result logger per channel.
        result_source: String-based tag to select the result source in readout
            mode, e.g. "result_of_integration" or "result_of_discrimination".
        result_length: Number of results to be returned by the result logger.
        num_averages: Number of averages, will be rounded to 2^n.
        averaging_mode: Select the averaging order of the result, with
            0 = cyclic and 1 = sequential.
    """
    result_path = f"/{device_id}/qachannels/{channel_index}/readout/result/"
    settings = []

    settings.append((result_path + "length", result_length))
    settings.append((result_path + "averages", num_averages))
    settings.append((result_path + "source", result_source))
    settings.append((result_path + "mode", averaging_mode))

    daq.set(settings)


def enable_result_logger(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    mode: str,
    acknowledge_timeout: float = 1.0,
) -> None:
    """Resets and enables a specified result logger.

    Blocks until the host has received the enable acknowledgment from the
    device.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which result logger to enable - there is
            one result logger per channel.
        mode: Select between "spectroscopy" and "readout" mode.
        acknowledge_timeout: Maximum time to wait for diverse acknowledgments in
            the implementation.

            .. versionadded:: 0.1.1
    """
    enable_path = f"/{device_id}/qachannels/{channel_index}/{mode}/result/enable"

    # reset the result logger if some old measurement is still running
    if daq.getInt(enable_path) == 1 and daq.syncSetInt(enable_path, 0) != 0:
        raise RuntimeError(f"Failed to disable the result logger for {mode} mode.")

    # enable the result logger
    if daq.syncSetInt(enable_path, 1) != 1:
        raise RuntimeError(
            f"Failed to enable the result logger for {mode} mode. "
            f"Please make sure that the QA channel mode is set to {mode}."
        )


def get_result_logger_data(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    mode: str,
    timeout: float = 1.0,
) -> np.array:
    """Return the measured data of a specified result logger.

    Blocks until the specified result logger is finished.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which result logger to query results
            from - there is one result logger per channel.
        mode: Select between "spectroscopy" and "readout" mode.
        timeout: Maximum time to wait for data in seconds.

    Returns:
        Array containing the result logger data.
    """
    try:
        wait_for_state_change(
            daq,
            f"/{device_id}/qachannels/{channel_index}/{mode}/result/enable",
            0,
            timeout=timeout,
        )
    except TimeoutError as error:
        raise TimeoutError(
            "The result logger is still running. "
            "This usually indicates that it did not receive the expected number of "
            "triggers."
        ) from error

    data = daq.get(
        f"/{device_id}/qachannels/{channel_index}/{mode}/result/data/*/wave",
        flat=True,
    )

    result = np.array([d[0]["vector"] for d in data.values()])
    return result


def configure_channel(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    input_range: int,
    output_range: int,
    center_frequency: float,
    mode: str,
) -> None:
    """Configures the RF input and output of a specified channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which channel to configure.
        input_range: Maximal range of the signal input power in dbM.
        output_range: Maximal range of the signal output power in dbM.
        center_frequency: Center Frequency of the analysis band.
        mode: Select between "spectroscopy" and "readout" mode.
    """
    path = f"/{device_id}/qachannels/{channel_index}/"
    settings = []

    settings.append((path + "input/range", input_range))
    settings.append((path + "output/range", output_range))
    settings.append((path + "centerfreq", center_frequency))
    settings.append((path + "mode", mode))

    daq.set(settings)


def configure_sequencer_triggering(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    aux_trigger: str,
    play_pulse_delay: float = 0.0,
) -> None:
    """Configures the triggering of a specified sequencer.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQA device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying on which sequencer to configure the
            triggering - there is one sequencer per channel.
        aux_trigger: Alias for the trigger used in the sequencer. For a list of
            available values use.
            daq.help(f"/{device_id}/qachannels/0/generator/auxtriggers/0/channel")
        play_pulse_delay: Delay in seconds before the start of waveform playback.
    """
    daq.setString(
        f"/{device_id}/qachannels/{channel_index}/generator/auxtriggers/0/channel",
        aux_trigger,
    )
    daq.setDouble(
        f"/{device_id}/qachannels/{channel_index}/generator/delay",
        play_pulse_delay,
    )
