Installation
=============

Python version
--------------

We recommend using the latest version of Python. zhinst-utils supports Python
3.7 and newer.

Dependencies
------------

These distributions will be installed automatically when installing zhinst-toolkit.

* `numpy <https://pypi.org/project/numpy/>`_ adds support for large, multi-dimensional
  arrays and matrices, along with a large collection of high-level mathematical
  functions to operate on these arrays.
* `zhinst-core <https://pypi.org/project/zhinst-core/>`_ is the low level python api for Zurich
  Instruments devices.

Install zhinst-utils
---------------------------

Use the following command to install zhinst-utils:

.. code-block:: sh

    $ pip install zhinst-utils

Or use the the generic `zhinst` package that includes everything you need to 
work with the Zurich Instrument devices (including the utils).

.. code-block:: sh

    $ pip install zhinst

Check out the :ref:`first_steps/quickstart:Quickstart` or
go back to the :doc:`Documentation Overview <index>`.
