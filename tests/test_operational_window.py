"""Operational window: base-case golden, input validation and the Qt tab."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from drilling.features.operational_window import (
    BASE_CASE_PARAMETERS,
    PROFILE_COLUMNS,
    OperationalWindow,
    WellParameters,
    calculate_operational_window,
    load_base_case_profile,
)

from tests.numeric import assert_close, load_golden


@pytest.fixture(scope="module")
def golden() -> dict:
    """Committed curves of the base case."""
    return load_golden("operational_window_base_case.json")


def _as_array(values: list) -> np.ndarray:
    """Convert a golden column (``null`` for NaN) into a float array."""
    return np.array([np.nan if value is None else value for value in values], dtype=float)


def test_base_case_matches_golden(golden: dict) -> None:
    """The base case reproduces the frozen curves and the normal-trend fit."""
    assert BASE_CASE_PARAMETERS.to_dict() == golden["parameters"]
    window = OperationalWindow(BASE_CASE_PARAMETERS, load_base_case_profile())
    results = window.calculate()

    assert_close(window.trend, golden["trend"], name="trend")
    assert_close(results["depth_m"], golden["depth_m"], name="depth_m")
    for column, expected in golden["columns"].items():
        np.testing.assert_allclose(
            results[column].to_numpy(), _as_array(expected), rtol=1e-10, atol=1e-10, err_msg=column
        )


def test_base_case_window_is_open_below_the_seabed() -> None:
    """The safe limits stay ordered: lower <= safe lower <= safe upper <= upper."""
    results = calculate_operational_window(BASE_CASE_PARAMETERS, load_base_case_profile()).iloc[1:]
    assert (results["safe_lower_limit_ppg"] >= results["lower_limit_ppg"]).all()
    assert (results["safe_upper_limit_ppg"] >= results["safe_lower_limit_ppg"]).all()
    assert (results["upper_limit_ppg"] >= results["safe_upper_limit_ppg"]).all()


def test_profile_order_does_not_change_results() -> None:
    """Profile rows are sorted by depth before the calculation."""
    profile = load_base_case_profile()
    expected = calculate_operational_window(BASE_CASE_PARAMETERS, profile)
    shuffled = calculate_operational_window(BASE_CASE_PARAMETERS, profile.sample(frac=1.0, random_state=0))
    pd.testing.assert_frame_equal(expected, shuffled)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"water_depth": 0.0}, "water depth"),
        ({"ppg_conversion": 0.0}, "conversion factor"),
        ({"safety_margin": 0.5}, "safety margin"),
        ({"water_depth": 1300.0}, "below the seabed"),
        ({"trend_base_depth": 1260.0}, "at least two"),
    ],
)
def test_invalid_parameters_are_rejected(change: dict, message: str) -> None:
    """Invalid scalar parameters raise a ValueError that names the problem."""
    parameters = WellParameters(**{**BASE_CASE_PARAMETERS.to_dict(), **change})
    with pytest.raises(ValueError, match=message):
        calculate_operational_window(parameters, load_base_case_profile())


def test_invalid_profile_is_rejected() -> None:
    """Empty profiles, missing columns and out-of-range values are rejected."""
    profile = load_base_case_profile()
    with pytest.raises(ValueError, match="no rows"):
        calculate_operational_window(BASE_CASE_PARAMETERS, profile.iloc[0:0])
    with pytest.raises(ValueError, match="missing the columns"):
        calculate_operational_window(BASE_CASE_PARAMETERS, profile.drop(columns="cohesion_psi"))
    bad = profile.copy()
    bad.loc[3, "poisson_ratio"] = 1.2
    with pytest.raises(ValueError, match="Poisson"):
        calculate_operational_window(BASE_CASE_PARAMETERS, bad)


@pytest.fixture(scope="module")
def qt_app():
    """A QApplication on the offscreen platform."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_view_loads_base_case_generates_and_exports(qt_app, tmp_path, monkeypatch) -> None:
    """Base case -> Generate -> Export writes the same table as the library call."""
    from PySide6.QtWidgets import QFileDialog

    from drilling.features.operational_window.view import OperationalWindowView

    view = OperationalWindowView()
    assert view.profile_table.rowCount() == 0
    assert not view.export_button.isEnabled()

    view.load_base_case()
    assert view.read_parameters() == BASE_CASE_PARAMETERS
    pd.testing.assert_frame_equal(view.read_profile(), load_base_case_profile())

    view.generate_window()
    expected = calculate_operational_window(BASE_CASE_PARAMETERS, load_base_case_profile())
    pd.testing.assert_frame_equal(view.results, expected)
    assert view.export_button.isEnabled()
    assert view.results_table.rowCount() == len(expected)

    target = tmp_path / "window"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), "CSV (*.csv)"))
    view.export_csv()
    exported = pd.read_csv(tmp_path / "window.csv")
    assert list(exported.columns) == list(expected.columns)
    pd.testing.assert_frame_equal(exported, expected, check_dtype=False)


def test_view_reports_bad_cells(qt_app) -> None:
    """A non-numeric profile cell names its row and column."""
    from drilling.features.operational_window.view import OperationalWindowView

    view = OperationalWindowView()
    view.add_profile_row([1250, 151, 2709.4, 2584.75, 0.36, 397.8, 37.3])
    view.profile_table.item(0, 4).setText("abc")
    with pytest.raises(ValueError, match="row 1: 'Poisson's ratio'"):
        view.read_profile()
    view.profile_table.item(0, 4).setText("0,36")
    assert view.read_profile().loc[0, "poisson_ratio"] == 0.36
    assert list(view.read_profile().columns) == PROFILE_COLUMNS
