"""DLS configurável dos Casos 2 e 3 da correção de trajetória."""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from drilling.features.well_path.defaults import (
    CASE3_FEASIBLE_DIRECTION,
    DEFAULT_DLS_DEG_PER_30M,
    DEFAULT_WELL_PATH_INPUT,
)
from drilling.features.well_path.logic import dls_to_radius, solve_case2, solve_case3


def _kwargs(v=None) -> dict:
    kwargs = DEFAULT_WELL_PATH_INPUT.solver_kwargs()
    if v is not None:
        kwargs["v"] = v.as_array()
    return kwargs


def test_default_dls_matches_solver_defaults() -> None:
    """O padrão da GUI é o mesmo DLS que os solvers já usavam (3°/30 m)."""
    assert DEFAULT_DLS_DEG_PER_30M == 3.0
    for solver in (solve_case2, solve_case3):
        assert inspect.signature(solver).parameters["dls_deg"].default == DEFAULT_DLS_DEG_PER_30M


def test_case2_default_dls_is_unchanged() -> None:
    """Sem passar ``dls_deg`` o Caso 2 dá o mesmo resultado de antes."""
    implicit = solve_case2(**_kwargs())
    explicit = solve_case2(**_kwargs(), dls_deg=DEFAULT_DLS_DEG_PER_30M)
    assert implicit["radius"] == pytest.approx(dls_to_radius(3.0))
    assert implicit["total_length"] == pytest.approx(explicit["total_length"])


@pytest.mark.parametrize("dls", [1.5, 4.0, 6.0])
def test_case2_radius_follows_dls(dls: float) -> None:
    """O raio do arco do Caso 2 segue o DLS informado."""
    result = solve_case2(**_kwargs(), dls_deg=dls)
    assert result["radius"] == pytest.approx(dls_to_radius(dls))
    assert np.allclose(np.linalg.norm(result["arc"] - result["center"], axis=1), result["radius"])


def test_case3_radii_follow_dls() -> None:
    """Os dois arcos do Caso 3 usam o DLS informado."""
    result = solve_case3(**_kwargs(CASE3_FEASIBLE_DIRECTION), dls_deg=4.0)
    assert result["alignment_radius"] == pytest.approx(dls_to_radius(4.0))
    assert result["main_radius"] == pytest.approx(dls_to_radius(4.0))
