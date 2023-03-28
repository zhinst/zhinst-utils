"""Module for device functionality."""
import json
import typing as t
from enum import IntFlag

from zhinst.core import ziDAQServer


class DeviceStatusFlag(IntFlag):
    """Device status codes."""

    CLEAR = 0
    NOT_YET_READY = 1 << 0
    FREE = 1 << 1
    IN_USE = 1 << 2
    FW_UPGRADE_USB = 1 << 3
    FW_UPGRADE_REQUIRED = 1 << 4
    FW_UPGRADE_AVAILABLE = 1 << 5
    FW_DOWNGRADE_REQUIRED = 1 << 6
    FW_DOWNGRADE_AVAILABLE = 1 << 7
    FW_UPDATE_IN_PROGRESS = 1 << 8
    UNKNOWN = 1 << 9


def get_device_statuses(
    daq: ziDAQServer, serials: t.List[str]
) -> t.Dict[str, DeviceStatusFlag]:
    """Get status of one or multiple devices.

    Devices must be visible to the dataserver.

    Args:
        daq: ziDAQServer
        device_serial: Serial of the device whose status is returned.

    Returns:
        A dictionary where device serial is the key and flags as the value.

    Raises:
        RuntimeError: Device is not visible to the dataserver.

    .. versionadded:: 0.3
    """
    devices = json.loads(daq.getString("/zi/devices"))
    try:
        return {
            serial: DeviceStatusFlag(devices[serial.upper()]["STATUSFLAGS"])
            for serial in serials
        }
    except KeyError as error:
        raise RuntimeError(f"Device {error} could not be found.") from error
