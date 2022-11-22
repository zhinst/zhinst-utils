import pytest

from zhinst.utils.feedback_model import *


def test_valid_configuration():
    model = QCCSFeedbackModel(
        description=get_feedback_system_description(
            generator_type=SGType.HDAWG,
            analyzer_type=QAType.SHFQA,
            pqsc_mode=PQSCMode.DECODER,
        )
    )
    model = QCCSFeedbackModel(
        description=get_feedback_system_description(
            generator_type=SGType.HDAWG,
            analyzer_type=QAType.SHFQC,
            pqsc_mode=PQSCMode.REGISTER_FORWARD,
        )
    )
    model = QCCSFeedbackModel(
        description=get_feedback_system_description(
            generator_type=SGType.SHFSG,
            analyzer_type=QAType.SHFQA,
            pqsc_mode=PQSCMode.DECODER,
        )
    )
    model = QCCSFeedbackModel(
        description=get_feedback_system_description(
            generator_type=SGType.SHFSG,
            analyzer_type=QAType.SHFQC,
            pqsc_mode=PQSCMode.REGISTER_FORWARD,
        )
    )
    model = QCCSFeedbackModel(
        description=get_feedback_system_description(
            generator_type=SGType.SHFQC,
            analyzer_type=QAType.SHFQC,
            pqsc_mode=PQSCMode.DECODER,
        )
    )
    model = QCCSFeedbackModel(
        description=get_feedback_system_description(
            generator_type=SGType.SHFQC,
            analyzer_type=QAType.SHFQC,
            pqsc_mode=PQSCMode.REGISTER_FORWARD,
        )
    )


def test_invalid_sg_type():
    with pytest.raises(ValueError):
        QCCSFeedbackModel(
            description=get_feedback_system_description(
                generator_type=max(SGType) + 1,
                analyzer_type=QAType.SHFQC,
                pqsc_mode=PQSCMode.REGISTER_FORWARD,
            )
        )


def test_invalid_qa_type():
    with pytest.raises(ValueError):
        QCCSFeedbackModel(
            description=get_feedback_system_description(
                generator_type=SGType.HDAWG,
                analyzer_type=max(QAType) + 1,
                pqsc_mode=PQSCMode.REGISTER_FORWARD,
            )
        )


def test_invalid_pqsc_mode():
    with pytest.raises(ValueError):
        QCCSFeedbackModel(
            description=get_feedback_system_description(
                generator_type=SGType.HDAWG,
                analyzer_type=QAType,
                pqsc_mode=max(PQSCMode) + 1,
            )
        )
