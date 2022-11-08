"""Class for frequency sweeps on SHFQA
"""

# Copyright 2022 Zurich Instruments AG

from collections import namedtuple
from dataclasses import dataclass
from enum import Enum, auto
import time
import textwrap
import math
import numpy as np
from zhinst.utils import utils
from zhinst.core import compile_seqc


class _Mapping(Enum):
    LIN = "linear"
    LOG = "log"


class _AveragingMode(Enum):
    CYCLIC = "cyclic"
    SEQUENTIAL = "sequential"


class _TriggerSource(Enum):
    """
    Valid trigger sources for spectroscopy
    Note: the user should write the trigger selection in lowercase letters.
    e.g. "software_trigger0". The strings are transformed to uppercase only
    for this enum, which is needed to distinguish between internal and external
    triggers (see _EXTERNAL_TRIGGER_LIMIT).
    """

    CHANNEL0_TRIGGER_INPUT0 = 0  # Important: start counting with 0
    CHAN0TRIGIN0 = CHANNEL0_TRIGGER_INPUT0

    CHANNEL0_TRIGGER_INPUT1 = auto()
    CHAN0TRIGIN1 = CHANNEL0_TRIGGER_INPUT1

    CHANNEL1_TRIGGER_INPUT0 = auto()
    CHAN1TRIGIN0 = CHANNEL1_TRIGGER_INPUT0

    CHANNEL1_TRIGGER_INPUT1 = auto()
    CHAN1TRIGIN1 = CHANNEL1_TRIGGER_INPUT1

    CHANNEL2_TRIGGER_INPUT0 = auto()
    CHAN2TRIGIN0 = CHANNEL2_TRIGGER_INPUT0

    CHANNEL2_TRIGGER_INPUT1 = auto()
    CHAN2TRIGIN1 = CHANNEL2_TRIGGER_INPUT1

    CHANNEL3_TRIGGER_INPUT0 = auto()
    CHAN3TRIGIN0 = CHANNEL3_TRIGGER_INPUT0

    CHANNEL3_TRIGGER_INPUT1 = auto()
    CHAN3TRIGIN1 = CHANNEL3_TRIGGER_INPUT1

    CHANNEL0_SEQUENCER_TRIGGER0 = auto()
    CHAN0SEQTRIG0 = CHANNEL0_SEQUENCER_TRIGGER0

    CHANNEL1_SEQUENCER_TRIGGER0 = auto()
    CHAN1SEQTRIG0 = CHANNEL1_SEQUENCER_TRIGGER0

    CHANNEL2_SEQUENCER_TRIGGER0 = auto()
    CHAN2SEQTRIG0 = CHANNEL2_SEQUENCER_TRIGGER0

    CHANNEL3_SEQUENCER_TRIGGER0 = auto()
    CHAN3SEQTRIG0 = CHANNEL3_SEQUENCER_TRIGGER0

    SOFTWARE_TRIGGER0 = auto()
    SWTRIG0 = SOFTWARE_TRIGGER0


_EXTERNAL_TRIGGER_LIMIT = _TriggerSource.CHANNEL3_TRIGGER_INPUT1

_SHF_SAMPLE_RATE = 2e9
_MIN_SETTLING_TIME = 80e-9
_MAX_PLAYZERO_CYCLES = 2**30 - 16
_MAX_PLAYZERO_TIME = _MAX_PLAYZERO_CYCLES / _SHF_SAMPLE_RATE


def _check_trigger_source(trigger):
    """
    Checks whether the trigger source exists in the _TriggerSource enumeration

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        trigger: the trigger source setting to be checked
    """
    try:
        _TriggerSource[trigger.upper()]
    except ValueError:
        print(
            (
                "Trigger source needs to be 'channel[0,3]_trigger_input[0,1]', "
                "'channel[0,3]_sequencer_trigger0' or 'software_trigger0'."
            )
        )


def _check_channel_index(daq, device_id, channel_index):
    """
    Checks whether the provided channel index is valid

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        channel_index: index of the qachannel to be checked
    """
    device_type = daq.getString(f"/{device_id}/features/devtype")
    if device_type == "SHFQA4":
        num_qa_channels = 4
    elif device_type == "SHFQA2":
        num_qa_channels = 2
    else:
        # SHFQC
        num_qa_channels = 1
    if channel_index >= num_qa_channels:
        raise ValueError(
            f"Device {device_id} only has a total of {num_qa_channels} QA channels."
        )


def _check_center_freq(center_freq_hz):
    """
    Checks whether the center frequency is within the valid range

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        center_freq_hz: the center frequency to be checked in units Hz
    """
    min_center_freq = 0
    max_center_freq = 8e9
    center_freq_steps = 100e6
    rounding_error = 0.1

    if center_freq_hz < min_center_freq:
        raise ValueError(f"Center frequency must be greater than {min_center_freq}Hz.")
    if center_freq_hz > max_center_freq:
        raise ValueError(f"Center frequency must be less than {max_center_freq}Hz.")
    if center_freq_hz % center_freq_steps > rounding_error:
        raise ValueError(f"Center frequency must be multiple of {center_freq_steps}Hz.")


def _check_in_band_freq(start_freq, stop_freq):
    """
    Checks whether the start/stop frequency for the in-band sweep is in the valid
    range

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        start_freq:
        stop_freq:
    """
    min_offset_freq = -1e9
    max_offset_freq = 1e9

    if start_freq >= stop_freq:
        raise ValueError("Stop frequency must be larger than start_freq frequency.")
    if start_freq < min_offset_freq:
        raise ValueError(f"Start frequency must be greater than {min_offset_freq}Hz.")
    if stop_freq > max_offset_freq:
        raise ValueError(f"Stop frequency must be less than {max_offset_freq}Hz.")


