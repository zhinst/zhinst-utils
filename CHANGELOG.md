# Changelog

## Version 0.3.5

* Adapt feedback latency model for LabOne 23.10
  * Modify default values of `QCCSSystemDescription`

## Version 0.3.3

* Adapt feedback latency model for LabOne 23.06
  * Add `rtlogger_correction` to `QCCSSystemDescription`
  * Modify default values of `QCCSSystemDescription`

## Version 0.3.2

* Increase default timeout for get_scope_data
* Avoid duplicate fetching of results in shf_sweeper.

## Version 0.3.1

* Add internal trigger to SHFQA sweeper class.

## Version 0.3

* Feedback model now supports SHFQC internal feedback.
* Added a function to get status flags of devices. New module `zhinst.utils.device_status` includes `DeviceStatusFlag` Enum and `get_device_statuses()`.
* Added a function `zhinst.utils.api_compatiblity.check_dataserver_device_compatibility()` to check LabOne DataServer and devices firmware compatibility.
The function raises `zhinst.utils.exceptions.CompatibilityError` if incompatibilities are found.


## Version 0.2
* ShfSweeper: New Setting for PSD
* Shfqa: Fix writing of weights vectors if index zero is absent.
* Adapt feedback latency model for LabOne 23.02.

## Version 0.1.5
* ShfSweeper: Fixed a bug where delay settings would be wrongly rejected as "Delay ... ns not in multiples of 2 ns" due to numerical precision.
* ShfSweeper: Changed the default value of the integration delay to 224 ns to better match the digital and analog delay when directly looping back the analog output to the analog input.

## Version 0.1.4
* ShfSweeper: Fixed a bug where the step size for the sweep was calculated with the wrong division factor, resulting in a too small step size and the sweep stopping one step short of the stop frequency.

## Version 0.1.3
* Docs: Updated documentation to display `zhinst.core` instead of `zhinst.ziPython`
* Increased `DeprecationWarning` stack level when importing `zhinst.deviceutils`
* ShfSweeper: Add configurable wait time after integration

## Version 0.1.2
* SHFQA: in the multistate.get_qudits_results() function,
  work around a firmware issue present in the LabOne release 22.08

## Version 0.1.1
* SHFQA: add utils for multi-state discrimination

## Version 0.1
* initial release
* utils from old zhinst package copied
* deviceutils from old zhinst-deviceutils package copied for
  * SHFQA
  * SHFSG
  * SHFQC
