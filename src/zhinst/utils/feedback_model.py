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
from zhinst.timing_models import *  # noqa F401