def _check_io_range(range_dbm, min_range):
    """
    Checks whether the supplied input or output range setting is within the device
    boundaries

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        range_dbm: the range setting to be checked in units of dBm
        min_range: lower boundary
    """
    max_range = 10
    range_step = 5
    rounding_error = 0.001
    if range_dbm > max_range + rounding_error:
        raise ValueError(f"Maximum range is {max_range}dBm.")
    if range_dbm < min_range - rounding_error:
        raise ValueError(f"Minimum range is {min_range}dBm.")
    if range_dbm % range_step > rounding_error:
        raise ValueError(f"Range must be multiple of {range_step}dBm.")


def _check_output_range(range_dbm):
    """
    Checks whether the supplied output range setting is within the device boundaries

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        range_dbm: the range setting to be checked in units of dBm
    """
    min_range_output = -30
    _check_io_range(range_dbm, min_range_output)


def _check_input_range(range_dbm):
    """
    Checks whether the supplied output range setting is within the device boundaries

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        range_dbm: the range setting to be checked in units of dBm
    """
    min_range_input = -50
    _check_io_range(range_dbm, min_range_input)


def _check_output_gain(gain):
    """
    Checks whether the supplied output gain setting is within the device boundaries

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        gain: the gain setting to be checked
    """
    max_gain = 1
    min_gain = 0
    if gain < min_gain or gain > max_gain:
        raise ValueError(f"Output gain must be within [{min_gain}, {max_gain}].")


def _check_settling_time(settling_time):
    """
    Checks whether the settling time is within the acceptable range.

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        settling_time: the settling time setting to be checked
    """
    if settling_time < _MIN_SETTLING_TIME:
        raise ValueError(
            f"Settling time {settling_time} s smaller than minimum allowed value: {_MIN_SETTLING_TIME} s!"
        )

    if settling_time > _MAX_PLAYZERO_TIME:
        raise ValueError(
            f"Settling time {settling_time} s greater than maximum allowed value: {_MAX_PLAYZERO_TIME} s!"
        )


def _check_wait_after_integration(wait_after_integration):
    """
    Checks whether the wait time after integration is within the acceptable range.

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        wait_after_integration: the wait time setting to be checked
    """
    if wait_after_integration < 0:
        raise ValueError(
            f"Wait time after integration {wait_after_integration} s"
            " smaller than zero!"
        )

    if wait_after_integration > _MAX_PLAYZERO_TIME:
        raise ValueError(
            f"Wait time after integration {wait_after_integration} s"
            f" greater than maximum allowed value: {_MAX_PLAYZERO_TIME} s!"
        )


def _check_envelope_waveform(wave_vector):
    """
    Checks whether the suplied vector is a valid envelope waveform.

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        wave_vector: the waveform vector to be checked
    """
    if wave_vector is None:
        raise ValueError("No envelope waveform specified.")

    max_envelope_length = 2**16
    if len(wave_vector) > max_envelope_length:
        raise ValueError(
            f"Envelope length exceeds maximum of {max_envelope_length} samples."
        )

    # Note: here, we check that the envelope vector elements are within the unit
    #       circle. This check is repeated by the envelope/wave node but it is
    #       stated here explicitly as a guidance to the user.
    if np.any(np.abs(wave_vector) > 1.0):
        raise ValueError(
            "The absolute value of each envelope vector element must be smaller "
            "than 1."
        )


def _check_mapping(mapping):
    """
    Checks whether the suplied mapping is a valid setting

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        mapping: the setting to be checked
    """
    try:
        _Mapping(mapping.lower())
    except ValueError:
        print("Mapping needs to be 'linear' or 'log'.")


def _check_avg_mode(mode):
    """
    Checks whether the average mode is a valid setting

    Raises a ValueError exception if the checked setting was invalid.

    Arguments:
        mode: the setting to be checked
    """
    try:
        _AveragingMode(mode.lower())
    except ValueError:
        print("Averaging mode needs to be 'cyclic' or 'sequential'.")


def _print_sweep_progress(current, total, freq, newline=False):
    """
    Prints a line indicating the sweep progress

    Arguments:
        current:    the current number of measurements
        total:      the total number of measurements
        freq:       the current frequency
        newline:    specifies whether to print a newline (True)
                    or else a carriage return (False) at the end of the line
    """
    print(
        f"Measurement ({current}/{total}) at {(freq / 1e6):.3f}MHz." + " " * 20,
        end=("\r" if not newline else "\n"),
    )


def _round_for_playzero(time_interval: float, sample_rate: float):
    """
    Rounds a time interval to the granularity of the playZero SeqC command

    Arguments:
        time_interval: the time interval to be rounded for the playZero command
        sample_rate:    the sample rate of the instrument

    Returns:
        rounded the time interval
    """
    playzero_granularity = 16

    # round up the number of samples to multiples of playzero_granularity
    num_samples = (
        ((round(time_interval * sample_rate) + (playzero_granularity - 1)))
        // playzero_granularity
    ) * playzero_granularity
    return num_samples / sample_rate


def _is_subscribed(daq, node_path: str) -> bool:
    """
    Checks whether the daq instance is subscribed to a given node or not

    Arguments:
        daq (ziDAQServer):  an instance of the core.ziDAQServer class
        node_path:          the path of the node to be checked

    Returns:
        True if the node is subscribed, False if not
    """
    # NOTE: currently, daq.listNodes will not respect the subscribedonly flag when the
    # node path does not contain a wildcard. Thus we work around this problem by
    # determining the base path of the node and using a wildcard.
    # Remove this workaround once the underlying bug L1-864 is fixed.
    wildcard_path = "/".join(node_path.split("/")[:-1]) + "/*"
    listed_nodes = daq.listNodes(wildcard_path, subscribedonly=True)
    return node_path in listed_nodes


