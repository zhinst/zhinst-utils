"""Zurich Instruments LabOne Python API Utility Functions.

This module provides basic utility functions to ease the use of the native
Python API zhinst-core.
"""

import os
import re
import time
import warnings
import socket
import typing as t
from pathlib import Path
import datetime

try:
    # load_labone_mat() requires scipy.io.loadmat()
    import scipy.io
except ImportError as e:
    # No fallback. No complaints upon importing zhinst.utils, handle/raise
    # exception when the function load_labone_mat() is called.
    __SCIPY_IMPORT_ERROR = e
import numpy as np
import zhinst.core as zi


def create_api_session(
    device_serial: str,
    api_level: int,
    server_host: str = None,
    server_port: int = 8004,
    *,
    required_devtype: str = None,
    required_options: str = None,
    required_err_msg: str = None,
) -> t.Tuple[zi.ziDAQServer, str, t.Dict]:
    """Create an API session for the specified device.

    Args:
      device_serial: A string specifying the device serial number. For
        example, 'uhf-dev2123' or 'dev2123'.
      api_level: The targeted API level used by the code where the returned API
        session will be used. The maximum API level you may use is defined by the
        device class. HF2 only supports API level 1 and other devices support
        API level 6. You should try to use the maximum level possible to enable
        extended API features.
      server_host: A hostname or IP address. The data server can be omitted
        if the targeted device is an MF* device or a local data server is running.
        In this case it will try to connect to the local data server or device
        internal data server (local server has priority).
      server_port: The port number of the data server. The default port is 8004.
      required_devtype: Deprecated: This option will be ignored.
      required_options: Deprecated: This option will be ignored.
      required_err_msg: Deprecated: This option will be ignored.

    Returns:
      daq: An instance of the core.ziDAQServer class
        (representing an API session connected to a Data Server).
      device: The device's ID, this is the string that specifies the
        device's node branch in the data server's node tree.
      props: The device's discovery properties as returned by the
        ziDiscovery get() method.
    """
    if required_devtype is not None:
        raise DeprecationWarning(
            "required_devtype is not supported anymore and will be removed in "
            "the future."
        )
    if required_options is not None:
        raise DeprecationWarning(
            "required_options is not supported anymore and will be removed in "
            "the future."
        )
    if required_err_msg is not None:
        raise DeprecationWarning(
            "required_error_msg is not supported anymore and will be removed "
            "in the future."
        )

    class SessionInfo:
        """Information about the Session."""

        device_serial = None
        data_server = None
        interfaces = None
        api_level = None
        daq = None

    if not device_serial.startswith("dev"):
        # Assume it has a prefix (e.g. 'mf-', 'uhf-') and strip that away
        prefix_end = device_serial.find("-")
        if prefix_end != -1:
            device_serial = device_serial[prefix_end + 1 :]  # noqa: E203
        else:
            raise RuntimeError(
                "Device serial is invalid. It should be of the form: "
                "dev3225 or uhf-dev2123."
            )

    session_info = SessionInfo()
    session_info.device_serial = device_serial
    session_info.api_level = api_level

    discovery = zi.ziDiscovery()
    device_id = discovery.find(session_info.device_serial).lower()
    discovery_info = discovery.get(device_id)

    if server_host is None:
        if discovery_info["serveraddress"] != "127.0.0.1" and not discovery_info[
            "devicetype"
        ].upper().startswith("MF"):
            raise DeprecationWarning(
                "Please provide a server address for a data server."
            )
        if not discovery_info["discoverable"]:
            raise RuntimeError(
                "The specified device {} is not discoverable from the API."
                "Please ensure the device is powered-on and visible using the "
                "LabOne User Interface.".format(session_info.device_serial)
            )
        # Since it's an MF device the discovery should return its own data server as
        # server address or it's the local data server
        session_info.data_server = (
            discovery_info["serveraddress"],
            discovery_info["serverport"],
        )
    else:
        session_info.data_server = (socket.gethostbyname(server_host), server_port)

    session_info.interfaces = discovery_info["interfaces"]

    if not discovery_info["available"]:
        if (
            discovery_info["serveraddress"] != session_info.data_server[0]
            and discovery_info["owner"].upper() != "PCIE"
        ):
            error_message = "Device {} is not available: ".format(
                session_info.device_serial
            )
            if discovery_info["status"].startswith("In use"):
                error_message += "In use by {}".format(discovery_info["owner"])
            else:
                error_message += discovery_info["status"]
            raise RuntimeError(error_message)
    try:
        session_info.daq = zi.ziDAQServer(
            session_info.data_server[0],
            session_info.data_server[1],
            session_info.api_level,
        )
    except RuntimeError as error:
        raise RuntimeError(
            "Failed to connect to the data server {}:"
            "{}".format(session_info.data_server[0], session_info.data_server[1])
        ) from error

    connected = False

    for interface in session_info.interfaces:
        try:
            print(
                "Trying to connect to {} on interface {}".format(
                    session_info.device_serial, interface
                )
            )
            session_info.daq.connectDevice(session_info.device_serial, interface)
            connected = True
            print(
                "Connected to {} via data server "
                "{}:{} and interface {}".format(
                    session_info.device_serial,
                    session_info.data_server[0],
                    session_info.data_server[1],
                    interface,
                )
            )
            break
        except Exception:
            continue

    if not connected:
        raise RuntimeError(
            "Failed to connect device {} to "
            "data server {}. Make sure the "
            "device is connected and turned on".format(
                session_info.device_serial, session_info.data_server
            )
        )

    return (session_info.daq, session_info.device_serial, discovery_info)


