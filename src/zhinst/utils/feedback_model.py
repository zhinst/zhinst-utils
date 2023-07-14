"""Feedback Data Latency model for PQSC, SHF- and HDAWG systems.

Typical usage example:
```python
model = QCCSFeedbackModel(
    description=get_feedback_system_description(
        generator_type=SGType.HDAWG,
        analyzer_type=QAType.SHFQA,
        pqsc_mode=PQSCMode.DECODER
    )
)
```
"""
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Tuple

import numpy as np


class SGType(IntEnum):
    """Different signal generator types used in a QCCS setup."""

    HDAWG = 1
    SHFSG = 2
    SHFQC = 3


class QAType(IntEnum):
    """Different quantum analyzer types used in a QCCS setup."""

    SHFQA = 1
    SHFQC = 2


class PQSCMode(IntEnum):
    """Different handling of feedback data from the PQSC."""

    REGISTER_FORWARD = 1
    DECODER = 2


class FeedbackPath(IntEnum):
    """Different handling of feedback data from the PQSC.

    .. versionadded:: 0.3
    """

    ZSYNC = 1
    INTERNAL = 3


@dataclass
class QCCSSystemDescription:
    """Describe the behavior of a QCCS system with respect to feedback latency."""

    initial_latency_smpl: int
    """[samples] Minimum latency for the smallest amount of
    integration samples. Always a multiple of 4."""
    initial_steps: int
    """[steps] Integration length increment until the
    first latency increment."""
    pattern: List[Tuple[int, int]]
    """[(clock cycles, steps),...] The pattern of periodic
    latency increments with respect to integration sample increments """
    period_steps: int = 50
    """[steps] Period of the latency increment pattern."""
    latency_in_period_step: int = 25
    """[clock cycles] Latency increment for a full period."""
    rtlogger_correction: int = 0
    """[clock_cycles] Correction needed on top of the RTLogger recorded
    latency to get the latency seen by the sequencer"""


def get_feedback_system_description(
    generator_type: SGType,
    analyzer_type: QAType,
    pqsc_mode: PQSCMode = None,
    feedback_path: FeedbackPath = FeedbackPath.ZSYNC,
) -> QCCSSystemDescription:
    """Returns a QCCSSysDescription object for a given configuration.

    Args:
      generator_type: Signal generator used (SHFSG/HDAWG).
      analyzer_type: Quantum analyzer used.
      pqsc_mode: Mode of operation for the PQSC.
      feedback_path: Used only when the generator type is SHFQC to select
                     between local feedback or through PQSC

    Returns:
      A QCCS system description object to be used in a `QCCSFeedbackModel` object.

    Raises:
      ValueError: Incorrect values for 'generator_type', 'analyzer_type',
                  'pqsc_mode' or 'feedback_path'.

    .. versionchanged:: 0.3

        Added `feedback_path` argument.
    """
    if analyzer_type not in [QAType.SHFQA, QAType.SHFQC]:
        raise ValueError(f"Unknown quantum analyzer type ({analyzer_type})")

    if (
        pqsc_mode in [PQSCMode.DECODER, PQSCMode.REGISTER_FORWARD]
        and feedback_path is FeedbackPath.INTERNAL
    ):
        raise ValueError(
            (
                f"PQSC mode ({pqsc_mode}) incompatible ",
                f"with selected feedback path ({feedback_path})",
            )
        )

    if generator_type is SGType.HDAWG:
        if feedback_path == FeedbackPath.INTERNAL:
            raise ValueError(
                "Internal Feedback can only be used with generator=SGType.SHFQC"
            )
        if pqsc_mode is PQSCMode.REGISTER_FORWARD:
            return QCCSSystemDescription(
                initial_latency_smpl=96,
                initial_steps=5,
                pattern=[(4, 9), (4, 8), (4, 8), (4, 9), (5, 8), (4, 8)],
                rtlogger_correction=2,
            )
        if pqsc_mode is PQSCMode.DECODER:
            return QCCSSystemDescription(
                initial_latency_smpl=100,
                initial_steps=7,
                pattern=[(4, 8), (4, 9), (4, 8), (5, 8), (4, 9), (4, 8)],
                rtlogger_correction=2,
            )
        raise ValueError(f"Unknown PQSC mode ({pqsc_mode})")

    if generator_type in [SGType.SHFSG, SGType.SHFQC]:
        if feedback_path is FeedbackPath.INTERNAL:
            if generator_type != SGType.SHFQC:
                raise ValueError(
                    "Internal Feedback can only be used with generator=SGType.SHFQC"
                )
            if analyzer_type != QAType.SHFQC:
                raise ValueError(
                    "Internal Feedback can only be used with analyzer=QAType.SHFQC"
                )
            if pqsc_mode is not None:
                raise ValueError(
                    (
                        "Internal Feedback can't be used with ",
                        f"the selected pqsc mode ({pqsc_mode})",
                    )
                )
            return QCCSSystemDescription(
                initial_latency_smpl=23,
                initial_steps=1,
                pattern=[(1, 2)] * 25,
            )
        if pqsc_mode is PQSCMode.REGISTER_FORWARD:
            return QCCSSystemDescription(
                initial_latency_smpl=91,
                initial_steps=5,
                pattern=[(3, 9), (5, 8), (5, 8), (2, 9), (5, 8), (5, 8)],
                rtlogger_correction=2,
            )
        if pqsc_mode is PQSCMode.DECODER:
            return QCCSSystemDescription(
                initial_latency_smpl=94,
                initial_steps=7,
                pattern=[(5, 8), (5, 9), (2, 8), (5, 8), (5, 9), (3, 8)],
                rtlogger_correction=2,
            )

        raise ValueError(f"Unknown PQSC mode ({pqsc_mode})")

    raise ValueError(f"Unknown signal generator type ({generator_type})")


@dataclass
class QCCSFeedbackModel:
    """A model that calculates the latency of feedback data.

    Estimates are provided for the selected Signal Generator.
    The 'start trigger' from the PQSC is used as starting point for
    the latency estimate.

    Attributes:
      description: The QCCS system configuration description as returned
                   from get_feedback_system_description()
    """

    description: QCCSSystemDescription

    def get_latency(self, length: int) -> int:
        """Provide the expected latency relative to the integration length.

        Args:
          length: Integration length in samples

        Returns:
          The expected latency in AWG clock cycles
        """
        # before the periodic pattern
        model = np.array(
            [self.description.initial_latency_smpl] * self.description.initial_steps,
            dtype=np.int64,
        )

        # build the periodic pattern
        periodic_mdl = np.array([], dtype=np.int64)
        acc = 0
        for lat_inc, int_steps in self.description.pattern:
            acc += lat_inc
            periodic_mdl = np.concatenate(
                (periodic_mdl, np.array([acc] * int_steps, dtype=np.int64)),
                dtype=np.int64,
            )

        # from integration samples to generator cc
        def f_calculate_cycles():
            index = length // 4
            if index <= self.description.initial_steps:
                return model[index - 1]

            index -= self.description.initial_steps + 1
            lat_full_periods = (
                index // self.description.period_steps
            ) * self.description.latency_in_period_step  # latency from full periods
            index = (
                index % self.description.period_steps
            )  # remainder within the periodic pattern
            # total latency
            return int(
                self.description.initial_latency_smpl
                + periodic_mdl[index]
                + lat_full_periods
            )

        latency_clk = f_calculate_cycles()

        return latency_clk + self.description.rtlogger_correction
