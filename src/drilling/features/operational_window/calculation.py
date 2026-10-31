"""Operational drilling window computed from a sonic log.

Steps
-----
1. Density (Gardner) -> overburden stress and gradient.
2. Normal compaction trend (logarithmic fit of the sonic log).
3. Pore pressure (Eaton).
4. Collapse gradient (Mohr-Coulomb).
5. Fracture gradient (Poisson).
6. Operational window, narrowed by a safety margin.

Units: depth in m, transit time in µs/ft, stresses in psi, densities in
g/cm³ and gradients in ppg (lb/gal).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

PSI_PER_KGF_CM2 = 1.422
"""Pressure conversion: 1 kgf/cm² = 1.422 psi."""

DEPTH = "depth_m"
TRANSIT_TIME = "transit_time_us_ft"
MAX_HORIZONTAL_STRESS = "max_horizontal_stress_psi"
MIN_HORIZONTAL_STRESS = "min_horizontal_stress_psi"
POISSON_RATIO = "poisson_ratio"
COHESION = "cohesion_psi"
FRICTION_ANGLE = "friction_angle_deg"

PROFILE_COLUMNS = [
    DEPTH,
    TRANSIT_TIME,
    MAX_HORIZONTAL_STRESS,
    MIN_HORIZONTAL_STRESS,
    POISSON_RATIO,
    COHESION,
    FRICTION_ANGLE,
]
"""Columns of the input profile, one row per depth below the seabed."""


@dataclass
class WellParameters:
    """Scalar parameters of the well and of the models.

    Parameters
    ----------
    water_depth : float
        Water depth (m). It is also the depth of the seabed.
    seawater_density : float
        Seawater density (g/cm³).
    gardner_a : float
        Gardner coefficient ``a`` in ``rho = a * V**b``.
    gardner_b : float
        Gardner exponent ``b``.
    ppg_conversion : float
        Conversion factor from psi/m to ppg (0.1704).
    eaton_exponent : float
        Exponent of Eaton's method for the sonic log.
    trend_base_depth : float
        Deepest depth (m) of the points used in the normal compaction fit.
    safety_margin : float
        Fraction of the window removed from each limit (0.1 = 10 %).
    """

    water_depth: float = 1000.0
    seawater_density: float = 1.03
    gardner_a: float = 0.234
    gardner_b: float = 0.25
    ppg_conversion: float = 0.1704
    eaton_exponent: float = 3.0
    trend_base_depth: float = 3200.0
    safety_margin: float = 0.10

    def to_dict(self) -> dict:
        """Return the parameters as a plain dict.

        Returns
        -------
        dict
            Field name -> value, in declaration order.
        """
        return asdict(self)


def validate_inputs(parameters: WellParameters, profile: pd.DataFrame) -> None:
    """Check that the inputs can produce a window.

    Parameters
    ----------
    parameters : WellParameters
        Scalar parameters of the well.
    profile : pandas.DataFrame
        Input profile with the columns in ``PROFILE_COLUMNS``.

    Raises
    ------
    ValueError
        With a message that names the first invalid input.
    """
    missing = [column for column in PROFILE_COLUMNS if column not in profile.columns]
    if missing:
        raise ValueError(f"The profile is missing the columns: {', '.join(missing)}.")
    if parameters.water_depth <= 0:
        raise ValueError("The water depth must be greater than zero.")
    if parameters.ppg_conversion <= 0:
        raise ValueError("The psi/m to ppg conversion factor must be greater than zero.")
    if not 0 <= parameters.safety_margin < 0.5:
        raise ValueError("The safety margin must be in [0, 0.5).")
    if profile.empty:
        raise ValueError("The profile has no rows.")
    if profile[PROFILE_COLUMNS].isna().any().any():
        raise ValueError("The profile has empty cells.")

    depths = profile[DEPTH]
    if (depths <= parameters.water_depth).any():
        raise ValueError("Every profile depth must be below the seabed (greater than the water depth).")
    if depths.duplicated().any():
        raise ValueError("The profile has repeated depths.")
    if (profile[TRANSIT_TIME] <= 0).any():
        raise ValueError("Transit times must be greater than zero.")
    if ((profile[POISSON_RATIO] <= 0) | (profile[POISSON_RATIO] >= 1)).any():
        raise ValueError("Poisson's ratios must be in (0, 1).")
    if ((profile[FRICTION_ANGLE] < 0) | (profile[FRICTION_ANGLE] >= 90)).any():
        raise ValueError("Friction angles must be in [0, 90) degrees.")
    if (depths <= parameters.trend_base_depth).sum() < 2:
        raise ValueError("The normal compaction fit needs at least two profile depths above the trend base depth.")


class OperationalWindow:
    """Build the operational window of a well.

    Parameters
    ----------
    parameters : WellParameters
        Scalar parameters of the well.
    profile : pandas.DataFrame
        One row per depth below the seabed, with the columns in
        ``PROFILE_COLUMNS``.

    Examples
    --------
    >>> window = OperationalWindow(parameters, profile)
    >>> results = window.calculate()
    """

    def __init__(self, parameters: WellParameters, profile: pd.DataFrame) -> None:
        self.parameters = parameters
        self.profile = profile.sort_values(DEPTH).reset_index(drop=True)
        self.results: pd.DataFrame | None = None
        self.trend: tuple[float, float] | None = None

    def calculate(self) -> pd.DataFrame:
        """Run every step and return the results table.

        The first row is the seabed (depth = water depth), where only the
        overburden is defined.

        Returns
        -------
        pandas.DataFrame
            Inputs plus every intermediate and final column, one row per depth.

        Raises
        ------
        ValueError
            If the inputs fail ``validate_inputs``.
        """
        validate_inputs(self.parameters, self.profile)
        seabed = pd.DataFrame({DEPTH: [self.parameters.water_depth]})
        df = pd.concat([seabed, self.profile[PROFILE_COLUMNS]], ignore_index=True)

        self._overburden(df)
        self.trend = self._fit_trend(df)
        self._pore_pressure(df)
        self._collapse(df)
        self._fracture(df)
        self._window(df)

        self.results = df
        return df

    def _overburden(self, df: pd.DataFrame) -> None:
        """Gardner density, overburden stress and overburden gradient.

        The first row (seabed) carries the water column; below it,
        ``rho = a * (1e6 / DT)**b`` and each layer adds ``rho * dD``.
        """
        p = self.parameters
        df["layer_thickness_m"] = df[DEPTH].diff()
        df["density_g_cm3"] = p.gardner_a * (1e6 / df[TRANSIT_TIME]) ** p.gardner_b
        df.loc[0, "density_g_cm3"] = p.seawater_density
        df["density_x_thickness"] = df["density_g_cm3"] * df["layer_thickness_m"]
        df.loc[0, "density_x_thickness"] = p.seawater_density * p.water_depth
        df["overburden_stress_psi"] = PSI_PER_KGF_CM2 * df["density_x_thickness"].cumsum()
        df["overburden_gradient_ppg"] = self._gradient(df["overburden_stress_psi"], df[DEPTH])

    def _fit_trend(self, df: pd.DataFrame) -> tuple[float, float]:
        """Fit the normal compaction line ``depth = A - B * ln(DT)``.

        Only the points down to ``trend_base_depth`` are used, like the
        logarithmic trend line of a spreadsheet.

        Returns
        -------
        tuple[float, float]
            The coefficients ``(A, B)``.
        """
        zone = df[(df[DEPTH] <= self.parameters.trend_base_depth) & df[TRANSIT_TIME].notna()]
        slope, intercept = np.polyfit(np.log(zone[TRANSIT_TIME]), zone[DEPTH], 1)
        return float(intercept), float(-slope)

    def _pore_pressure(self, df: pd.DataFrame) -> None:
        """Pore pressure gradient by Eaton's method.

        ``Gpp = Gov - (Gov - Gn) * (Tn / T)**n``, where ``Tn`` is the transit
        time on the normal trend and ``Gn`` is the hydrostatic gradient (the
        overburden gradient at the seabed).
        """
        a, b = self.trend
        hydrostatic = df.loc[0, "overburden_gradient_ppg"]
        df["normal_transit_time_us_ft"] = np.exp((a - df[DEPTH]) / b)
        df["hydrostatic_gradient_ppg"] = hydrostatic
        ratio = (df["normal_transit_time_us_ft"] / df[TRANSIT_TIME]) ** self.parameters.eaton_exponent
        df["pore_pressure_gradient_ppg"] = (
            df["overburden_gradient_ppg"] - (df["overburden_gradient_ppg"] - hydrostatic) * ratio
        )
        df["pore_pressure_psi"] = df["pore_pressure_gradient_ppg"] * df[DEPTH] * self.parameters.ppg_conversion

    def _collapse(self, df: pd.DataFrame) -> None:
        """Collapse gradient by the Mohr-Coulomb criterion.

        ``C0 = 2 S0 cos(phi) / (1 - sin(phi))`` and
        ``Pw = (3 sH - sh - C0 + Pp (tan²(45° + phi/2) - 1)) / (tan²(45° + phi/2) + 1)``.
        """
        phi = np.radians(df[FRICTION_ANGLE])
        df["friction_angle_rad"] = phi
        df["compressive_strength_psi"] = 2 * df[COHESION] * np.cos(phi) / (1 - np.sin(phi))
        tan2 = np.tan(np.pi / 4 + phi / 2) ** 2
        df["collapse_pressure_psi"] = (
            3 * df[MAX_HORIZONTAL_STRESS]
            - df[MIN_HORIZONTAL_STRESS]
            - df["compressive_strength_psi"]
            + df["pore_pressure_psi"] * (tan2 - 1)
        ) / (tan2 + 1)
        df["collapse_gradient_ppg"] = self._gradient(df["collapse_pressure_psi"], df[DEPTH])

    def _fracture(self, df: pd.DataFrame) -> None:
        """Fracture gradient ``Gfrac = K (Gov - Gpp) + Gpp``, with ``K = v / (1 - v)``."""
        df["stress_ratio_k"] = df[POISSON_RATIO] / (1 - df[POISSON_RATIO])
        df["fracture_gradient_ppg"] = (
            df["stress_ratio_k"] * (df["overburden_gradient_ppg"] - df["pore_pressure_gradient_ppg"])
            + df["pore_pressure_gradient_ppg"]
        )

    def _window(self, df: pd.DataFrame) -> None:
        """Window limits and safe limits after the safety margin.

        Lower limit = max(pore pressure, collapse); upper limit = fracture.
        Each limit is narrowed by ``safety_margin`` times the window width.
        """
        margin = self.parameters.safety_margin
        df["lower_limit_ppg"] = df[["pore_pressure_gradient_ppg", "collapse_gradient_ppg"]].max(axis=1, skipna=False)
        df["upper_limit_ppg"] = df["fracture_gradient_ppg"]
        df["window_width_ppg"] = df["upper_limit_ppg"] - df["lower_limit_ppg"]
        df["safe_lower_limit_ppg"] = df["lower_limit_ppg"] + margin * df["window_width_ppg"]
        df["safe_upper_limit_ppg"] = df["upper_limit_ppg"] - margin * df["window_width_ppg"]

    def _gradient(self, pressure_psi: pd.Series, depth_m: pd.Series) -> pd.Series:
        """Convert a pressure (psi) into a gradient (ppg) at the given depth."""
        return pressure_psi / (depth_m * self.parameters.ppg_conversion)


def calculate_operational_window(parameters: WellParameters, profile: pd.DataFrame) -> pd.DataFrame:
    """Compute the operational window in one call.

    Parameters
    ----------
    parameters : WellParameters
        Scalar parameters of the well.
    profile : pandas.DataFrame
        One row per depth below the seabed, with the columns in
        ``PROFILE_COLUMNS``.

    Returns
    -------
    pandas.DataFrame
        The results table of ``OperationalWindow.calculate``.
    """
    return OperationalWindow(parameters, profile).calculate()