def api_server_version_check(daq: zi.ziDAQServer) -> bool:
    """Check the consistency of the used version in the LabOne stack.

    Issue a warning and return False if the release version of the API used in
    the session (daq) does not have the same release version as the Data Server
    (that the API is connected to). If the versions match return True.

    Args:
      daq (ziDAQServer): An instance of the core.ziDAQServer class
        (representing an API session connected to a Data Server).

    Returns:
      Flag if the Versions of API and Data Server match.

    Raises:
        Warning: If the Versions of API and Data Server do not match.
    """
    api_version = daq.version()
    api_revision = daq.revision()
    server_version = daq.getString("/zi/about/version")
    server_revision = daq.getInt("/zi/about/revision")
    if api_version != server_version:
        message = (
            "There is a mismatch between the versions of the API and Data Server. "
            "The API reports version `{}' (revision: {}) whilst the Data Server has "
            "version `{}' (revision {}). See the ``Compatibility'' Section in the "
            "LabOne Programming Manual for more information.".format(
                api_version, api_revision, server_version, server_revision
            )
        )
        warnings.warn(message)
        return False
    return True


def default_output_mixer_channel(
    discovery_props: t.Dict, output_channel: int = 0
) -> int:
    """Return an instrument's default output mixer channel.

    Based on the specified `devicetype` and `options` discovery properties and
    the hardware output channel.

    This utility function is used by the core examples and returns a node
    available under the /devX/sigouts/0/{amplitudes,enables}/ branches.

    Args:
      discovery_props: A device's discovery properties as returned by
        ziDiscovery's get() method.
      output_channel: The zero-based index of the hardware
        output channel for which to return an output mixer channel.

    Returns:
      The zero-based index of an available signal output mixer channel.

    Raises:
      Exception: If an invalid signal input index was provided.
    """
    # The logic below assumes the device type is one of the following.
    assert discovery_props["devicetype"] in [
        "HF2IS",
        "HF2LI",
        "UHFLI",
        "UHFAWG",
        "UHFQA",
        "MFIA",
        "MFLI",
    ], "Unknown device type: {}.".format(discovery_props["devicetype"])

    if re.match(r"UHF(LI|AWG)", discovery_props["devicetype"]) and (
        "MF" not in discovery_props["options"]
    ):
        if output_channel == 0:
            return 3
        if output_channel == 1:
            return 7
        raise Exception(
            "Invalid output channel `{}`, UHF Instruments have two signal "
            "ouput channels (0, 1).".format(output_channel)
        )

    if re.match(r"UHFQA", discovery_props["devicetype"]):
        if output_channel == 0:
            return 0
        if output_channel == 1:
            return 1
        raise Exception(
            "Invalid output channel `{}`, UHF Instruments have two signal "
            "ouput channels (0, 1).".format(output_channel)
        )

    if re.match(r"HF2LI", discovery_props["devicetype"]) and (
        "MF" not in discovery_props["options"]
    ):
        if output_channel == 0:
            return 6
        if output_channel == 1:
            return 7
        raise Exception(
            "Invalid output channel `{}`, HF2 Instruments have two signal output"
            "channels (0, 1).".format(output_channel)
        )

    if re.match(r"(MFLI|MFIA)", discovery_props["devicetype"]) and (
        "MD" not in discovery_props["options"]
    ):
        if output_channel == 0:
            return 1
        raise Exception(
            f"Invalid output channel `{output_channel}`, MF Instruments have one "
            "signal output channel (0)."
        )

    return 0 if output_channel == 0 else 1


def autoDetect(daq: zi.ziDAQServer, exclude: t.List[str] = None) -> str:
    """Return one of the devices connected to the Data Server.

    Return a string containing the first device ID (not in the exclude list)
    that is attached to the Data Server connected via daq, an instance of the
    core.ziDAQServer class.

    Args:
      daq: An instance of the core.ziDAQServer class
        (representing an API session connected to a Data Server).
      exclude: A list of strings specifying devices to
        exclude. autoDetect() will not return the name of a device in this
        list.

    Returns:
      Device ID of a device connected to the Data Server not in exclude.

    Raises:
      RuntimeError: If no device was found.
      RuntimeError: If daq is not an instance of core.ziDAQServer.

    Example:
      >>> zhinst.utils
      >>> daq = zhinst.utils.autoConnect()
      >>> device = zhinst.utils.autoDetect(daq)
    """
    if not isinstance(daq, zi.ziDAQServer):
        raise RuntimeError("First argument must be an instance of core.ziDAQServer")
    nodes = daq.listNodes("/", 0)
    devs = [node for node in nodes if re.match("dev*", node, re.IGNORECASE)]
    if exclude is None:
        exclude = []
    if not isinstance(exclude, list):
        exclude = [exclude]
    exclude = [x.lower() for x in exclude]
    devs = [dev for dev in devs if dev.lower() not in exclude]
    if not devs:
        raise RuntimeError(
            "No Device found. Make sure that the device is connected to the host via "
            "USB or Ethernet and that it is switched on. It may also be necessary to "
            "issue a connectDevice command."
        )
    # Found at least one device -> selection valid.
    # Select the first one
    device = devs[0].lower()
    print("autoDetect selected the device", device, "for the measurement.")
    return device


def devices(daq: zi.ziDAQServer) -> t.List[str]:
    """List of device_id of all devices connected to the Data Server.

    Return a list of strings containing the device IDs that are attached to the
    Data Server connected via daq, an instance of the core.ziDAQServer
    class. Returns an empty list if no devices are found.

    Args:
      daq: An instance of the core.ziDAQServer class (representing an API
        session connected to a Data Server).

    Returns:
      A list of strings of connected device IDs. The list is empty if no devices
      are detected.

    Raises:
      RuntimeError: If daq is not an instance of core.ziDAQServer.

    Example:
      >>> import zhinst.utils
      >>> daq = zhinst.utils.autoConnect()  # autoConnect not supported for MFLI devices
      >>> device = zhinst.utils.autoDetect(daq)

    """
    if not isinstance(daq, zi.ziDAQServer):
        raise RuntimeError("First argument must be an instance of core.ziDAQServer")
    nodes = daq.listNodes("/", 0)
    devs = [node for node in nodes if re.match("dev*", node, re.IGNORECASE)]
    return list(x.lower() for x in list(devs))