def _subscribe_with_assert(daq, node_path: str) -> bool:
    """
    Subscribes to a node only if it was not already subscribed

    Raises an AssertionError if the node was already subscribed

    Arguments:
        daq (ziDAQServer):  an instance of the core.ziDAQServer class
        node_path:          the path of the node to be checked
    """
    assert not _is_subscribed(daq, node_path), (
        "The following node was already subscribed:\n"
        + node_path
        + "\n"
        + "This would lead to unexpected behavior!"
    )

    daq.subscribe(node_path)


@dataclass
class SweepConfig:
    """Frequency range settings for a sweep"""

    start_freq: float = -300e6  #: minimum frequency for the sweep
    stop_freq: float = 300e6  #: maximum frequency for the sweep
    num_points: int = 100  #: number of frequency points to measure
    mapping: str = "linear"  #: linear or logarithmic frequency axis
    oscillator_gain: float = 1  #: amplitude gain for the oscillator used for modulation
    settling_time: float = _MIN_SETTLING_TIME
    """time to wait to ensure new frequency took effect in the device under test"""
    wait_after_integration: float = 0.0
    """time to wait after the integration finished until the next frequency is set"""
    use_sequencer: bool = True
    """specify whether to use the fast sequencer-based sweep (True) or the slower
    host-driven sweep (False)"""


@dataclass
class RfConfig:
    """RF in- and ouput settings for a sweep"""

    channel: int = 0  #: device channel to be used
    input_range: int = -5  #: maximal Range of the Signal Input power
    output_range: int = 0  #: maximal Range of the Signal Output power
    center_freq: float = 5e9  #: Center Frequency of the analysis band


@dataclass
class AvgConfig:
    """Averaging settings for a sweep"""

    integration_time: float = 1e-3  #: total time while samples are integrated
    num_averages: int = 1  #: times to measure each frequency point
    mode: str = "cyclic"
    """averaging mode, which can be "cyclic", to first scan the frequency and then
    repeat, or "sequential", to average each point before changing the frequency"""
    integration_delay: float = 272.0e-9
    """time delay after the trigger for the integrator to start"""


@dataclass
class TriggerConfig:
    """Settings for the trigger"""

    source: str = None
    """trigger source. Please refer to the node documentation in the user manual under
    /DEV.../QACHANNELS/n/GENERATOR/AUXTRIGGERS/n/CHANNEL for a list of possible sources.
    The default source (None) means the repetition rate of the experiment will be
    determined by the sequencer using the integration time in AvgConfig and settling
    time in SweepConfig.
    Further note that the software trigger is not supported for the sequencer-based
    sweeps (exception see force_sw_trigger)!"""
    level: float = 0.5  #: trigger level
    imp50: bool = True  #: trigger input impedance - 50 Ohm if True; else high impedance
    force_sw_trigger: bool = False
    """if True, the sequencer program waits for the software trigger even in
    sequencer-based mode. Note, however, that the ShfSweeper python class will not
    generate the software trigger on its own. Thus this mode is only useful if a
    separate API session issues the software triggers!"""


@dataclass
class EnvelopeConfig:
    """Settings for defining a complex envelope for pulsed spectroscopy"""

    waveform: np.complex128 = None  #: the complex envelope waveform vector
    delay: float = 0.0  #: time delay the waveform is generated after the trigger


Config = namedtuple("Config", ["sweep", "avg", "rf", "trig"])

