"""Zurich Instruments LabOne Python API Utility functions for SHFQC."""
import numpy as np
from zhinst.core import AwgModule, ziDAQServer

from zhinst.utils import shfqa, shfsg


def max_qubits_per_qa_channel(daq: ziDAQServer, device_id: str) -> int:
    """Returns the maximum number of supported qubits per channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
    """
    return shfqa.max_qubits_per_channel(daq, device_id)


def load_sequencer_program(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    sequencer_program: str,
    *,
    channel_type: str,
    awg_module: AwgModule = None,
    timeout: float = 10,
) -> None:
    """Compiles and loads a program to a specified sequencer.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying to which sequencer the program below is
            uploaded - there is one sequencer per channel. (Always 0 for the
            qa channel)
        sequencer_program: Sequencer program to be uploaded.
        channel_type: Identifier specifing if the sequencer from the qa or sg
            channel should be used. ("qa" or "sg")
        awg_module: The standalone AWG compiler is used instead. .. deprecated:: 22.08
        timeout: Maximum time to wait for the compilation on the device in
            seconds.
    """
    if channel_type == "qa":
        return shfqa.load_sequencer_program(
            daq,
            device_id,
            0,
            sequencer_program,
            awg_module=awg_module,
            timeout=timeout,
        )
    if channel_type == "sg":
        return shfsg.load_sequencer_program(
            daq,
            device_id,
            channel_index,
            sequencer_program,
            awg_module=awg_module,
            timeout=timeout,
        )
    raise ValueError(
        f'channel_type was set to {channel_type} but only qa" and "sg" ' "are allowed"
    )


def enable_sequencer(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    single: int,
    channel_type: str,
) -> None:
    """Starts the sequencer of a specific channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer to enable - there is one
            sequencer per channel. (Always 0 for the qa channel)
        single: 1 - Disable sequencer after finishing execution.
                0 - Restart sequencer after finishing execution.
        channel_type: Identifier specifing if the sequencer from the qa or sg
            channel should be used. ("qa" or "sg")
    """
    if channel_type == "qa":
        return shfqa.enable_sequencer(
            daq,
            device_id,
            0,
            single=single,
        )
    if channel_type == "sg":
        return shfsg.enable_sequencer(
            daq,
            device_id,
            channel_index,
            single=single,
        )
    raise ValueError(
        f'channel_type was set to {channel_type} but only "qa" and "sg" ' "are allowed"
    )