def autoConnect(default_port: int = None, api_level: int = None) -> zi.ziDAQServer:
    """Try to connect to a Zurich Instruments Data Server (UHF,HF2 only).

    Important: autoConnect() does not support MFLI devices.

    Args:
      default_port: The default port to use when connecting to
        the Data Server (specify 8005 for the HF2 Data Server and 8004 for the
        UHF Data Server)
        If default_port is not specified (=None) then first try to connect to a
        HF2, if no server devices are found then try to connect to an UHF.
        This behaviour is useful for the API examples. If we cannot connect to
        a server and/or detect a connected device raise a RuntimeError.
        (default=None).
      api_level: The API level to use, either 1, 4 or 5. HF2 only supports
        Level 1, Level 5 is recommended for UHF and MFLI devices (default=None).

    Returns:
      ziDAQServer: An instance of the core.ziDAQServer class that is used
        for communication to the Data Server.

    Raises:
      RuntimeError: If no running Data Server is found or no device is found
        that is attached to a Data Server.x
    """
    if default_port is None:
        default_port = 8005
        secondary_port = 8004
    elif default_port in [8004, 8005]:
        # If a port is specified, then don't try to connect to a secondary port
        secondary_port = None
    else:
        raise RuntimeError(
            f"autoConnect(): input argument default_port ({default_port}) must be "
            "either 8004 or 8005."
        )
    if api_level is None:
        # Note: level 1 used by default for both UHF and HF2, otherwise
        # backwards compatibility not maintained.
        api_level = 1

    port_device = {8005: "HF2", 8004: "UHFLI or MFLI"}
    port_valid_api_levels = {8005: [1], 8004: [1, 4, 5, 6]}
    port_exception = {}
    try:
        assert api_level in port_valid_api_levels[default_port], (
            "Invalid API level (`{}`) specified for port {} ({} devices), valid "
            "API Levels: {}."
        ).format(
            api_level,
            default_port,
            port_device[default_port],
            port_valid_api_levels[default_port],
        )
        daq = zi.ziDAQServer("localhost", default_port, api_level)
        devs = devices(daq)
        assert devs, (
            "Successfully connected to the server on port `{}`, API level `{}` but "
            "devices() returned an empty list: No devices are connected to this PC."
        ).format(default_port, api_level)
        # We have a server running and a device, we're done
        print(
            "autoConnect connected to a server on port",
            default_port,
            "using API level",
            api_level,
            ".",
        )
        return daq
    except (RuntimeError, AssertionError) as e:
        port_exception[default_port] = e

    error_msg_no_dev = str(
        "Please ensure that the correct Zurich Instruments server is running for your "
        "device and that your device is connected to the server (try connecting first "
        "via the User Interface)."
    )

    # If default_port is specified as an input argument, then secondary_port is
    # None. If we got here we had no success on default_port: raise an error.
    if secondary_port is None:
        error_msg = (
            "autoConnect(): failed to connect to a running server or failed to find a "
            "device connected to the server on port {} (used for {} devices). {} The "
            "exception was: {}"
        ).format(
            default_port,
            port_device[default_port],
            error_msg_no_dev,
            port_exception[default_port],
        )
        raise RuntimeError(error_msg)

    try:
        assert api_level in port_valid_api_levels[secondary_port], (
            "Invalid API level specified for port {} ({} devices), valid API "
            "Levels: {}."
        ).format(
            secondary_port,
            port_device[secondary_port],
            port_valid_api_levels[secondary_port],
        )
        daq = zi.ziDAQServer("localhost", secondary_port, api_level)
        devs = devices(daq)
        assert devs, (
            "Successfully connected to the server on port `{}`, API level `{}` but "
            "devices() returned an empty list: No devices are connected to this PC."
        ).format(secondary_port, api_level)
        # We have a server running and a device, we're done
        print(
            "autoConnect connected to a server on port",
            default_port,
            "using API level",
            api_level,
            ".",
        )
        return daq
    except (RuntimeError, AssertionError) as e:
        port_exception[secondary_port] = e

    # If we got here we failed to connect to a device. Raise a RuntimeError.
    error_msg = (
        "autoConnect(): failed to connect to a running server or failed to find a "
        "device connected to the server. {} The exception on port {} (used for {} "
        "devices) was: {} The exception on port {} (used for {} devices) was: {}"
    ).format(
        error_msg_no_dev,
        default_port,
        port_device[default_port],
        port_exception[default_port],
        secondary_port,
        port_device[secondary_port],
        port_exception[secondary_port],
    )
    raise RuntimeError(error_msg)


def sigin_autorange(daq: zi.ziDAQServer, device: str, in_channel: int) -> float:
    """Perform an automatic adjustment of the signal input range.

    Based on the measured input signal. This utility function starts the
    functionality implemented in the device's firmware and waits until it has
    completed. The range is set by the firmware based on the measured input
    signal's amplitude measured over approximately 100 ms.

    Requirements:
      A devtype that supports autorange functionality on the firmware level,
      e.g., UHFLI, MFLI, MFIA.

    Args:
      daq: A core API session.
      device: The device ID on which to perform the signal input autorange.
      in_channel: The index of the signal input channel to autorange.

    Returns:
      Signal input range.

    Raises:
      AssertionError: If the functionality is not supported by the device or an
        invalid in_channel was specified.
      RuntimeError: If autorange functionality does not complete within the
        timeout.

    Example:
      >>> import zhinst.utils
      >>> device_serial = 'dev2006'
      >>> (daq, _, _) = zhinst.utils.create_api_session(device_serial, 5)
      >>> input_channel = 0
      >>> zhinst.utils.sigin_autorange(daq, device_serial, input_channel)
    """
    autorange_path = "/{}/sigins/{}/autorange".format(device, in_channel)
    assert any(
        re.match(autorange_path, node, re.IGNORECASE)
        for node in daq.listNodes(autorange_path, 7)
    ), (
        "The signal input autorange node `{}` was not returned by listNodes(). Please "
        "check that: The device supports autorange functionality (HF2 does not), the "
        "device `{}` is connected to the Data Server and that the specified input "
        "channel `{}` is correct."
    ).format(
        autorange_path, device, in_channel
    )
    daq.setInt(autorange_path, 1)
    daq.sync()  # Ensure the value has taken effect on device before continuing
    # The node /device/sigins/in_channel/autorange has the value of 1 until an
    # appropriate range has been configured by the device, wait until the
    # autorange routing on the device has finished.
    t0 = time.time()
    timeout = 30
    while daq.getInt(autorange_path):
        time.sleep(0.010)
        if time.time() - t0 > timeout:
            raise RuntimeError(
                "Signal input autorange failed to complete after after %.f seconds."
                % timeout
            )
    return daq.getDouble("/{}/sigins/{}/range".format(device, in_channel))


