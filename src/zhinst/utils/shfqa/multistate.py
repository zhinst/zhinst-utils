"""Zurich Instruments Utility functions for multi-state discrimination."""

import typing as t
from dataclasses import dataclass
from enum import IntEnum
import itertools
import numpy as np
import zhinst.utils.shfqa as shfqa_utils
from zhinst.core import ziDAQServer

DEVICE_MIN_STATES = 2
DEVICE_MAX_STATES = 4
DEVICE_MAX_INTEGRATION_LEN = 4096


@dataclass
class QuditState:
    """Qudit state with associated reference trace.

    Args:
        index: A unique identifier of the state.
        label: The label of the state.
        ref_trace: The reference traces of the qudit. They are typically
            obtained by an averaged scope measurement of the qudit's response to a
            readout pulse when a certain state has been prepared.
    """

    index: int
    label: str
    ref_trace: np.ndarray


class IntegrationWeight:
    """Represents integration weights vectors for one-vs-one classification.

    Differential weight vectors are defined as the complex conjugate of the
    difference between reference traces of two states. They are used for weighed
    integration in the multi-state discrimination units.

    Args:
        state_left: The state corresponding to the reference trace used as the
            left side of the subtraction operator.
        state_right: The state corresponding to the reference trace used as the
            right side of the subtraction operator.
    """

    def __init__(self, state_left: QuditState, state_right: QuditState):
        self._left_state = state_left
        self._right_state = state_right
        self._vector = np.conj(state_left.ref_trace - state_right.ref_trace)
        self.center_threshold_ref()

    @property
    def left_state(self) -> QuditState:
        """The state corresponding to the left side of the subtraction."""
        return self._left_state

    @property
    def right_state(self) -> QuditState:
        """The state corresponding to the right side of the subtraction."""
        return self._right_state

    @property
    def vector(self) -> np.ndarray:
        """The vector of integration weights."""
        return self._vector

    @property
    def threshold(self) -> float:
        """Get the threshold value used together with this weight."""
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        """Sets the threshold value used together with this weight."""
        self._threshold = value

    def scale(self, factor: float) -> None:
        """Scales the weight vector with a factor.

        Args:
            factor: Factor to scale the weight vector with.
        """
        self._vector *= factor

    def __array__(self) -> np.ndarray:
        return self._vector

    def center_threshold(self, trace1: np.ndarray, trace2: np.ndarray) -> None:
        """Center the threshold value between trace1 and trace2.

        This function computes the weighted integration results using trace1
        and trace2 as input and then computes the arithmetic mean of the two
        results.

        Args:
            trace1: The first trace.
            trace2: The second trace.

        Returns:
            The arithmetic mean of the weighted integration results between
            trace1 and trace2.
        """
        res1 = np.real(weighted_integration(self._vector, trace1))
        res2 = np.real(weighted_integration(self._vector, trace2))

        self._threshold = (res1 + res2) / 2

    def center_threshold_ref(self) -> None:
        """Center the threshold value between the left and right reference traces."""
        self.center_threshold(self.left_state.ref_trace, self.right_state.ref_trace)


