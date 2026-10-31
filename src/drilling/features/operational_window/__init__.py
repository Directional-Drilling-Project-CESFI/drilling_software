"""Operational drilling window from a sonic log.

Overburden (Gardner), pore pressure (Eaton), collapse gradient
(Mohr-Coulomb) and fracture gradient (Poisson), narrowed by a safety margin.
Depths are positive downwards, measured from sea level; the profile starts
below the seabed.

Public API
----------
``calculate_operational_window`` takes a ``WellParameters`` and a profile
``DataFrame`` (columns in ``PROFILE_COLUMNS``) and returns the results table.
``BASE_CASE_PARAMETERS`` and ``load_base_case_profile`` give the base case.
"""

from .calculation import (
    PROFILE_COLUMNS,
    OperationalWindow,
    WellParameters,
    calculate_operational_window,
    validate_inputs,
)
from .defaults import BASE_CASE_PARAMETERS, load_base_case_profile

__all__ = [
    "BASE_CASE_PARAMETERS",
    "PROFILE_COLUMNS",
    "OperationalWindow",
    "WellParameters",
    "calculate_operational_window",
    "load_base_case_profile",
    "validate_inputs",
]
