"""Base case of the operational window and the typed GUI fields.

The base case is the well used to validate the method against the reference
spreadsheet: 1000 m of water and a sonic profile from 1250 m to 4500 m.
``OPERATIONAL_WINDOW_FIELD_SPECS`` describes the scalar parameters for
``drilling.gui.param_form.ParamForm``.
"""

from __future__ import annotations

from importlib import resources

import pandas as pd

from drilling.core import FieldSpec

from .calculation import PROFILE_COLUMNS, WellParameters

BASE_CASE_PARAMETERS = WellParameters()
"""Scalar parameters of the base case."""

BASE_CASE_PROFILE_FILE = "base_case_profile.csv"
"""Name of the base-case profile shipped in the package ``data`` folder."""

OPERATIONAL_WINDOW_FIELD_SPECS = [
    FieldSpec("water_depth", "Water depth", "m", step=10.0, decimals=2),
    FieldSpec("seawater_density", "Seawater density", "g/cm³", step=0.01),
    FieldSpec("gardner_a", "Gardner coefficient a", step=0.001),
    FieldSpec("gardner_b", "Gardner exponent b", step=0.01),
    FieldSpec("ppg_conversion", "psi/m to ppg factor", step=0.0001),
    FieldSpec("eaton_exponent", "Eaton exponent", step=0.1),
    FieldSpec("trend_base_depth", "Normal trend base depth", "m", step=10.0, decimals=2),
    FieldSpec("safety_margin", "Safety margin", "fraction", step=0.01, maximum=0.4999),
]
"""Scalar parameters shown in the Operational Window tab, keyed like ``WellParameters``."""

PROFILE_HEADERS = {
    "depth_m": "Depth (m)",
    "transit_time_us_ft": "Transit time (µs/ft)",
    "max_horizontal_stress_psi": "σH max (psi)",
    "min_horizontal_stress_psi": "σh min (psi)",
    "poisson_ratio": "Poisson's ratio",
    "cohesion_psi": "Cohesion (psi)",
    "friction_angle_deg": "Friction angle (deg)",
}
"""Table header of each profile column, in ``PROFILE_COLUMNS`` order."""


def load_base_case_profile() -> pd.DataFrame:
    """Read the base-case profile shipped with the package.

    Returns
    -------
    pandas.DataFrame
        One row per depth below the seabed, with the columns in
        ``PROFILE_COLUMNS``.
    """
    source = resources.files(__package__).joinpath("data", BASE_CASE_PROFILE_FILE)
    with source.open(encoding="utf-8") as handle:
        return pd.read_csv(handle)[PROFILE_COLUMNS].astype(float)