class QuditSettings:
    """Collection of qudit settings for multistate discrimination.

    Qudit settings are the integration weights, thresholds, and the assignment
    vector for qudit state discrimination. These settings are initialized based
    on reference traces for each state, which need to be provided as input to the
    constructor of this class.

    Args:
        ref_traces: List of (complex-valued) reference traces,
            one vector per state. The reference traces are typically obtained by an
            averaged scope measurement of the readout resonator response when the
            qudit is prepared in a certain state.
    """

    def __init__(self, ref_traces: t.List[np.ndarray]):
        # Number of states equals number of reference traces
        self._num_states = len(ref_traces)

        # First, make sure that all reference traces have an equal length
        first_ref_len = len(ref_traces[0])

        for ref_traces_idx, ref_trace in enumerate(ref_traces[1:]):
            assert len(ref_trace) == first_ref_len, (
                f"The length {len(ref_trace)} of ref_traces[{ref_traces_idx}] "
                + f"differs from the length of ref_traces[0]: {first_ref_len}."
            )

        self._states = {}
        for state_idx, ref_trace in enumerate(ref_traces):
            self._states[state_idx] = QuditState(state_idx, str(state_idx), ref_trace)

        self._weights = []
        for state_left, state_right in itertools.combinations(self._states.values(), 2):
            self._weights.append(IntegrationWeight(state_left, state_right))

        self.normalize_weights()
        # re-center thresholds to the reference traces
        self.reset_thresholds_to_center()

        self._assignment_vec = self.calc_theoretical_assignment_vec()

    @property
    def num_states(self) -> int:
        """Number of states (d) of the qudit."""
        return self._num_states

    @property
    def states(self) -> t.Dict[int, QuditState]:
        """Dictionary of states of the qudit.

        The dictionary keys are state indices and the values are State objects.
        """
        return self._states

    @property
    def weights(self) -> t.List[IntegrationWeight]:
        """List of weight vectors for one-vs-one classification."""
        return self._weights

    @property
    def integration_len(self) -> int:
        """Length of the weight vectors as number of samples."""
        return len(self._weights[0].vector)

    @property
    def thresholds(self) -> t.List[float]:
        """Threshold values, one per weight vector, for one-vs-one classification."""
        return [weight.threshold for weight in self._weights]

    @property
    def assignment_vec(self) -> np.ndarray:
        """Vector assigning state indices for each threshold comparison outcome.

        The vector has 2**( d * (d - 1) / 2 ) elements, where d is the number
        of states of the qudit.
        """
        return self._assignment_vec

    def reset_thresholds_to_center(self) -> None:
        """Resets the thresholds of each weight to the center.

        The thresholds get centered between the results of the weighted
        integration using the reference traces of the corresponding pairs of
        states.
        """
        for weight in self._weights:
            weight.center_threshold_ref()

    def normalize_weights(self) -> None:
        """Scales all weight vectors with a common factor.

        The common factor is chosen such that maximum absolute weight value is 1.
        """
        max_abs_weight = max([np.abs(weight.vector).max() for weight in self._weights])

        factor = 1 / max_abs_weight
        for weight in self._weights:
            weight.scale(factor)

    def calc_theoretical_assignment_vec(self) -> np.ndarray:
        """Calculates the theoretical assignment vector.

        The theoretical assignment vector is determined by the majority vote
        (winner takes all) principle.
        """
        assignment_len = 2 ** len(self._weights)
        assignment_vec = np.zeros(assignment_len, dtype=int)

        for assignment_idx in range(assignment_len):
            state_counts = np.zeros(self._num_states, dtype=int)
            for weight_idx, weight in enumerate(self._weights):
                above_threshold = (assignment_idx & (2**weight_idx)) != 0
                state_idx = (
                    weight.left_state.index
                    if above_threshold
                    else weight.right_state.index
                )
                state_counts[state_idx] += 1
            winner_state = np.argmax(state_counts)
            assignment_vec[assignment_idx] = winner_state

        return assignment_vec


def _get_base_path(dev: str, qa_channel: int) -> str:
    """Gets the base node tree path of the multistate discrimination feature.

    Args:
        dev: The device id.
        qa_channel: The QA channel index.

    Returns:
        The path to the multistate node tree branch.
    """
    return f"/{dev}/qachannels/{qa_channel}/readout/multistate"


def _get_qudit_base_path(dev: str, qa_channel: int, qudit_idx: int) -> str:
    """Gets the base node tree path of a particular qudit.

    Args:
        dev: The device id
        qa_channel: The QA channel index
        qudit_idx: The index of the qudit

    Returns:
        The path to the qudit node tree branch.
    """
    return _get_base_path(dev, qa_channel) + f"/qudits/{qudit_idx}"


def get_settings_transaction(
    dev: str,
    qa_channel: int,
    qudit_idx: int,
    qudit_settings: QuditSettings,
    *,
    enable: bool = True,
) -> t.List[t.Tuple[str, t.Any]]:
    """Compiles a list of settings to apply to the device.

    Args:
        dev: The device id.
        qa_channel: The index of the QA channel
        qudit_idx: The index of the qudit to be configured
        qudit_settings: The qudit settings to be configured
        enable: Whether to enable the qudit (default: True)

    Returns:
        List of settings defining a transaction. Each list entry is a tuple,
        where the first entry specifies the node path and the second entry the
        value to be configured to the respective node.
    """
    # Make sure the number of states is feasible for the device
    assert DEVICE_MIN_STATES <= qudit_settings.num_states <= DEVICE_MAX_STATES, (
        "The number of states must be in the range"
        f"[{DEVICE_MIN_STATES}, {DEVICE_MAX_STATES}] (inclusive)."
    )

    # Make sure the integration length is feasible for the device
    assert qudit_settings.integration_len <= DEVICE_MAX_INTEGRATION_LEN, (
        f"Too long integration length {qudit_settings.integration_len}. "
        f"It must be less than or equal to {DEVICE_MAX_INTEGRATION_LEN}."
    )

    qudit_base_path = _get_qudit_base_path(dev, qa_channel, qudit_idx)

    transaction = []
    transaction.append((qudit_base_path + "/numstates", qudit_settings.num_states))
    transaction.append((qudit_base_path + "/enable", 1 if enable else 0))
    transaction.append(
        (
            f"/{dev}/qachannels/{qa_channel}/readout/integration/length",
            qudit_settings.integration_len,
        )
    )

    # NOTE: Upload only the first d - 1 differential weight vectors.
    # The remaining pairwise difference of results will be computed in
    # real time on the device in order to save hardware resources
    for weight_idx, weight in enumerate(
        qudit_settings.weights[: qudit_settings.num_states - 1]
    ):
        transaction.append(
            (
                qudit_base_path + f"/weights/{weight_idx}/wave",
                weight.vector,
            )
        )

    threshold_base = qudit_base_path + "/thresholds"
    for threshold_idx, threshold in enumerate(qudit_settings.thresholds):
        transaction.append((threshold_base + f"/{threshold_idx}/value", threshold))

    transaction.append(
        (qudit_base_path + "/assignmentvec", qudit_settings.assignment_vec)
    )

    return transaction


