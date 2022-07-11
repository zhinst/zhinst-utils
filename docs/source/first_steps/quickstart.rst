Quickstart
==========

Eager to get started? This page gives a good introduction to zhinst-utils.
Follow :doc:`installation` to install zhinst-utils first.

Preparation
-----------

Before you can spin up zhinst-utils LabOne® needs to installed and running.
For a complete reference see the dedicated `user manual <http://docs.zhinst.com/>`_
page for your instrument(s).

Before you continue make sure a LabOne® data server is running in your network and
all of your devices are visible.

Session To The Data Server
---------------------------

The utils provide a set of helper functions to ease the use of commonly
used functionalities. It can not be used as a standalone package but
rather is an addition to the LabOne python API (``zhinst-core``).

Each function is stateless/static. Meaning it either creates or operates on an 
existing data server session from ``zhinst-core``. 

The follwoing example shows how a call to a device specific utils function
``zhinst.utils.shfqa.max_qubits_per_channel`` could look like for the device ``DEVXXXX``
connected to the dataserver running on ``localhost``.

.. code-block:: python

    >>> from zhinst.ziPython import ziDAQServer
    >>> import zhinst.utils.shfqa as shfqa_utils
    >>> daq = ziDAQServer("localhost", 8004, 6)
    >>> daq.connectDevice("DEVXXXX", "1GbE")
    >>> shfqa_utils.max_qubits_per_channel(daq, "DEVXXXX")
    16

For a complete list of all helper function provided by zhinst-utils take
a look at the :ref:`package/utils:Package Documentation`
