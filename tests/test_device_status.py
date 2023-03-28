import json
from unittest.mock import patch

import pytest

from zhinst.utils.device_status import DeviceStatusFlag, get_device_statuses


class TestGetDeviceStatus:
    @pytest.fixture
    @patch("zhinst.core.ziDAQServer")
    def mock_daq(self, daq):
        return daq

    @pytest.mark.parametrize(
        "status, enums",
        [
            (1, DeviceStatusFlag.NOT_YET_READY),
            (2, DeviceStatusFlag.FREE),
            (4, DeviceStatusFlag.IN_USE),
            (8, DeviceStatusFlag.FW_UPGRADE_USB),
            (16, DeviceStatusFlag.FW_UPGRADE_REQUIRED),
            (32, DeviceStatusFlag.FW_UPGRADE_AVAILABLE),
            (64, DeviceStatusFlag.FW_DOWNGRADE_REQUIRED),
            (128, DeviceStatusFlag.FW_DOWNGRADE_AVAILABLE),
            (256, DeviceStatusFlag.FW_UPDATE_IN_PROGRESS),
            (512, DeviceStatusFlag.UNKNOWN),
            (132, DeviceStatusFlag.IN_USE | DeviceStatusFlag.FW_DOWNGRADE_AVAILABLE),
            (0, DeviceStatusFlag.CLEAR),
        ],
    )
    def test_device_status_code(self, mock_daq, status, enums):
        resp = {"DEV123": {"STATUSFLAGS": status}, "DEV345": {"STATUSFLAGS": 16}}
        mock_daq.getString.return_value = json.dumps(resp)
        statuses = {"DEV123": enums, "DEV345": DeviceStatusFlag.FW_UPGRADE_REQUIRED}
        assert get_device_statuses(mock_daq, serials=["DEV123", "DEV345"]) == statuses

    def test_device_not_found(self, mock_daq):
        mock_daq.getString.return_value = json.dumps({})
        with pytest.raises(RuntimeError, match="Device 'DEV123' could not be found."):
            get_device_statuses(mock_daq, serials=["DEV123"])
