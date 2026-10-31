"""Qt tab of the operational window.

The inputs (scalar parameters and the layer profile table) build a
``WellParameters`` and a profile ``DataFrame``; ``calculate_operational_window``
returns the results table, drawn by ``plot.plot_operational_window`` and
exported to CSV on request. The view holds no formulas.
"""

from __future__ import annotations

import math

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from drilling.gui.param_form import ParamForm

from .calculation import PROFILE_COLUMNS, WellParameters, calculate_operational_window
from .defaults import (
    BASE_CASE_PARAMETERS,
    OPERATIONAL_WINDOW_FIELD_SPECS,
    PROFILE_HEADERS,
    load_base_case_profile,
)
from .plot import plot_operational_window, show_empty_plot

EMPTY_PLOT_MESSAGE = "Fill in the inputs (or load the base case) and click Generate window."


def format_number(value: float) -> str:
    """Format a number for a table cell without losing precision.

    Parameters
    ----------
    value : float
        Number to format.

    Returns
    -------
    str
        ``""`` for NaN, an integer for whole numbers, otherwise the shortest
        text that reads back to the same float.
    """
    value = float(value)
    if math.isnan(value):
        return ""
    if value.is_integer():
        return str(int(value))
    return repr(value)


class OperationalWindowView(QWidget):
    """Input panel on the left, window plot and results table on the right."""

    def __init__(self) -> None:
        super().__init__()
        self.results: pd.DataFrame | None = None
        self.setObjectName("OperationalWindowView")
        self.setup_ui()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def setup_ui(self) -> None:
        """Build the input panel and the results panel side by side."""
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)
        root.addWidget(self.build_controls(), 0)
        root.addWidget(self.build_results_panel(), 1)

    def build_controls(self) -> QScrollArea:
        """Build the scrollable panel with the actions and the inputs."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(620)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        title = QLabel("Operational Window")
        title.setObjectName("Title")
        subtitle = QLabel("Pore pressure, collapse and fracture gradients from a sonic log")
        subtitle.setObjectName("Subtitle")
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(title)
        heading.addWidget(subtitle)

        self.base_case_button = QPushButton("Load base case")
        self.base_case_button.setToolTip("Fill every input with the base case")
        self.base_case_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.base_case_button.clicked.connect(self.load_base_case)

        header = QHBoxLayout()
        header.addLayout(heading, 1)
        header.addWidget(self.base_case_button, 0, Qt.AlignVCenter)
        layout.addLayout(header)

        self.generate_button = QPushButton("Generate window")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.setDefault(True)
        font = self.generate_button.font()
        font.setBold(True)
        self.generate_button.setFont(font)
        self.generate_button.clicked.connect(self.generate_window)
        layout.addWidget(self.generate_button)

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        layout.addWidget(self.parameters_group())
        layout.addWidget(self.profile_group(), 1)

        scroll.setWidget(panel)
        return scroll

    def parameters_group(self) -> QGroupBox:
        """Build the form with the scalar well parameters, initially zero."""
        group = QGroupBox("Well and model parameters")
        layout = QVBoxLayout(group)
        self.parameter_form = ParamForm(OPERATIONAL_WINDOW_FIELD_SPECS, {})
        layout.addLayout(self.parameter_form.layout)
        return group

    def profile_group(self) -> QGroupBox:
        """Build the editable layer profile table and its row buttons."""
        group = QGroupBox("Layer profile (one row per depth below the seabed)")
        layout = QVBoxLayout(group)

        self.profile_table = QTableWidget(0, len(PROFILE_COLUMNS))
        self.profile_table.setHorizontalHeaderLabels([PROFILE_HEADERS[column] for column in PROFILE_COLUMNS])
        self.profile_table.setAlternatingRowColors(True)
        self.profile_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.profile_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.profile_table.verticalHeader().setDefaultSectionSize(26)
        self.profile_table.setMinimumHeight(360)
        layout.addWidget(self.profile_table)

        buttons = QHBoxLayout()
        add_row = QPushButton("Add row")
        remove_rows = QPushButton("Remove selected rows")
        add_row.clicked.connect(lambda: self.add_profile_row())
        remove_rows.clicked.connect(self.remove_selected_rows)
        buttons.addWidget(add_row)
        buttons.addWidget(remove_rows)
        layout.addLayout(buttons)
        return group

    def build_results_panel(self) -> QTabWidget:
        """Build the result tabs (window plot, results table) with the CSV export in the corner."""
        self.results_tabs = QTabWidget()

        plot_tab = QWidget()
        plot_layout = QVBoxLayout(plot_tab)
        plot_layout.setContentsMargins(8, 8, 8, 8)
        self.canvas = FigureCanvas(Figure(figsize=(11, 8), dpi=100))
        self.canvas.setMinimumHeight(520)
        plot_layout.addWidget(NavigationToolbar(self.canvas, plot_tab))
        plot_layout.addWidget(self.canvas)
        self.results_tabs.addTab(plot_tab, "Window Plot")

        self.results_table = QTableWidget(0, 0)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.results_table.verticalHeader().setVisible(False)
        self.results_tabs.addTab(self.results_table, "Results Table")

        self.export_button = QPushButton("Export CSV...")
        self.export_button.setToolTip("Save the results table of the last generated window")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_csv)
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 4, 4)
        corner_layout.addWidget(self.export_button)
        self.results_tabs.setCornerWidget(corner, Qt.TopRightCorner)

        show_empty_plot(self.canvas.figure, EMPTY_PLOT_MESSAGE)
        self.canvas.draw_idle()
        return self.results_tabs

    # ------------------------------------------------------------------ #
    # Inputs
    # ------------------------------------------------------------------ #
    def load_base_case(self) -> None:
        """Fill every input with the base case; the user still clicks Generate."""
        self.parameter_form.set_values(BASE_CASE_PARAMETERS.to_dict())
        self.set_profile(load_base_case_profile())
        self.status_label.setText("Base case loaded. Click Generate window.")

    def set_profile(self, profile: pd.DataFrame) -> None:
        """Replace the profile table rows with the given profile.

        Parameters
        ----------
        profile : pandas.DataFrame
            Table with the columns in ``PROFILE_COLUMNS``.
        """
        self.profile_table.setRowCount(0)
        for values in profile[PROFILE_COLUMNS].itertuples(index=False):
            self.add_profile_row(values)

    def add_profile_row(self, values=None) -> None:
        """Append a profile row, empty or filled with ``values``.

        Parameters
        ----------
        values : sequence of float, optional
            One value per column of ``PROFILE_COLUMNS``.
        """
        row = self.profile_table.rowCount()
        self.profile_table.insertRow(row)
        for column in range(len(PROFILE_COLUMNS)):
            text = format_number(values[column]) if values else ""
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.profile_table.setItem(row, column, item)

    def remove_selected_rows(self) -> None:
        """Delete the rows that have a selected cell."""
        rows = sorted({index.row() for index in self.profile_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.profile_table.removeRow(row)

    def read_profile(self) -> pd.DataFrame:
        """Read the profile table into a ``DataFrame``.

        Decimal commas are accepted. Fully empty rows are skipped.

        Returns
        -------
        pandas.DataFrame
            Table with the columns in ``PROFILE_COLUMNS``.

        Raises
        ------
        ValueError
            If the table has no rows or a cell is empty or not a number.
        """
        rows = []
        for row in range(self.profile_table.rowCount()):
            texts = []
            for column in range(len(PROFILE_COLUMNS)):
                item = self.profile_table.item(row, column)
                texts.append(item.text().strip().replace(",", ".") if item is not None else "")
            if not any(texts):
                continue
            values = []
            for column, text in enumerate(texts):
                header = PROFILE_HEADERS[PROFILE_COLUMNS[column]]
                if not text:
                    raise ValueError(f"Profile row {row + 1}: '{header}' is empty.")
                try:
                    values.append(float(text))
                except ValueError:
                    raise ValueError(f"Profile row {row + 1}: '{header}' is not a number ({text!r}).") from None
            rows.append(values)
        if not rows:
            raise ValueError("The layer profile is empty. Fill in the table or load the base case.")
        return pd.DataFrame(rows, columns=PROFILE_COLUMNS)

    def read_parameters(self) -> WellParameters:
        """Read the scalar parameters from the form.

        Returns
        -------
        WellParameters
            The values currently in the form.
        """
        return WellParameters(**self.parameter_form.to_dict())

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def generate_window(self) -> None:
        """Compute the window from the inputs and refresh the plot and the table."""
        try:
            results = calculate_operational_window(self.read_parameters(), self.read_profile())
        except Exception as exc:
            QMessageBox.warning(self, "Invalid inputs", str(exc))
            return

        self.results = results
        plot_operational_window(self.canvas.figure, results)
        self.canvas.draw_idle()
        self.populate_results_table(results)
        self.export_button.setEnabled(True)
        self.results_tabs.setCurrentIndex(0)
        self.status_label.setText(f"Window generated for {len(results) - 1} profile depths.")

    def populate_results_table(self, results: pd.DataFrame) -> None:
        """Show every results column, rounded to four decimals.

        Parameters
        ----------
        results : pandas.DataFrame
            Table returned by ``calculate_operational_window``.
        """
        self.results_table.clear()
        self.results_table.setRowCount(len(results))
        self.results_table.setColumnCount(len(results.columns))
        self.results_table.setHorizontalHeaderLabels(list(results.columns))
        for row, values in enumerate(results.itertuples(index=False)):
            for column, value in enumerate(values):
                text = "" if pd.isna(value) else f"{value:.4f}"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.results_table.setItem(row, column, item)

    def export_csv(self) -> None:
        """Save the last generated results table to a CSV file chosen by the user."""
        if self.results is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export operational window", "operational_window.csv", "CSV (*.csv);;All files (*)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self.results.to_csv(path, index=False)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.status_label.setText(f"Results exported to {path}")