def get_default_settings_path(daq: zi.ziDAQServer) -> str:
    """Return the default path used for settings by the ziDeviceSettings module.

    Args:
      daq: A core API session.

    Returns:
      settings_path: The default ziDeviceSettings path.
    """
    device_settings = daq.deviceSettings()
    settings_path = device_settings.get("path")["path"][0]
    device_settings.clear()
    return settings_path


def load_settings(daq: zi.ziDAQServer, device: str, filename: str) -> None:
    """Load a LabOne settings file to the specified device.

    This function is synchronous; it will block until loading the settings has
    finished.

    Args:
      daq: A core API session.
      device: The device ID specifying where to load the settings,
      e.g., 'dev123'.
      filename: The filename of the xml settings file to load. The filename can
      include a relative or full path.

    Raises:
      RuntimeError: If loading the settings times out.

    Examples:
      >>> import zhinst.utils as utils
      >>> daq = utils.autoConnect()
      >>> dev = utils.autoDetect(daq)
      >>> # Then, e.g., load settings from a file in the current directory:
      >>> utils.load_settings(daq, dev, 'my_settings.xml')
      >>> # Then, e.g., load settings from the default LabOne settings path:
      >>> filename = 'default_ui.xml'
      >>> path = utils.get_default_settings_path(daq)
      >>> utils.load_settings(daq, dev, path + os.sep + filename)
    """
    path, filename = os.path.split(filename)
    filename_noext = os.path.splitext(filename)[0]
    device_settings = daq.deviceSettings()
    device_settings.set("device", device)
    device_settings.set("filename", filename_noext)
    if path:
        device_settings.set("path", path)
    else:
        device_settings.set("path", "." + os.sep)
    device_settings.set("command", "load")
    try:
        device_settings.execute()
        t0 = time.time()
        timeout = 60
        while not device_settings.finished():
            time.sleep(0.05)
            if time.time() - t0 > timeout:
                raise RuntimeError(
                    "Unable to load device settings after %.f seconds." % timeout
                )
    finally:
        device_settings.clear()


def save_settings(daq: zi.ziDAQServer, device: str, filename: str) -> None:
    """Save settings from the specified device to a LabOne settings file.

    This function is synchronous; it will block until saving the settings has
    finished.

    Args:
      daq: A core API session.
      device: The device ID specifying where to load the settings,
      e.g., 'dev123'.
      filename: The filename of the LabOne xml settings file. The filename
      can include a relative or full path.

    Raises:
      RuntimeError: If saving the settings times out.

    Examples:
      import zhinst.utils as utils
      daq = utils.autoConnect()
      dev = utils.autoDetect(daq)

      # Then, e.g., save settings to a file in the current directory:
      utils.save_settings(daq, dev, 'my_settings.xml')

      # Then, e.g., save settings to the default LabOne settings path:
      filename = 'my_settings_example.xml'
      path = utils.get_default_settings_path(daq)
      utils.save_settings(daq, dev, path + os.sep + filename)
    """
    path, filename = os.path.split(filename)
    filename_noext = os.path.splitext(filename)[0]
    device_settings = daq.deviceSettings()
    device_settings.set("device", device)
    device_settings.set("filename", filename_noext)
    if path:
        device_settings.set("path", path)
    else:
        device_settings.set("path", "." + os.sep)
    device_settings.set("command", "save")
    try:
        device_settings.execute()
        t0 = time.time()
        timeout = 60
        while not device_settings.finished():
            time.sleep(0.05)
            if time.time() - t0 > timeout:
                raise RuntimeError(
                    "Unable to save device settings after %.f seconds." % timeout
                )
    finally:
        device_settings.clear()


# The names correspond to the data in the columns of a CSV file saved by the
# LabOne User Interface. These are the names of demodulator sample fields.
LABONE_DEMOD_NAMES = (
    "chunk",
    "timestamp",
    "x",
    "y",
    "freq",
    "phase",
    "dio",
    "trigger",
    "auxin0",
    "auxin1",
)
LABONE_DEMOD_FORMATS = ("u8", "u8", "f8", "f8", "f8", "f8", "u4", "u4", "f8", "f8")
# The dtype to provide when creating a numpy array from LabOne demodulator data
LABONE_DEMOD_DTYPE = list(zip(LABONE_DEMOD_NAMES, LABONE_DEMOD_FORMATS))

# The names correspond to the data in the columns of a CSV file saved by the
# ziControl User Interface. These are the names of demodulator sample fields.
ZICONTROL_NAMES = ("t", "x", "y", "freq", "dio", "auxin0", "auxin1")
ZICONTROL_FORMATS = ("f8", "f8", "f8", "f8", "u4", "f8", "f8")
# The dtype to provide when creating a numpy array from ziControl-saved demodulator data
ZICONTROL_DTYPE = list(zip(ZICONTROL_NAMES, ZICONTROL_FORMATS))