def write_to_waveform_memory(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    waveforms: dict,
    *,
    channel_type: str,
    clear_existing: bool = True,
) -> None:
    """Writes pulses to the waveform memory of a specified generator.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which sequencer the waveforms below are
            written to - there is one generator per channel.
        waveforms: Dictionary of waveforms, the key specifies the slot to which
            to write the value which is a complex array containing the waveform
            samples.
        channel_type: Identifier specifing if the waveforms should be uploaded
            to the qa or sg channel. ("qa" or "sg")
        clear_existing: Specify whether to clear the waveform memory before the
            present upload. (Only used when channel_type is "qa"!)
    """
    if channel_type == "qa":
        return shfqa.write_to_waveform_memory(
            daq,
            device_id,
            channel_index,
            waveforms,
            clear_existing=clear_existing,
        )
    if channel_type == "sg":
        return shfsg.write_to_waveform_memory(daq, device_id, channel_index, waveforms)
    raise ValueError(
        f'channel_type was set to {channel_type} but only "qa" and "sg" are allowed'
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
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        input_select: Keys (int) map a specific scope channel with a signal
            source (str), e.g. "channel0_signal_input". For a list of available
            values use daq.help(f"/{device_id}/scopes/0/channels/0/inputselect").
        num_samples: Number of samples.
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
    return shfqa.configure_scope(
        daq,
        device_id,
        input_select=input_select,
        num_samples=num_samples,
        trigger_input=trigger_input,
        num_segments=num_segments,
        num_averages=num_averages,
        trigger_delay=trigger_delay,
    )


def get_scope_data(daq: ziDAQServer, device_id: str, *, timeout: float = 1.0) -> tuple:
    """Queries the scope for data once it is finished.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
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
    return shfqa.get_scope_data(daq, device_id, timeout=timeout)


def start_continuous_sw_trigger(
    daq: ziDAQServer, device_id: str, *, num_triggers: int, wait_time: float
) -> None:
    """Start a continuous trigger.

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
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        num_triggers: Number of triggers to be issued.
        wait_time: Time between triggers in seconds.
    """
    return shfqa.start_continuous_sw_trigger(
        daq, device_id, num_triggers=num_triggers, wait_time=wait_time
    )


def enable_scope(
    daq: ziDAQServer, device_id: str, *, single: int, acknowledge_timeout: float = 1.0
) -> None:
    """Resets and enables the scope.

    Blocks until the host has received the enable acknowledgment from the device.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        single: 0 = continuous mode, 1 = single-shot.
        acknowledge_timeout: Maximum time to wait for diverse acknowledgments
            in the implementation.

    .. versionadded:: 0.1.1
    """
    return shfqa.enable_scope(
        daq, device_id, single=single, acknowledge_timeout=acknowledge_timeout
    )


def configure_weighted_integration(
    daq: ziDAQServer,
    device_id: str,
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
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        weights: Dictionary containing the complex weight vectors, where keys
            correspond to the indices of the integration units to be configured.
        integration_delay: Delay in seconds before starting readout.
        clear_existing: Specify whether to set all the integration weights to
            zero before proceeding with the present upload.
    """
    return shfqa.configure_weighted_integration(
        daq,
        device_id,
        0,
        weights=weights,
        integration_delay=integration_delay,
        clear_existing=clear_existing,
    )


def configure_result_logger_for_spectroscopy(
    daq: ziDAQServer,
    device_id: str,
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
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        result_length: Number of results to be returned by the result logger
        num_averages: Number of averages, will be rounded to 2^n.
        averaging_mode: Select the averaging order of the result, with
            0 = cyclic and 1 = sequential.
    """
    return shfqa.configure_result_logger_for_spectroscopy(
        daq,
        device_id,
        0,
        result_length=result_length,
        num_averages=num_averages,
        averaging_mode=averaging_mode,
    )


def configure_result_logger_for_readout(
    daq: ziDAQServer,
    device_id: str,
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
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        result_source: String-based tag to select the result source in readout
            mode, e.g. "result_of_integration" or "result_of_discrimination".
        result_length: Number of results to be returned by the result logger.
        num_averages: Number of averages, will be rounded to 2^n.
        averaging_mode: Select the averaging order of the result, with
            0 = cyclic and 1 = sequential.
    """
    return shfqa.configure_result_logger_for_readout(
        daq,
        device_id,
        0,
        result_source=result_source,
        result_length=result_length,
        num_averages=num_averages,
        averaging_mode=averaging_mode,
    )


def enable_result_logger(
    daq: ziDAQServer, device_id: str, *, mode: str, acknowledge_timeout: float = 1.0
) -> None:
    """Resets and enables a specified result logger.

    Blocks until the host has received the enable acknowledgment from the device.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        mode: Select between "spectroscopy" and "readout" mode.
        acknowledge_timeout: Maximum time to wait for diverse acknowledgments
            in the implementation.

    .. versionadded:: 0.1.1
    """
    return shfqa.enable_result_logger(
        daq, device_id, 0, mode=mode, acknowledge_timeout=acknowledge_timeout
    )


def get_result_logger_data(
    daq: ziDAQServer,
    device_id: str,
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
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        mode: Select between "spectroscopy" and "readout" mode.
        timeout: Maximum time to wait for data in seconds.

    Returns:
        Array containing the result logger data.
    """
    return shfqa.get_result_logger_data(daq, device_id, 0, mode=mode, timeout=timeout)


def configure_qa_channel(
    daq: ziDAQServer,
    device_id: str,
    *,
    input_range: int,
    output_range: int,
    center_frequency: float,
    mode: str,
) -> None:
    """Configures the RF input and output of a specified QA channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        input_range: Maximal range of the signal input power in dbM.
        output_range: Maximal range of the signal output power in dbM.
        center_frequency: Center Frequency of the analysis band.
        mode: Select between "spectroscopy" and "readout" mode.
    """
    return shfqa.configure_channel(
        daq,
        device_id,
        0,
        input_range=input_range,
        output_range=output_range,
        center_frequency=center_frequency,
        mode=mode,
    )


def configure_qa_sequencer_triggering(
    daq: ziDAQServer,
    device_id: str,
    *,
    aux_trigger: str,
    play_pulse_delay: float = 0.0,
) -> None:
    """Configures the triggering of a specified sequencer.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        aux_trigger: Alias for the trigger used in the sequencer. For a list of
            available values use.
            daq.help(f"/{device_id}/qachannels/0/generator/auxtriggers/0/channel")
        play_pulse_delay: Delay in seconds before the start of waveform playback.
    """
    return shfqa.configure_sequencer_triggering(
        daq,
        device_id,
        0,
        aux_trigger=aux_trigger,
        play_pulse_delay=play_pulse_delay,
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
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index specifying which SG channel to upload the command
            table to.
        command_table: The command table to be uploaded.
    """
    return shfsg.upload_commandtable(daq, device_id, channel_index, command_table)


def configure_marker_and_trigger(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    trigger_in_source: str,
    trigger_in_slope: str,
    marker_out_source: str,
) -> None:
    """Configures the trigger inputs and marker outputs of a specified AWG core.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'
        channel_index: Index of the used SG channel.
        trigger_in_source: Alias for the trigger input used by the
            sequencer. For a list of available values use:
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/awg/auxtriggers/0/channel")
        trigger_in_slope: Alias for the slope of the input trigger used
            by sequencer. For a list of available values use
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/awg/auxtriggers/0/slope")
        marker_out_source: Alias for the marker output source used by the
            sequencer. For a list of available values use
            daq.help(f"/{dev_id}/sgchannels/{channel_index}/marker/source")
    """
    return shfsg.configure_marker_and_trigger(
        daq,
        device_id,
        channel_index,
        trigger_in_source=trigger_in_source,
        trigger_in_slope=trigger_in_slope,
        marker_out_source=marker_out_source,
    )


def configure_sg_channel(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    enable: int,
    output_range: int,
    center_frequency: float,
    rflf_path: int,
) -> None:
    """Configures the RF input and output of a specified SG channel.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
        channel_index: Index of the used SG channel.
        enable: Whether or not to enable the channel.
        output_range: Maximal range of the signal output power in dbM.
        center_frequency: Center Frequency before modulation.
        rflf_path: Switch between RF and LF paths.
    """
    return shfsg.configure_channel(
        daq,
        device_id,
        channel_index,
        enable=enable,
        output_range=output_range,
        center_frequency=center_frequency,
        rflf_path=rflf_path,
    )


def configure_pulse_modulation(
    daq: ziDAQServer,
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
) -> None:
    """Configure the pulse modulation.

    Configures the sine generator to digitally modulate the AWG output, for
    generating single sideband AWG signals.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'
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
    return shfsg.configure_pulse_modulation(
        daq,
        device_id,
        channel_index,
        enable=enable,
        osc_index=osc_index,
        osc_frequency=osc_frequency,
        phase=phase,
        global_amp=global_amp,
        gains=gains,
        sine_generator_index=sine_generator_index,
    )


def configure_sine_generation(
    daq: ziDAQServer,
    device_id: str,
    channel_index: int,
    *,
    enable: int,
    osc_index: int = 0,
    osc_frequency: float = 100e6,
    phase: float = 0.0,
    gains: tuple = (0.0, 1.0, 1.0, 0.0),
    sine_generator_index: int = 0,
) -> None:
    """Configures the sine generator output of a specified SG channel.

    Configures the sine generator output of a specified channel for generating
    continuous wave signals without the AWG.

    Args:
        daq: Instance of a Zurich Instruments API session connected to a Data
            Server. The device with identifier device_id is assumed to already
            be connected to this instance.
        device_id: SHFQC device identifier, e.g. `dev12004` or 'shf-dev12004'.
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
    return shfsg.configure_sine_generation(
        daq,
        device_id,
        channel_index,
        enable=enable,
        osc_index=osc_index,
        osc_frequency=osc_frequency,
        phase=phase,
        gains=gains,
        sine_generator_index=sine_generator_index,
    )
