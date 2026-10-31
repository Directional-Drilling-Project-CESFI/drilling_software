"""Matplotlib drawing of the operational window on an existing ``Figure``."""

from __future__ import annotations

import pandas as pd
from matplotlib.figure import Figure

from .calculation import DEPTH

GRADIENT_CURVES = [
    ("hydrostatic_gradient_ppg", "Hydrostatic", "#0ea5e9"),
    ("pore_pressure_gradient_ppg", "Pore pressure", "#2563eb"),
    ("collapse_gradient_ppg", "Collapse", "#f59e0b"),
    ("fracture_gradient_ppg", "Fracture", "#dc2626"),
    ("overburden_gradient_ppg", "Overburden", "#4b5563"),
]
"""Results column, legend label and color of each gradient curve."""


def plot_operational_window(figure: Figure, results: pd.DataFrame) -> None:
    """Draw the gradients and the operational window versus depth.

    Parameters
    ----------
    figure : matplotlib.figure.Figure
        Figure to draw on. It is cleared first.
    results : pandas.DataFrame
        Table returned by ``calculate_operational_window``.
    """
    figure.clear()
    gradients_ax, window_ax = figure.subplots(1, 2, sharey=True)
    depth = results[DEPTH]

    for column, label, color in GRADIENT_CURVES:
        gradients_ax.plot(results[column], depth, label=label, color=color, linewidth=1.6)
    gradients_ax.set_title("Gradients vs depth")

    window_ax.fill_betweenx(
        depth,
        results["safe_lower_limit_ppg"],
        results["safe_upper_limit_ppg"],
        color="#22c55e",
        alpha=0.25,
        label="Window with safety margin",
    )
    window_ax.plot(results["lower_limit_ppg"], depth, "k--", linewidth=1.4, label="Lower limit")
    window_ax.plot(results["upper_limit_ppg"], depth, "k-", linewidth=1.4, label="Upper limit")
    window_ax.set_title("Operational window")

    for ax in (gradients_ax, window_ax):
        ax.set_xlabel("Gradient (ppg)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower left")
    gradients_ax.set_ylabel("Depth (m)")
    gradients_ax.invert_yaxis()
    figure.tight_layout()


def show_empty_plot(figure: Figure, message: str) -> None:
    """Clear the figure and write a centered placeholder message.

    Parameters
    ----------
    figure : matplotlib.figure.Figure
        Figure to draw on.
    message : str
        Text shown in the middle of the figure.
    """
    figure.clear()
    ax = figure.add_subplot(1, 1, 1)
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center", color="#6b7280", fontsize=12, transform=ax.transAxes)