def load_labone_demod_csv(
    fname: t.Union[str, Path], column_names: t.List[str] = LABONE_DEMOD_NAMES
) -> np.ndarray:
    """Load a CSV file containing demodulator samples.

    Load a CSV file containing demodulator samples as saved by the LabOne User
    Interface into a numpy structured array.

    Args:
      fname: The file or filename of the CSV file to load.
      column_names (list or tuple of str, optional): A list (or tuple) of column
      names to load from the CSV file. Default is to load all columns.

    Returns:
      sample: A numpy structured array of shape (num_points,)
      whose field names correspond to the column names in the first line of the
      CSV file. num_points is the number of lines in the CSV file - 1.

    Example:
      >>> import zhinst.utils
      >>> sample = zhinst.utils.load_labone_demod_csv(
      >>>   'dev2004_demods_0_sample_00000.csv',
      >>>   ('timestamp', 'x', 'y'))
      >>> import matplotlib.pyplot as plt
      >>> import numpy as np
      >>> plt.plot(sample['timestamp'], np.abs(sample['x'] + 1j*sample['y']))
    """
    assert set(column_names).issubset(
        LABONE_DEMOD_NAMES
    ), "Invalid name in ``column_names``, valid names are: %s" % str(LABONE_DEMOD_NAMES)
    cols = [
        col for col, dtype in enumerate(LABONE_DEMOD_DTYPE) if dtype[0] in column_names
    ]
    dtype = [dt for dt in LABONE_DEMOD_DTYPE if dt[0] in column_names]
    sample = np.genfromtxt(
        fname, delimiter=";", dtype=dtype, usecols=cols, skip_header=1
    )
    return sample


def load_labone_csv(fname: str) -> np.ndarray:
    """Load a csv file generated from LabOne.

    Load a CSV file containing generic data as saved by the LabOne User
    Interface into a numpy structured array.

    Args:
      filename: The filename of the CSV file to load.

    Returns:
      A numpy structured array of shape (num_points,) whose field names
      correspond to the column names in the first line of the CSV file.
      num_points is the number of lines in the CSV file - 1.

    Example:
      >>> import zhinst.utils
      >>> # Load the CSV file of PID error data (node: /dev2004/pids/0/error)
      >>> data = zhinst.utils.load_labone_csv('dev2004_pids_0_error_00000.csv')
      >>> import matplotlib.pyplot as plt
      >>> # Plot the error
      >>> plt.plot(data['timestamp'], data['value'])
    """
    data = np.genfromtxt(fname, delimiter=";", dtype=None, names=True)
    return data


def load_labone_mat(filename: str) -> t.Dict:
    """Load a mat file generated from LabOne.

    A wrapper function for loading a MAT file as saved by the LabOne User
    Interface with scipy.io's loadmat() function. This function is included
    mainly to document how to work with the data structure return by
    scipy.io.loadmat().

    Args:
      filename: the name of the MAT file to load.

    Returns:
      A nested dictionary containing the instrument data as
      specified in the LabOne User Interface. The nested structure of ``data``
      corresponds to the path of the data's node in the instrument's node
      hierarchy.

    Further comments:
      The MAT file saved by the LabOne User Interface (UI) is a Matlab V5.0 data
      file. The LabOne UI saves the specified data using native Matlab data
      structures in the same format as are returned by commands in the LabOne
      Matlab API. More specifically, these data structures are nested Matlab
      structs, the nested structure of which correspond to the location of the
      data in the instrument's node hierarchy.

      Matlab structs are returned by scipy.io.loadmat() as dictionaries, the
      name of the struct becomes a key in the dictionary. However, as for all
      objects in MATLAB, structs are in fact arrays of structs, where a single
      struct is an array of shape (1, 1). This means that each (nested)
      dictionary that is returned (corresponding to a node in node hierarchy) is
      loaded by scipy.io.loadmat as a 1-by-1 array and must be indexed as
      such. See the ``Example`` section below.

      For more information please refer to the following link:
      http://docs.scipy.org/doc/scipy/reference/tutorial/io.html#matlab-structs

    Example:
      >>> device = 'dev88'
      >>> # See ``Further explanation`` above for a comment on the indexing:
      >>> timestamp = data[device][0,0]['demods'][0,0]['sample'][0,0]['timestamp'][0]
      >>> x = data[device][0,0]['demods'][0,0]['sample'][0,0]['x'][0]
      >>> y = data[device][0,0]['demods'][0,0]['sample'][0,0]['y'][0]
      >>> import matplotlib.pyplot as plt
      >>> import numpy as np
      >>> plt.plot(timestamp, np.abs(x + 1j*y))
      >>> # If multiple demodulator's are saved, data from the second demodulator,
      >>> # e.g., is accessed as following:
      >>> x = data[device][0,0]['demods'][0,1]['sample'][0,0]['x'][0]
    """
    try:
        data = scipy.io.loadmat(filename)
        return data
    except (NameError, AttributeError):
        print(
            "\n\n *** Please install the ``scipy`` package and verify you can use "
            "scipy.io.loadmat() in order to use zhinst.utils.load_labone_mat. *** \n\n"
        )
        print(
            "Whilst calling import scipy.io an exception was raised with the message: ",
            str(__SCIPY_IMPORT_ERROR),
        )
        print("Whilst calling scipy.io.loadmat() the following exception was raised:")
        raise
    except Exception as e:
        print("Unexpected exception", str(e))
        raise


def load_zicontrol_csv(
    filename: str, column_names: t.List[str] = ZICONTROL_NAMES
) -> np.ndarray:
    """Load a CSV file containing demodulator samples.

    Load a CSV file containing demodulator samples as saved by the ziControl
    User Interface into a numpy structured array.

    Args:
      filename: The file or filename of the CSV file to load.
      column_names: A list (or tuple) of column names (demodulator sample
        field names) to load from the CSV file. Default is to load all columns.

    Returns:
      sample: A numpy structured array of shape (num_points,)
      whose field names correspond to the field names of a ziControl demodulator
      sample. num_points is the number of lines in the CSV file - 1.

    Example:
      >>> import zhinst.utils
      >>> import matplotlib.plt as plt
      >>> import numpy as np
      >>> sample = zhinst.utils.load_labone_csv('Freq1.csv', ('t', 'x', 'y'))
      >>> plt.plot(sample['t'], np.abs(sample['x'] + 1j*sample['y']))
    """
    assert set(column_names).issubset(
        ZICONTROL_NAMES
    ), "Invalid name in ``column_names``, valid names are: %s" % str(ZICONTROL_NAMES)
    cols = [
        col for col, dtype in enumerate(ZICONTROL_DTYPE) if dtype[0] in column_names
    ]
    dtype = [dt for dt in ZICONTROL_DTYPE if dt[0] in column_names]
    sample = np.genfromtxt(filename, delimiter=",", dtype=dtype, usecols=cols)
    return sample


