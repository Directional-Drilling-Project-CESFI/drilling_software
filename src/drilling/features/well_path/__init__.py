"""Correção de trajetória 3D (Casos 1, 2 e 3).

Solvers públicos
----------------
``solve_case1``, ``solve_case2`` e ``solve_case3`` recebem os mesmos cinco
vetores usados pela GUI (``Pin``, ``Pbd``, ``p1``, ``pt``, ``v``) e devolvem
dicionários consumidos pelos plotters do PyVista. Os Casos 2 e 3 aceitam
``dls_deg`` (graus por 30 m, padrão ``DEFAULT_DLS_DEG_PER_30M``); o Caso 1
tem raio livre e não usa DLS.

Entrada tipada: ``WellPathInput`` e ``DEFAULT_WELL_PATH_INPUT`` em
``defaults``. A profundidade é **Z negativo**.
"""

from drilling.core import CorrectionResult, WellPathInput

from .defaults import CASE3_FEASIBLE_DIRECTION, DEFAULT_DLS_DEG_PER_30M, DEFAULT_WELL_PATH_INPUT
from .logic import solve_case1, solve_case2, solve_case3

__all__ = [
    "CASE3_FEASIBLE_DIRECTION",
    "CorrectionResult",
    "DEFAULT_DLS_DEG_PER_30M",
    "DEFAULT_WELL_PATH_INPUT",
    "WellPathInput",
    "solve_case1",
    "solve_case2",
    "solve_case3",
]
