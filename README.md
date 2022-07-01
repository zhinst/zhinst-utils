[![PyPI version](https://badge.fury.io/py/zhinst-utils.svg)](https://badge.fury.io/py/zhinst-utils)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Twitter URL](https://img.shields.io/twitter/url/https/twitter.com/fold_left.svg?style=social&label=Follow%20%40zhinst)](https://twitter.com/zhinst)

# Utils for Zurich Instruments LabOne API

zhinst-utils provides a set of helper functions for the native LabOne Python API
called [zhinst.core](https://pypi.org/project/zhinst/core).

It offers higher level functions to ease the communication with
[Zurich Instruments](https://zhinst.com) devices. It is not intended to be a
separate layer above ``zhinst.core`` but rather as an addition.

Apart for a set of not device specific functions the utility also provide
specific functionality for some devices. Currently including:
* SHFQA
* SHFSG
* SHFQC

To see the device utils in action check out the
[LabOne API examples](https://github.com/zhinst/labone-api-examples).

## Installation
Python 3.6+ is required.
```
pip install zhinst-utils
```

## Usage
```
import zhinst.utils.shfqa
import zhinst.utils.shfsg
import zhinst.utils.shfqc

help(zhinst.utils.shfqa)
help(zhinst.utils.shfsg)
help(zhinst.utils.shfqc)
```

## About

More information about programming with Zurich Instruments devices is available in the
[package documentation](https://docs.zhinst.com/zhinst-utils/en/latest/)
and the
[LabOne Programming Manual](https://docs.zhinst.com/labone_programming_manual/overview.html).