# pylint: disable=too-many-instance-attributes
class ShfSweeper:
    """
    Class to set up and run a sweep on an SHFQA

    Arguments:
        daq (zhinst.core.ziDAQServer):
            ziDAQServer object to communicate with a Zurich Instruments data server
        dev (str):
            The ID of the device to run the sweeper with. For example, `dev12004`.
    """

    def __init__(self, daq, dev):
        self._daq = daq
        self._dev = dev
        self._sweep = SweepConfig()
        self._rf = RfConfig()
        self._avg = AvgConfig()
        self._trig = TriggerConfig()
        # the envelope multiplication is enabled if and only if this member is not None
        self._envelope = None
        self._shf_sample_rate = _SHF_SAMPLE_RATE
        self._result = []

    def run(self):
        """
        Perform a sweep with the specified settings.

        WARNING: During the sweep the following nodes are subscribed and the sync
        command is used to clear all buffers on the data server before the measurement:

        /{dev}/qachannels/{rf.channel}/spectroscopy/result/acquired
        /{dev}/qachannels/{rf.channel}/spectroscopy/result/data/wave

        Returns:
            a dictionary with measurement data of the sweep
        """
        self._init_sweep()
        self._run_freq_sweep()
        return self.get_result()

    def get_result(self):
        """
        Returns:
            a dictionary with measurement data of the last sweep
        """
        data = self._get_result_logger_data()
        vec = self._result
        if not self._sweep.use_sequencer:
            vec = self._average_samples(vec)
        data["vector"] = vec
        props = data["properties"]
        props["centerfreq"] = self._rf.center_freq
        props["startfreq"] = self._sweep.start_freq
        props["stopfreq"] = self._sweep.stop_freq
        props["numpoints"] = self._sweep.num_points
        props["mapping"] = self._sweep.mapping
        return data

    def plot(self):
        """
        Plots power over frequency for last sweep
        """
        import matplotlib.pyplot as plt

        freq = self.get_offset_freq_vector()
        freq_mhz = freq / 1e6
        data = self.get_result()
        power_dbm = utils.volt_rms_to_dbm(data["vector"])
        phase = np.unwrap(np.angle(data["vector"]))
        fig, axs = plt.subplots(2, sharex=True)
        plt.xlabel("freq [MHz]")

        axs[0].plot(freq_mhz, power_dbm)
        axs[0].set(ylabel="power [dBm]")
        axs[0].grid()

        axs[1].plot(freq_mhz, phase)
        axs[1].set(ylabel="phase [rad]")
        axs[1].grid()

        fig.suptitle(f"Sweep with center frequency {self._rf.center_freq / 1e9}GHz")
        plt.show()

    def set_to_device(self):
        """
        Transfer settings to device
        """
        # First, make sure that the configuration is still valid. This is needed
        # since the users might change their instance of the dataclasses
        self._check_config(self._sweep, self._avg, self._rf, self._trig, self._envelope)

        # set configuration to device
        self._configure_rf_frontends()
        if self._is_externally_triggered:
            self._configure_external_trigger()
        self._configure_envelope()
        self._configure_spectroscopy_delay()
        self._configure_integration_time()
        self._daq.sync()

    def configure(
        self,
        sweep_config=None,
        avg_config=None,
        rf_config=None,
        trig_config=None,
        envelope_config=None,
    ):
        """
        Configure and check the settings

        Arguments:
          sweep_config (SweepConfig, optional): @dataclass containing sweep
            configuration (None: default configuration applies)
          avg_config (AvgConfig, optional): @dataclass with averaging configuration
            (None: default configuration applies)
          rf_config (RfConfig, optional): @dataclass with RF configuration
            (None: default configuration applies)
          trig_config (TriggerConfig, optional): @dataclass with trigger
            configuration (None: default configuration applies)
          envelope_config: (EnvelopeConfig, optional): @dataclass configuring
            the envelope for pulse spectroscopy (None: the multiplication with
            the envelope is disabled)
        """

        self._check_config(
            sweep_config, avg_config, rf_config, trig_config, envelope_config
        )

        self._sweep = sweep_config or self._sweep
        self._rf = rf_config or self._rf
        self._avg = avg_config or self._avg
        self._trig = trig_config or self._trig
        # Note: in the case the envelope_config argument is None, the envelope
        # multiplication will be disabled. Hence no "or" statement is used here.
        self._envelope = envelope_config

    def get_configuration(self):
        """
        Returns:
            the configuration of the sweeper class as
            Config(SweepConfig, AvgConfig, RfConfig, TriggerConfig)
        """
        return Config(self._sweep, self._avg, self._rf, self._trig)

    def get_offset_freq_vector(self):
        """
        Get vector of frequency points
        """
        if self._sweep.mapping == _Mapping.LIN.value:
            freq_vec = np.linspace(
                self._sweep.start_freq, self._sweep.stop_freq, self._sweep.num_points
            )
        else:  # log
            start_f_log = np.log10(self._sweep.start_freq + self._rf.center_freq)
            stop_f_log = np.log10(self._sweep.stop_freq + self._rf.center_freq)
            temp_f_vec = np.logspace(start_f_log, stop_f_log, self._sweep.num_points)
            freq_vec = temp_f_vec - self._rf.center_freq

        return freq_vec

    def _check_config(
        self,
        sweep_config=None,
        avg_config=None,
        rf_config=None,
        trig_config=None,
        envelope_config=None,
    ):
        """
        Checks if the supplied configurations are valid
        This function has the same arguments as the public function self.configure()
        """

        if rf_config:
            _check_channel_index(self._daq, self._dev, rf_config.channel)
            _check_center_freq(rf_config.center_freq)
            _check_input_range(rf_config.input_range)
            _check_output_range(rf_config.output_range)
        if sweep_config:
            if self._sweep.use_sequencer and self._sweep.mapping != _Mapping.LIN.value:
                raise ValueError(
                    "Only linear sweeps are supported with the sequencer-based approach"
                )
            _check_in_band_freq(sweep_config.start_freq, sweep_config.stop_freq)
            _check_mapping(sweep_config.mapping)
            _check_output_gain(sweep_config.oscillator_gain)
            _check_settling_time(sweep_config.settling_time)
            _check_wait_after_integration(sweep_config.wait_after_integration)
        if avg_config:
            _check_avg_mode(avg_config.mode)
            self._check_integration_time(avg_config.integration_time)
            self._check_integration_delay(avg_config.integration_delay)
        if trig_config and trig_config.source is not None:
            _check_trigger_source(trig_config.source)
        if envelope_config:
            _check_envelope_waveform(envelope_config.waveform)
            self._check_envelope_delay(envelope_config.delay)

    @property
    def _path_prefix(self) -> str:
        return f"/{self._dev}/qachannels/{self._rf.channel}/"

    @property
    def _acquired_path(self) -> str:
        return self._path_prefix + "spectroscopy/result/acquired"

    @property
    def _spec_enable_path(self) -> str:
        return self._path_prefix + "spectroscopy/result/enable"

    @property
    def _data_path(self) -> str:
        return self._path_prefix + "spectroscopy/result/data/wave"

    @property
    def _is_externally_triggered(self) -> bool:
        if self._trig.source is None:
            return False
        return (
            _TriggerSource[self._trig.source.upper()].value
            <= _EXTERNAL_TRIGGER_LIMIT.value
        )

    @property
    def _is_sw_triggered(self) -> bool:
        if self._trig.source is None:
            return False
        return (
            _TriggerSource[self._trig.source.upper()].value
            == _TriggerSource.SOFTWARE_TRIGGER0.value
        )

    def _configure_rf_frontends(self):
        """
        Configures the RF frontend settings to the device
        """
        # don't set output/input on/off, keep previous user settings
        self._daq.setInt(self._path_prefix + "input/range", self._rf.input_range)
        self._daq.setInt(self._path_prefix + "output/range", self._rf.output_range)
        self._daq.setDouble(self._path_prefix + "centerfreq", self._rf.center_freq)
        self._daq.setDouble(
            self._path_prefix + "oscs/0/gain", self._sweep.oscillator_gain
        )
        self._daq.setString(self._path_prefix + "mode", "spectroscopy")

    def _configure_external_trigger(self):
        """
        Configures the external trigger inputs to the device
        """
        # Note: the following index arithmetic is only valid for HW triggers:
        trig_channel = _TriggerSource[self._trig.source.upper()].value // 2
        trig_input = _TriggerSource[self._trig.source.upper()].value % 2
        trig_path = f"/{self._dev}/qachannels/{trig_channel}/triggers/{trig_input}/"
        self._daq.setDouble(trig_path + "level", self._trig.level)
        self._daq.setInt(trig_path + "imp50", self._trig.imp50)

    def _configure_envelope(self):
        """
        Configures the envelope waveform settings for pulsed spectroscopy to the device
        """
        path = self._path_prefix + "spectroscopy/envelope"
        if self._envelope:
            self._daq.setVector(
                path + "/wave", self._envelope.waveform.astype("complex128")
            )
            self._daq.setInt(path + "/enable", 1)
            self._daq.setDouble(path + "/delay", self._envelope.delay)
        else:
            self._daq.setInt(path + "/enable", 0)

    def _configure_spectroscopy_delay(self):
        """
        Configures the delay for triggering the spectroscopy module to the device
        """
        path = self._path_prefix + "spectroscopy/delay"
        if self._avg:
            self._daq.setDouble(path, self._avg.integration_delay)

    def _configure_integration_time(self):
        """
        Configure the integration time to the device
        """
        spectroscopy_len = round(self._avg.integration_time * self._shf_sample_rate)
        self._daq.setInt(self._path_prefix + "spectroscopy/length", spectroscopy_len)

    def _get_freq_vec_host(self):
        """
        Get the vector of frequencies for the host-based sweep
        """
        single_freq_vec = self.get_offset_freq_vector()
        return self._concatenate_freq_vecs_host(single_freq_vec)

    def _concatenate_freq_vecs_host(self, single_freq_vec):
        """
        Concatenates the vector of frequencies depending on the averaging and triggering
        type for the host-based sweep
        """
        triggered_sequential = (
            self._avg.mode.lower() == _AveragingMode.SEQUENTIAL.value
            and not self._is_sw_triggered
        )
        if self._avg.num_averages == 1 or triggered_sequential:
            freq_vec = single_freq_vec
        elif self._avg.mode == _AveragingMode.CYCLIC.value:
            num_concatenate = self._avg.num_averages - 1
            freq_vec = single_freq_vec
            while num_concatenate > 0:
                num_concatenate -= 1
                freq_vec = np.concatenate((freq_vec, single_freq_vec), axis=None)
        else:  # sequential + sw_trigger
            freq_vec = np.zeros(self._avg.num_averages * self._sweep.num_points)
            for i, f in enumerate(single_freq_vec):
                for j in range(self._avg.num_averages):
                    ind = i * self._avg.num_averages + j
                    freq_vec[ind] = f

        return freq_vec

    def _configure_direct_triggering_host(self):
        """
        Configures the direct triggering of the spectroscopy module in the host-based
        approach
        """
        if self._trig.source is None:
            raise ValueError(
                "Trigger source cannot be None if use_sequencer is set to False in "
                "SweepConfig"
            )
        self._daq.setString(
            self._path_prefix + "spectroscopy/trigger/channel",
            self._trig.source.lower(),
        )

    def _configure_triggering_via_sequencer(self):
        """
        Configures the triggering of the spectroscopy module via the sequencer
        """
        if self._is_sw_triggered and (not self._trig.force_sw_trigger):
            raise ValueError(
                textwrap.dedent(
                    """
                    Software trigger is not supported if use_sequencer is True!

                    We recommend to set the trigger source in TriggerConfig to None when
                    using the sequencer-based sweep, in order to let the sequencer
                    define the repetition rate of the experiment.
                    """
                )
            )

        # the sequencer receives the actual trigger
        if self._trig.source is not None:
            self._daq.setString(
                self._path_prefix + "generator/auxtriggers/0/channel",
                self._trig.source.lower(),
            )
        # the spectroscopy module must use the trigger coming from the sequencer
        self._daq.setString(
            self._path_prefix + "spectroscopy/trigger/channel",
            f"chan{self._rf.channel}seqtrig0",
        )

    def _init_sweep(self):
        """
        Initializes the sweep by configuring all settings to the devices
        """
        self.set_to_device()
        self._stop_result_logger()
        if self._sweep.use_sequencer:
            self._configure_triggering_via_sequencer()
            sequencer_program = self._generate_sequencer_program()
            self._load_sequencer_program(sequencer_program)
        else:
            self._configure_direct_triggering_host()

        self._daq.sync()

    def _stop_result_logger(self):
        """
        Stops the result logger and makes sure it is stopped
        """
        self._daq.setInt(self._spec_enable_path, 0)
        self._daq.sync()
        utils.wait_for_state_change(self._daq, self._spec_enable_path, 0)

    def _issue_single_sw_trigger(self):
        self._daq.syncSetInt(f"/{self._dev}/system/swtriggers/0/single", 1)

    def _enable_measurement(self):
        self._daq.syncSetInt(self._spec_enable_path, 1)

    def _get_data_after_measurement(self):
        data = self._get_result_logger_data()
        return data["vector"]

    def _set_freq_to_device(self, freq: float):
        """
        Configures a frequency on the device

        Arguments:
            freq:   the frequency to be configured
        """
        self._daq.syncSetDouble(self._path_prefix + "oscs/0/freq", freq)

    def _get_freq_sequencer(self, num_acquired: int) -> float:
        """
        Infers the frequency from the number of acquired results in a sequencer-based
        sweep

        Arguments:
            num_acquired:   the current number of acquired results

        Returns:
            the inferred frequency
        """
        if self._avg.mode == _AveragingMode.CYCLIC.value:
            # Cyclic averaging
            return self._sweep.start_freq + self._freq_step * (
                (num_acquired - 1) % self._sweep.num_points
            )
        # Sequential averaging
        return self._sweep.start_freq + self._freq_step * (
            (num_acquired - 1) // self._avg.num_averages
        )

    def _poll_results(
        self, data_path: str, acquired_path: str, expected_num_results: int
    ):
        """
        Repetitively polls for results in sequencer-driven sweeps until the expected
        number of results is acquired.

        Raises a TimeoutError excpetion if no new result is acquired within 10 seconds.

        Arguments:
            data_path:              path to the result data node
                                    Must be subscribed by caller!
            acquired_path:          path to the "acquired" node, which reports the
                                    current number of acquired results
                                    Must be subscribed by caller!
            expected_num_results:   expected total number of results

        Returns:
            the result vector when it becomes available
        """

        poll_time = 0.05
        result_timeout = 10  # seconds

        # avoid too many iterations but print often enough
        print_interval = 0.5  # seconds

        elapsed_time_since_result = 0
        elapsed_time_since_print = print_interval  # force print in first iteration
        results = 0
        result_logger_data = None

        while elapsed_time_since_result < result_timeout:
            poll_start = time.perf_counter()
            poll_results = self._daq.poll(poll_time, timeout_ms=10, flat=True)
            poll_duration = time.perf_counter() - poll_start
            if acquired_path in poll_results:
                results = poll_results[acquired_path]["value"][-1]
                elapsed_time_since_result = 0
            else:
                elapsed_time_since_result += poll_duration

            if data_path in poll_results:
                result_logger_data = poll_results[data_path][0]["vector"]

            if elapsed_time_since_print >= print_interval:
                _print_sweep_progress(
                    results, expected_num_results, self._get_freq_sequencer(results)
                )
                elapsed_time_since_print = 0
            else:
                elapsed_time_since_print += poll_duration

            is_done = (results == expected_num_results) and (
                result_logger_data is not None
            )
            if is_done:
                # report the final progress
                _print_sweep_progress(
                    results,
                    expected_num_results,
                    self._get_freq_sequencer(results),
                    newline=True,
                )
                return result_logger_data

        if results > 0:
            raise TimeoutError(
                f"failed to get a new result in {result_timeout} seconds, so far "
                f"only got {results}!"
            )
        raise TimeoutError(f"failed to get any result in {result_timeout} seconds!")

    def _wait_for_results_host(self, freq, num_results):
        """
        Waits for the results in the host-based sweep

        Arguments:
            freq:           the current frequency (only needed for the status printouts)
            num_results:    the desired number of results to wait for
        """
        poll_time = 0.05
        result_timeout = 10  # seconds

        # avoid too many iterations but print often enough
        print_interval = 0.5  # seconds

        elapsed_time_since_result = 0
        elapsed_time_since_print = print_interval  # force print in first iteration
        results = 0

        while elapsed_time_since_result < result_timeout:
            poll_start = time.perf_counter()
            poll_results = self._daq.poll(poll_time, timeout_ms=10, flat=True)
            poll_duration = time.perf_counter() - poll_start
            if self._acquired_path in poll_results:
                results = poll_results[self._acquired_path]["value"][-1]
                elapsed_time_since_result = 0
            else:
                elapsed_time_since_result += poll_duration

            if elapsed_time_since_print >= print_interval:
                _print_sweep_progress(results, num_results, freq)
                elapsed_time_since_print = 0
            else:
                elapsed_time_since_print += poll_duration

            if results == num_results:
                # we are done - but we must report the final progress
                _print_sweep_progress(results, num_results, freq)
                utils.wait_for_state_change(
                    self._daq, self._spec_enable_path, 0, timeout=1
                )
                return

        if results > 0:
            raise TimeoutError(
                f"failed to get a new result in {result_timeout} seconds, so far "
                f"only got {results}!"
            )
        raise TimeoutError(f"failed to get any result in {result_timeout} seconds!")

    def _wait_for_results_host_sw_trig(self, expected_results, wait_time=1):
        """
        Waits for the results in the host-based sweep using the software trigger

        Arguments:
            expected_results:   the expected number of results
            wait_time:          the expected maximal time to wait for the results
        """
        # leave margin for the swtrigger and the dataserver to be updated
        wait_time = 1.2 * (wait_time + 0.3)
        # iterate often (20ms) to improve performance
        utils.wait_for_state_change(
            self._daq,
            self._acquired_path,
            expected_results,
            timeout=wait_time,
            sleep_time=0.02,
        )

    def _run_freq_sweep(self):
        """
        Runs the frequency sweep.
        Dispatches between the different sweep approaches.
        """
        if self._sweep.use_sequencer:
            self._run_freq_sweep_sequencer()
        elif self._is_sw_triggered:
            self._run_freq_sweep_host_sw_trig()
        else:
            self._run_freq_sweep_host()

    def _run_freq_sweep_sequencer(self):
        """
        Runs the frequency sweep with the sequencer-based approach.
        """
        self._print_sweep_details()
        num_results = self._configure_result_length_and_averages_sequencer()
        _subscribe_with_assert(self._daq, self._data_path)
        _subscribe_with_assert(self._daq, self._acquired_path)
        self._daq.sync()
        self._enable_measurement()
        self._enable_sequencer()
        try:
            self._result = self._poll_results(
                self._data_path, self._acquired_path, num_results
            )
        finally:
            self._daq.unsubscribe(self._data_path)
            self._daq.unsubscribe(self._acquired_path)

    def _run_freq_sweep_host_sw_trig(self):
        """
        Runs the frequency sweep with the host-based approach using the software trigger
        """
        self._print_sweep_details()
        freq_vec = self._get_freq_vec_host()
        self._configure_result_length_and_averages_host()
        self._enable_measurement()

        for i, freq in enumerate(freq_vec):
            self._set_freq_to_device(freq)
            _print_sweep_progress(i + 1, len(freq_vec), freq)
            self._issue_single_sw_trigger()
            self._wait_for_results_host_sw_trig(
                expected_results=i + 1, wait_time=self._avg.integration_time
            )

        utils.wait_for_state_change(self._daq, self._spec_enable_path, 0, timeout=1.0)
        self._result = self._get_data_after_measurement()

    def _run_freq_sweep_host(self):
        """
        Runs the frequency sweep with the host-based approach (not software-triggered)
        """
        self._print_sweep_details()
        freq_vec = self._get_freq_vec_host()
        num_results = self._configure_result_length_and_averages_host()
        self._result = []
        _subscribe_with_assert(self._daq, self._acquired_path)
        self._daq.sync()
        for freq in freq_vec:
            self._set_freq_to_device(freq)
            self._enable_measurement()
            try:
                self._wait_for_results_host(freq, num_results)
            except Exception as wait_exception:
                # make sure we also unsubscribe from the node in case of an exception
                self._daq.unsubscribe(self._acquired_path)
                raise wait_exception

            self._result = np.append(self._result, self._get_data_after_measurement())

        # after the sweep has finished, we unsubscribe from the node
        self._daq.unsubscribe(self._acquired_path)

    @property
    def actual_settling_time(self) -> float:
        """Wait time between setting new frequency and triggering of integration.

        Note: the granularity of this time is 16 samples (8 ns).
        """
        return _round_for_playzero(
            self._sweep.settling_time,
            sample_rate=self._shf_sample_rate,
        )

    @property
    def actual_hold_off_time(self) -> float:
        """Wait time after triggering the integration unit until the next cycle.

        Note: the granularity of this time is 16 samples (8 ns).
        """

        # ensure safe hold-off time for the integration results to be written to the external RAM.
        min_hold_off_time = 1032e-9

        return _round_for_playzero(
            max(
                min_hold_off_time,
                self._avg.integration_delay
                + self._avg.integration_time
                + self._sweep.wait_after_integration,
            ),
            sample_rate=self._shf_sample_rate,
        )

    @property
    def predicted_cycle_time(self) -> float:
        """Predicted duration of each cycle of the spectroscopy loop.

        Note: this property only applies in self-triggered mode, which is active
        when the trigger source is set to None and `use_sequencer` is True.
        """
        return self.actual_settling_time + self.actual_hold_off_time

    def _get_playzero_hold_off_samples(self) -> int:
        """
        Returns the hold-off time needed per iteration of the the inner-most
        loop of the SeqC program. The return value respects the minimal hold-off time
        and the granularity of the playZero SeqC command.

        Returns:
            the number of samples corresponding to the hold-off time
        """

        return round(self.actual_hold_off_time * self._shf_sample_rate)

    def _get_playzero_settling_samples(self) -> int:
        """
        Returns an integer number of samples corresponding to the settling time
        The return value respects the granularity of the playZero SeqC command.

        Returns:
            the number of samples corresponding to the settling time
        """
        return round(self.actual_settling_time * self._shf_sample_rate)

    @property
    def _freq_step(self) -> float:
        """
        Returns the frequency step size according to the sweep settings
        """
        return (self._sweep.stop_freq - self._sweep.start_freq) / (
            self._sweep.num_points - 1
        )

    def _generate_sequencer_program(self):
        """
        Internal method, which generates the SeqC code for a sweep
        """

        seqc_header = textwrap.dedent(
            f"""
            const OSC0 = 0;
            setTrigger(0);
            configFreqSweep(OSC0, {self._sweep.start_freq}, {self._freq_step});
            """
        )

        seqc_wait_for_trigger = (
            "waitDigTrigger(1);"
            if self._trig.source is not None
            else "// self-triggering mode"
        )

        seqc_loop_body = textwrap.dedent(
            f"""
            {seqc_wait_for_trigger}

            // define time from setting the oscillator frequency to sending
            // the spectroscopy trigger
            playZero({self._get_playzero_settling_samples()});

            // set the oscillator frequency depending on the loop variable i
            setSweepStep(OSC0, i);
            resetOscPhase();

            // define time to the next iteration
            playZero({self._get_playzero_hold_off_samples()});

            // trigger the integration unit and pulsed playback in pulsed mode
            setTrigger(1);
            setTrigger(0);
            """
        )

        averaging_loop_arguments = f"var j = 0; j < {self._avg.num_averages}; j++"
        sweep_loop_arguments = f"var i = 0; i < {self._sweep.num_points}; i++"

        if self._avg.mode == _AveragingMode.CYCLIC.value:
            outer_loop_arguments = averaging_loop_arguments
            inner_loop_arguments = sweep_loop_arguments
        else:
            outer_loop_arguments = sweep_loop_arguments
            inner_loop_arguments = averaging_loop_arguments

        seqc = (
            seqc_header
            + textwrap.dedent(
                f"""
                for({outer_loop_arguments}) {{
                    for({inner_loop_arguments}) {{"""
            )
            + textwrap.indent(seqc_loop_body, " " * 8)
            + textwrap.dedent(
                """
                    }
                }
                """
            )
        )

        return seqc

    def _load_sequencer_program(self, sequencer_program: str, timeout: float = 10):
        """
        Compiles and loads a sequencer program for the fast sweep"

        Arguments:
            sequencer_program:  the sequencer program to be compiled and loaded
            timeout:            the maximum time to wait during compilation in seconds
        """

        # first, reset the sequencer
        self._daq.syncSetInt(self._path_prefix + "generator/reset", 1)

        device_type = self._daq.getString(f"/{self._dev}/features/devtype")
        device_options = self._daq.getString(f"/{self._dev}/features/options")
        elf, _ = compile_seqc(
            sequencer_program,
            device_type,
            device_options,
            self._rf.channel,
            sequencer="qa",
        )
        self._daq.setVector(
            f"/{self._dev}/qachannels/{self._rf.channel}/generator/elf/data", elf
        )

        # wait until the device becomes ready after program upload
        utils.wait_for_state_change(
            self._daq, self._path_prefix + "generator/ready", 1, timeout=1.0
        )
        time.sleep(0.1)

    def _enable_sequencer(self):
        """
        Starts the sequencer for the sequencer-based sweep
        """
        self._daq.setInt(self._path_prefix + "generator/single", 1)
        self._daq.syncSetInt(self._path_prefix + "generator/enable", 1)
        hundred_milliseconds = 0.1
        time.sleep(hundred_milliseconds)

    def _print_sweep_details(self):
        detail_str = (
            f"Run a sweep with {self._sweep.num_points} frequency points in the range of "
            f"[{self._sweep.start_freq / 1e6}, {self._sweep.stop_freq / 1e6}] MHz + "
            f"{self._rf.center_freq / 1e9} GHz. \n"
            f"Mapping is {self._sweep.mapping}. \n"
            f"Integration time = {self._avg.integration_time} sec. \n"
            f"Measures {self._avg.num_averages} times per frequency point. \n"
            f"Averaging mode is {self._avg.mode}.\n"
        )
        if self._trig.source is not None:
            detail_str += f"Trigger source is {self._trig.source.lower()}."
        else:
            detail_str += str(
                "Trigger source is set to None, which means the sequencer "
                "defines the repetition rate."
            )
        print(detail_str)

    def _configure_result_length_and_averages_host(self) -> int:
        """
        Configures the result vector length and number of averages for the host-based
        sweep to the device

        Returns:
            the configured number of results
        """
        if self._is_sw_triggered:
            num_results = self._sweep.num_points * self._avg.num_averages
        elif self._avg.mode.lower() == _AveragingMode.SEQUENTIAL.value:
            num_results = self._avg.num_averages
        else:
            num_results = 1
        self._daq.setInt(self._path_prefix + "spectroscopy/result/length", num_results)
        # for the host-based approach, we always average in software, thus set the
        # hardware averages to 1
        self._daq.setInt(self._path_prefix + "spectroscopy/result/averages", 1)
        return num_results

    def _configure_result_length_and_averages_sequencer(self) -> int:
        """
        Configures the result vector length and number of averages for the
        sequencer-based sweep to the device

        Returns:
            the expected total number of results, which is the product of the result
            vector length and number of averages
        """
        self._daq.setString(
            self._path_prefix + "spectroscopy/result/mode", self._avg.mode
        )
        self._daq.setInt(
            self._path_prefix + "spectroscopy/result/length", self._sweep.num_points
        )
        self._daq.setInt(
            self._path_prefix + "spectroscopy/result/averages", self._avg.num_averages
        )
        return self._sweep.num_points * self._avg.num_averages

    def _get_result_logger_data(self):
        result_path = self._path_prefix + "spectroscopy/result/data/wave"
        data = self._daq.get(result_path, flat=True)
        return data[result_path.lower()][0]

    def _average_samples(self, vec):
        if self._avg.num_averages == 1:
            return vec

        avg_vec = np.zeros(self._sweep.num_points, dtype="complex")
        if self._avg.mode == _AveragingMode.CYCLIC.value:
            total_measurements = self._sweep.num_points * self._avg.num_averages
            for i in range(self._sweep.num_points):
                avg_range = range(i, total_measurements, self._sweep.num_points)
                avg_vec[i] = np.mean(vec[avg_range])
        else:  # sequential
            for i in range(self._sweep.num_points):
                start_ind = i * self._avg.num_averages
                avg_range = range(start_ind, start_ind + self._avg.num_averages)
                avg_vec[i] = np.mean(vec[avg_range])

        return avg_vec

    def _check_integration_time(self, integration_time_s):
        max_int_len = ((2**23) - 1) * 4
        min_int_len = 4
        max_integration_time = max_int_len / self._shf_sample_rate
        min_integration_time = min_int_len / self._shf_sample_rate
        if integration_time_s < min_integration_time:
            raise ValueError(
                f"Integration time below minimum of {min_integration_time}s."
            )
        if integration_time_s > max_integration_time:
            raise ValueError(
                f"Integration time exceeds maximum of {max_integration_time}s."
            )

    def _check_delay(self, resolution_ns, min_s, max_s, val_s):
        if val_s > max_s or val_s < min_s:
            raise ValueError(f"Delay out of bounds! {min_s} <= delay <= {max_s}")
        val_ns = val_s * 1e9
        val_ns_modulo = val_ns % resolution_ns
        if not math.isclose(val_ns_modulo, 0.0):
            raise ValueError(
                f"Delay {val_ns} ns not in multiples of {resolution_ns} ns."
            )

    def _check_integration_delay(self, integration_delay_s):
        resolution_ns = 2
        max_s = 131e-6
        self._check_delay(resolution_ns, 0, max_s, integration_delay_s)

    def _check_envelope_delay(self, delay_s):
        resolution_ns = 2
        max_s = 131e-6
        self._check_delay(resolution_ns, 0, max_s, delay_s)
