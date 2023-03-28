from unittest.mock import patch

import pytest

from zhinst.utils.api_compatibility import check_dataserver_device_compatibility
from zhinst.utils.device_status import DeviceStatusFlag, get_device_statuses
from zhinst.utils.exceptions import CompatibilityError


class TestDataServerDeviceCompatibility:
    @pytest.mark.parametrize(
        "flags, match",
        [
            (
                DeviceStatusFlag.IN_USE | DeviceStatusFlag.FW_DOWNGRADE_REQUIRED,
                "requires firmware downgrade",
            ),
            (DeviceStatusFlag.FW_UPGRADE_AVAILABLE, "has firmware upgrade available"),
            (DeviceStatusFlag.FW_UPGRADE_USB, "requires firmware upgrade"),
        ],
    )
    @patch(
        "zhinst.utils.api_compatibility.get_device_statuses", spec=get_device_statuses
    )
    def test_check_dataserver_device_compatibility_error(
        self, mock_get_device_statuses, flags, match
    ):
        mock_get_device_statuses.return_value = {"dev1234": flags}
        with pytest.raises(CompatibilityError, match=match):
            check_dataserver_device_compatibility(None, ["dev1234"])

    @pytest.mark.parametrize(
        "flags, match",
        [
            (DeviceStatusFlag.FW_UPDATE_IN_PROGRESS, "has update in progress"),
        ],
    )
    @patch(
        "zhinst.utils.api_compatibility.get_device_statuses", spec=get_device_statuses
    )
    def test_check_dataserver_device_compatibility_fw_update_in_progress(
        self, mock_get_device_statuses, flags, match
    ):
        mock_get_device_statuses.return_value = {"dev1234": flags}
        with pytest.raises(ConnectionError, match=match):
            check_dataserver_device_compatibility(None, ["dev1234"])

    @pytest.mark.parametrize(
        "flags",
        [
            DeviceStatusFlag.FREE,
            DeviceStatusFlag.IN_USE,
            DeviceStatusFlag.NOT_YET_READY,
            DeviceStatusFlag.UNKNOWN,
            DeviceStatusFlag.CLEAR,
        ],
    )
    @patch(
        "zhinst.utils.api_compatibility.get_device_statuses", spec=get_device_statuses
    )
    def test_check_dataserver_device_compatibility_no_errors(
        self, mock_get_device_statuses, flags
    ):
        mock_get_device_statuses.return_value = {"dev1234": flags}
        check_dataserver_device_compatibility(None, ["dev1234"])