def config_to_device(
    daq: ziDAQServer,
    dev: str,
    qa_channel: int,
    qudit_idx: int,
    qudit_settings: QuditSettings,
    *,
    enable: bool = True,
) -> None:
    """Configures the qudit settings to the device.

    Args:
        daq: An instance of core.ziDAQServer
        dev: The device id.
        qa_channel: The index of the QA channel
        qudit_idx: The index of the qudit to be configured
        qudit_settings: The qudit settings to be configured
        enable: Whether to enable the qudit (default: True)
    """
    transaction = get_settings_transaction(
        dev,
        qa_channel=qa_channel,
        qudit_idx=qudit_idx,
        qudit_settings=qudit_settings,
        enable=enable,
    )

    daq.set(transaction)


class _ReslogSource(IntEnum):
    """Values for the result/source node."""

    RESULT_OF_INTEGRATION = 1
    RESULT_OF_DISCRIMINATION = 3


def get_qudits_results(
    daq: ziDAQServer, dev: str, qa_channel: int
) -> t.Dict[int, np.ndarray]:
    """Downloads the qudit results from the device and group them by qudit.

    Depending on the result logger source, this function accesses the multistate
    nodes to determine which integrators were used for which qudit to be able to
    group the results by qudit.

    Args:
        daq: An instance of the core.ziDAQServer class
        dev: The device id.
        qa_channels: The index of the QA channel

    Returns:
        A dictionary with the qudit index keys and result vector values.
    """
    results = shfqa_utils.get_result_logger_data(daq, dev, qa_channel, mode="readout")

    result_source = daq.getInt(f"/{dev}/qachannels/{qa_channel}/readout/result/source")

    base_path = _get_base_path(dev, qa_channel)

    qudits_results = {}
    max_num_qudits = len(daq.listNodes(base_path + "/qudits/*/enable"))
    for qudit_idx in range(max_num_qudits):
        qudit_base_path = _get_qudit_base_path(dev, qa_channel, qudit_idx)
        enable_node_value = daq.getInt(qudit_base_path + "/enable")
        is_enabled = enable_node_value != 0
        if not is_enabled:
            continue

        if result_source == _ReslogSource.RESULT_OF_INTEGRATION:
            start_idx_node = qudit_base_path + "/integrator/indexvec"
            integrator_indices = daq.get(start_idx_node, flat=True)[start_idx_node][0][
                "vector"
            ]
            qudits_results[qudit_idx] = results[integrator_indices]
        elif result_source == _ReslogSource.RESULT_OF_DISCRIMINATION:
            qudits_results[qudit_idx] = results[qudit_idx].astype(int)
        else:
            raise ValueError(f"Unkown result logger source: {result_source}")

    return qudits_results


def weighted_integration(weight_vec: np.ndarray, signal: np.ndarray) -> float:
    """Computes the weighted integration.

    Args:
        weight_vec: Vector of integration weights
        signal: Vector of input signal samples

    Returns:
        The result of the weighted integration.
    """
    return np.dot(weight_vec, signal)


def compare_threshold(threshold: float, integration_result: float) -> bool:
    """Compares an integration result with a threshold.

    Args:
        threshold: The threshold value
        integration_result: The integration result for the comparison

    Returns:
        True if the integration_result is greater than the threshold,
        False otherwise.
    """
    return integration_result > threshold