def load_zicontrol_zibin(
    filename: str, column_names: t.List[str] = ZICONTROL_NAMES
) -> np.ndarray:
    """Load a ziBin file containing demodulator samples.

    Load a ziBin file containing demodulator samples as saved by the ziControl
    User Interface into a numpy structured array. This is for data saved by
    ziControl in binary format.

    Note:
        Specifying a fewer names in ``column_names`` will not result in a
        speed-up as all data is loaded from the binary file by default.

    Args:
        filename: The filename of the .ziBin file to load.
        column_names: A list (or tuple) of column names to load from the CSV
            file. Default is to load all columns.

    Returns:
        A numpy structured array of shape (num_points,) whose field names
        correspond to the field names of a ziControl demodulator sample.
        num_points is the number of sample points saved in the file.

    Example:
        >>> import zhinst.utils
        >>> sample = zhinst.utils.load_zicontrol_zibin('Freq1.ziBin')
        >>> import matplotlib.plt as plt
        >>> import numpy as np
        >>> plt.plot(sample['t'], np.abs(sample['x'] + 1j*sample['y']))
    """
    assert set(column_names).issubset(
        ZICONTROL_NAMES
    ), "Invalid name in ``column_names``, valid names are: %s." % str(ZICONTROL_NAMES)
    sample = np.fromfile(filename, dtype=">f8")
    rem = np.size(sample) % len(ZICONTROL_NAMES)
    assert rem == 0, str(
        "Incorrect number of data points in ziBin file, the number of data points "
        "must be divisible by the number of demodulator fields."
    )
    n = np.size(sample) / len(ZICONTROL_NAMES)
    sample = np.reshape(sample, (n, len(ZICONTROL_NAMES))).transpose()
    cols = [
        col for col, dtype in enumerate(ZICONTROL_DTYPE) if dtype[0] in column_names
    ]
    dtype = [dt for dt in ZICONTROL_DTYPE if dt[0] in column_names]
    sample = np.core.records.fromarrays(sample[cols, :], dtype=dtype)
    return sample


def check_for_sampleloss(timestamps: np.ndarray) -> np.ndarray:
    """Check for sample loss.

    Check whether timestamps are equidistantly spaced, it not, it is an
    indication that sampleloss has occurred whilst recording the demodulator
    data.

    This function assumes that the timestamps originate from continuously saved
    demodulator data, during which the demodulator sampling rate was not
    changed.

    Args:
      timestamp: a 1-dimensional array containing demodulator timestamps

    Returns:
      A 1-dimensional array indicating the indices in timestamp where
      sampleloss has occurred. An empty array is returned in no sampleloss was
      present.
    """
    # If the second difference of the timestamps is zero, no sampleloss has occurred
    index = np.where(np.diff(timestamps, n=2) > 0.1)[0] + 1
    # Find the true dtimestamps (determined by the configured sampling rate)
    dtimestamp = np.nan
    for i in range(0, np.shape(timestamps)[0]):
        # Take the sampling rate from a point where sample loss has not
        # occurred.
        if i not in index:
            dtimestamp = timestamps[i + 1] - timestamps[i]
            break
    assert not np.isnan(dtimestamp)
    for i in index:
        warnings.warn(
            "Sample loss detected at timestamps={} (index: {}, {} points).".format(
                timestamps[i], i, (timestamps[i + 1] - timestamps[i]) / dtimestamp
            )
        )
    return index


def bwtc_scaling_factor(order: int) -> float:
    """Return the appropriate scaling factor for bandwidth to timeconstant.

    Converstion for the provided demodulator order.

    Args:
        order: demodulator order.

    Returns:
        Scaling factor for the bandwidth to timeconstant.
    """
    if order == 1:
        return 1.0
    if order == 2:
        return 0.643594
    if order == 3:
        return 0.509825
    if order == 4:
        return 0.434979
    if order == 5:
        return 0.385614
    if order == 6:
        return 0.349946
    if order == 7:
        return 0.322629
    if order == 8:
        return 0.300845
    raise RuntimeError("Error: Order (%d) must be between 1 and 8.\n" % order)


def bw2tc(bandwidth: float, order: int) -> float:
    """Convert the demodulator 3 dB bandwidth to its equivalent timeconstant.

    Args:
      bandwidth: The demodulator 3dB bandwidth to convert.
      order: The demodulator order (1 to 8) for which to convert the bandwidth.

    Returns:
      The equivalent demodulator timeconstant.
    """
    return bwtc_scaling_factor(order) / (2 * np.pi * bandwidth)


def tc2bw(timeconstant: float, order: int) -> float:
    """Convert the demodulator timeconstant to its equivalent 3 dB bandwidth.

    Args:
      timeconstant: The equivalent demodulator timeconstant.
      order: The demodulator order (1 to 8) for which to convert the
      bandwidth.

    Returns:
      The demodulator 3dB bandwidth to convert.
    """
    return bwtc_scaling_factor(order) / (2 * np.pi * timeconstant)


def systemtime_to_datetime(systemtime: int) -> datetime.datetime:
    """Convert the LabOne "systemtime" into a datetime object.

    Convert the LabOne "systemtime" returned in LabOne data headers from
    microseconds since Unix epoch to a datetime object with microsecond
    precision.

    Args:
        systemtime: Labone "systemtime" returned by LabOne.

    Returns:
        datetime object.
    """
    systemtime_sec, systemtime_microsec = divmod(systemtime, 1e6)
    # Create a datetime object from epoch timestamp with 0 microseconds.
    time_formated = datetime.datetime.fromtimestamp(systemtime_sec)
    # Set the number of microseconds in the datetime object.
    return time_formated.replace(microsecond=int(systemtime_microsec))


