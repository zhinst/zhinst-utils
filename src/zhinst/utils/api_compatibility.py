"""Functionality for API compatibility."""
import typing as t

import zhinst.core as zi

from zhinst.utils.device_status import DeviceStatusFlag, get_device_statuses
from zhinst.utils.exceptions import CompatibilityError


def check_dataserver_device_compatibility(daq: zi.ziDAQServer, serials: t.List[str]):
    """Check LabOne DataServer and device firmware compatibility.

    Args:
        daq: ziDAQServer
        serials: Serials of the devices whose compatibility is checked.

    Raises:
        ConnectionError: If a device update is in progress.
        CompatibilityError: If version compatibility issues are found.
            The error message will show the actions needed per device.

    .. versionadded:: 0.3
    """
    statuses = get_device_statuses(daq, serials)
    errors = []
    for serial, flags in statuses.items():
        if DeviceStatusFlag.FW_UPDATE_IN_PROGRESS in flags:
            raise ConnectionError(
                f"Device '{serial}' has update in progress. Wait for update to finish."
            )
        if DeviceStatusFlag.FW_UPGRADE_AVAILABLE in flags:
            errors.append(
                f"Device '{serial}' has firmware upgrade available."
                "Please upgrade the device firmware."
            )
        if (
            DeviceStatusFlag.FW_UPGRADE_REQUIRED in flags
            or DeviceStatusFlag.FW_UPGRADE_USB in flags
        ):
            errors.append(
                f"Device '{serial}' requires firmware upgrade. "
                "Please upgrade the device firmware."
            )
        if DeviceStatusFlag.FW_DOWNGRADE_AVAILABLE in flags:
            errors.append(
                f"Device '{serial}' has firmware downgrade available. "
                "Please downgrade the device firmware or update LabOne."
            )
        if DeviceStatusFlag.FW_DOWNGRADE_REQUIRED in flags:
            errors.append(
                f"Device '{serial}' requires firmware downgrade. "
                "Please downgrade the device firmware or update LabOne."
            )
    if errors:
        raise CompatibilityError(
            "LabOne and device firmware version compatibility issues were found.\n"
            + "\n".join(errors)
        )
