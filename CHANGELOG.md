# Changelog

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