def disable_everything(daq: zi.ziDAQServer, device: str) -> t.List[t.Tuple[str, int]]:
    """Put the device in a known base configuration.

    disable all extended functionality; disable all streaming nodes.

    Args:
        daq: An instance of the core.ziDAQServer class
            (representing an API session connected to a Data Server).
        device: The device ID specifying where to load the settings,
            e.g., 'dev123'.

    Returns:
      A list of lists as provided to ziDAQServer's set()
      command. Each sub-list forms a nodepath, value pair. This is a list of
      nodes configured by the function and may be reused.

    Warning:
        This function is intended as a helper function for the API's
        examples and it's signature or implementation may change in future releases.
    """
    node_branches = daq.listNodes("/{}/".format(device), 0)
    settings = []
    if node_branches == []:
        print("Device", device, "is not connected to the data server.")
        return settings

    if "aucarts" in (node.lower() for node in node_branches):
        settings.append(["/{}/aucarts/*/enable".format(device), 0])
    if "aupolars" in (node.lower() for node in node_branches):
        settings.append(["/{}/aupolars/*/enable".format(device), 0])
    if "awgs" in (node.lower() for node in node_branches):
        settings.append(["/{}/awgs/*/enable".format(device), 0])
    if "boxcars" in (node.lower() for node in node_branches):
        settings.append(["/{}/boxcars/*/enable".format(device), 0])
    if "cnts" in (node.lower() for node in node_branches):
        settings.append(["/{}/cnts/*/enable".format(device), 0])
    # CURRINS
    if daq.listNodes("/{}/currins/0/float".format(device), 0) != []:
        settings.append(["/{}/currins/*/float".format(device), 0])
    if "dios" in (node.lower() for node in node_branches):
        settings.append(["/{}/dios/*/drive".format(device), 0])
    if "demods" in (node.lower() for node in node_branches):
        settings.append(["/{}/demods/*/enable".format(device), 0])
        settings.append(["/{}/demods/*/trigger".format(device), 0])
        settings.append(["/{}/demods/*/sinc".format(device), 0])
        settings.append(["/{}/demods/*/oscselect".format(device), 0])
        settings.append(["/{}/demods/*/harmonic".format(device), 1])
        settings.append(["/{}/demods/*/phaseshift".format(device), 0])
    if "extrefs" in (node.lower() for node in node_branches):
        settings.append(["/{}/extrefs/*/enable".format(device), 0])
    if "imps" in (node.lower() for node in node_branches):
        settings.append(["/{}/imps/*/enable".format(device), 0])
    if "inputpwas" in (node.lower() for node in node_branches):
        settings.append(["/{}/inputpwas/*/enable".format(device), 0])
    if daq.listNodes("/{}/mods/0/enable".format(device), 0) != []:
        # HF2 without the MOD Option has an empty MODS branch.
        settings.append(["/{}/mods/*/enable".format(device), 0])
    if "outputpwas" in (node.lower() for node in node_branches):
        settings.append(["/{}/outputpwas/*/enable".format(device), 0])
    if daq.listNodes("/{}/pids/0/enable".format(device), 0) != []:
        # HF2 without the PID Option has an empty PID branch.
        settings.append(["/{}/pids/*/enable".format(device), 0])
    if daq.listNodes("/{}/plls/0/enable".format(device), 0) != []:
        # HF2 without the PLL Option still has the PLLS branch.
        settings.append(["/{}/plls/*/enable".format(device), 0])
    if "sigins" in (node.lower() for node in node_branches):
        settings.append(["/{}/sigins/*/ac".format(device), 0])
        settings.append(["/{}/sigins/*/imp50".format(device), 0])
        sigins_children = daq.listNodes("/{}/sigins/0/".format(device), 0)
        for leaf in ["diff", "float"]:
            if leaf in (node.lower() for node in sigins_children):
                settings.append(["/{}/sigins/*/{}".format(device, leaf.lower()), 0])
    if "sigouts" in (node.lower() for node in node_branches):
        settings.append(["/{}/sigouts/*/on".format(device), 0])
        settings.append(["/{}/sigouts/*/enables/*".format(device), 0])
        settings.append(["/{}/sigouts/*/offset".format(device), 0.0])
        sigouts_children = daq.listNodes("/{}/sigouts/0/".format(device), 0)
        for leaf in ["add", "diff", "imp50"]:
            if leaf in (node.lower() for node in sigouts_children):
                settings.append(["/{}/sigouts/*/{}".format(device, leaf.lower()), 0])
        if "precompensation" in (node.lower() for node in sigouts_children):
            settings.append(["/{}/sigouts/*/precompensation/enable".format(device), 0])
            settings.append(
                ["/{}/sigouts/*/precompensation/highpass/*/enable".format(device), 0]
            )
            settings.append(
                [
                    "/{}/sigouts/*/precompensation/exponentials/*/enable".format(
                        device
                    ),
                    0,
                ]
            )
            settings.append(
                ["/{}/sigouts/*/precompensation/bounces/*/enable".format(device), 0]
            )
            settings.append(
                ["/{}/sigouts/*/precompensation/fir/enable".format(device), 0]
            )
    if "scopes" in (node.lower() for node in node_branches):
        settings.append(["/{}/scopes/*/enable".format(device), 0])
        if daq.listNodes("/{}/scopes/0/segments/enable".format(device), 0) != []:
            settings.append(["/{}/scopes/*/segments/enable".format(device), 0])
        if daq.listNodes("/{}/scopes/0/stream/enables/0".format(device), 0) != []:
            settings.append(["/{}/scopes/*/stream/enables/*".format(device), 0])
    if "triggers" in (node.lower() for node in node_branches):
        settings.append(["/{}/triggers/out/*/drive".format(device), 0])
    daq.set(settings)
    daq.sync()
    return settings


def convert_awg_waveform(
    wave1: np.ndarray, wave2: np.ndarray = None, markers: np.ndarray = None
) -> np.ndarray:
    """Convert one or multiple waveforms into the native AWG waveform format.

    Converts one or multiple arrays with waveform data to the native AWG
    waveform format (interleaved waves and markers as uint16).

    Waveform data can be provided as integer (no conversion) or floating point
    (range -1 to 1) arrays.

    Args:
      wave1: Array with data of waveform 1.
      wave2: Array with data of waveform 2.
      markers: Array with marker data.

    Returns:
      The converted uint16 waveform is returned.
    """
    wave2_uint = None
    marker_uint = None
    mode = 0

    # Prepare waveforms
    def uint16_waveform(wave):
        wave = np.asarray(wave)
        if np.issubdtype(wave.dtype, np.floating):
            return np.asarray((np.power(2, 15) - 1) * wave, dtype=np.uint16)
        return np.asarray(wave, dtype=np.uint16)

    wave1_uint = uint16_waveform(wave1)
    mode += 1

    if wave2 is not None:
        if len(wave2) != len(wave1):
            raise Exception(
                "wave1 and wave2 have different length. They should have the same "
                "length."
            )
        wave2_uint = uint16_waveform(wave2)
        mode += 2

    if markers is not None:
        if len(markers) != len(wave1):
            raise Exception(
                "wave1 and marker have different length. They should have the same "
                "length."
            )
        marker_uint = np.array(markers, dtype=np.uint16)
        mode += 4

    # Merge waveforms
    waveform_data = None
    if mode == 1:
        waveform_data = wave1_uint
    elif mode == 3:
        waveform_data = np.vstack((wave1_uint, wave2_uint)).reshape((-2,), order="F")
    elif mode == 4:
        waveform_data = marker_uint
    elif mode == 5:
        waveform_data = np.vstack((wave1_uint, marker_uint)).reshape((-2,), order="F")
    elif mode == 6:
        waveform_data = np.vstack((wave2_uint, marker_uint)).reshape((-2,), order="F")
    elif mode == 7:
        waveform_data = np.vstack((wave1_uint, wave2_uint, marker_uint)).reshape(
            (-2,), order="F"
        )
    else:
        waveform_data = []

    return waveform_data


def parse_awg_waveform(
    wave_uint: np.ndarray, channels: int = 1, markers_present: bool = False
) -> t.Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Covert a native AWG waveform into the individual waves.

    Converts a received waveform from the AWG waveform node into floating point
    and separates its contents into the respective waves (2 waveform waves and 1
    marker wave), depending on the input.

    Args:
      wave: A uint16 array from the AWG waveform node.
      channels: Number of channels present in the wave.
      markers_present: Indicates if markers are interleaved in the wave.

    Returns:
      Three separated arrays are returned. The waveforms are scaled to be in the
      range [-1 and 1]. If no data is present the respective array is empty.
    """
    from collections import namedtuple

    # convert uint16 to int16
    wave_int = np.array(wave_uint, dtype=np.int16)

    parsed_waves = namedtuple("deinterleaved_waves", ["wave1", "wave2", "markers"])

    wave1 = []
    wave2 = []
    markers = []

    interleaved_frames = channels
    if markers_present:
        interleaved_frames += 1

    deinterleaved = [
        wave_int[idx::interleaved_frames] for idx in range(interleaved_frames)
    ]

    deinterleaved[0] = deinterleaved[0] / (np.power(2, 15) - 1)
    if channels == 2:
        deinterleaved[1] = deinterleaved[1] / (np.power(2, 15) - 1)

    wave1 = deinterleaved[0]
    if channels == 2:
        wave2 = deinterleaved[1]
    if markers_present:
        markers = deinterleaved[-1]

    return parsed_waves(wave1, wave2, markers)


def wait_for_state_change(
    daq: zi.ziDAQServer,
    node: str,
    value: int,
    timeout: float = 1.0,
    sleep_time: float = 0.005,
) -> None:
    """Waits until a node has the expected state/value.

    Attention: Only supports integer values as reference.

    Args:
        daq: A core API session.
        node: Path of the node.
        value: expected value.
        timeout: max in seconds. (default = 1.0)
        sleep_time: sleep interval in seconds. (default = 0.005)

    Raises:
        TimeoutError: If the node did not changed to the expected value within
            the given time.
    """
    start_time = time.time()
    while start_time + timeout >= time.time() and daq.getInt(node) != value:
        time.sleep(sleep_time)
    if daq.getInt(node) != value:
        raise TimeoutError(
            f"{node} did not change to expected value {value} within "
            f"{timeout} seconds."
        )


def assert_node_changes_to_expected_value(
    daq: zi.ziDAQServer,
    node: str,
    expected_value: t.Union[int, float, str],
    sleep_time: float = 0.005,
    max_repetitions: int = 200,
) -> None:
    """Polls a node until it has the the expected value.

    If the node didn't change to the expected value within the maximum number
    of polls an assertion error is issued.

    Args:
      daq: A core API session.
      node: path of the node that should change to expected value
      expected_value: value the node is expected to change to
      sleep_time: time in seconds to wait between requesting th value
      max_repetitions: max. number of loops we wait for the node to change

    Raises:
        AssertionError: If the node doesn't change to the expected value within
            the given time.
    """
    warnings.warn(
        "assert_node_changes_to_expected_value is deprecated please use "
        + "wait_for_state_change instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    daq.sync()

    for _ in range(max_repetitions):
        readback_value = daq.getInt(node)
        if readback_value == expected_value:
            break
        time.sleep(sleep_time)

    assert readback_value == expected_value, (
        "Node '{}' did not return {} (but returned {}) within {} sec."
    ).format(node, expected_value, readback_value, max_repetitions * sleep_time)


def volt_rms_to_dbm(
    volt_rms: t.Union[float, t.List[float]], input_impedance_ohm: int = 50
) -> t.Union[float, t.List[float]]:
    """Converts a Root Mean Square (RMS) voltage into a dBm power value.

    Args:
      volt_rms: The RMS voltage to be converted
      input_impedance_ohm: The input impedance in Ohm

    Returns:
      The power in dBm corrsponding to the volt_rms argument is returned.
    """
    return 10 * np.log10((np.abs(volt_rms) ** 2) * 1e3 / input_impedance_ohm)
