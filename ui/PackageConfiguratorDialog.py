# SPDX-License-Identifier: GPL-3.0-or-later
"""Requirements-driven package selection dialog."""

from compat import QtWidgets, QtCore
from core.package_configurator import (
    ChipInfo, PackageRequirements, extract_chip_info, recommend_packages,
)
from leadframe.PackageDatabase import families


class PackageConfiguratorDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, document=None):
        super().__init__(parent)
        self.setWindowTitle("Select Package")
        self.setMinimumSize(820, 650)
        self._document = document
        self._recommendations = []
        self._build_ui()
        self._load_detected_chip()
        self._recommend()

    def _spin(self, minimum=0.0, maximum=1000.0, value=0.0):
        w = QtWidgets.QDoubleSpinBox()
        w.setRange(minimum, maximum)
        w.setValue(value)
        w.setDecimals(3)
        w.setSuffix(" mm")
        return w

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        detected = QtWidgets.QGroupBox("Chip information (GDS detected where available)")
        form = QtWidgets.QFormLayout(detected)
        self.chip_source = QtWidgets.QLabel()
        self.chip_length = self._spin()
        self.chip_width = self._spin()
        self.chip_thickness = self._spin(0, 100, 0)
        self.chip_pads = QtWidgets.QSpinBox()
        self.chip_pads.setRange(0, 100000)
        for label, widget in (
            ("Source:", self.chip_source),
            ("Die length:", self.chip_length),
            ("Die width:", self.chip_width),
            ("Die thickness:", self.chip_thickness),
            ("Bond pads / electrical pins:", self.chip_pads),
        ):
            form.addRow(label, widget)
        self.chip_notes = QtWidgets.QLineEdit()
        self.chip_notes.setPlaceholderText("Additional chip information, die attach or pad notes")
        form.addRow("Additional information:", self.chip_notes)
        root.addWidget(detected)

        constraints = QtWidgets.QGroupBox("PCB / Assembly Constraints")
        cform = QtWidgets.QFormLayout(constraints)
        self.max_length = self._spin()
        self.max_width = self._spin()
        self.max_height = self._spin(0, 100, 0)
        self.min_pitch = self._spin(0, 10, 0)
        self.temp_min = QtWidgets.QDoubleSpinBox()
        self.temp_min.setRange(-273, 1000)
        self.temp_min.setSuffix(" °C")
        self.temp_max = QtWidgets.QDoubleSpinBox()
        self.temp_max.setRange(-273, 1000)
        self.temp_max.setValue(85)
        self.temp_max.setSuffix(" °C")
        self.pcb_layers = QtWidgets.QSpinBox()
        self.pcb_layers.setRange(0, 64)
        self.hdi = QtWidgets.QCheckBox("HDI / microvia capable")
        self.family = QtWidgets.QComboBox()
        self.family.addItem("Library selects family", "")
        for item in families():
            self.family.addItem(item, item)
        self.assembly = QtWidgets.QLineEdit()
        self.thermal = QtWidgets.QLineEdit()
        self.electrical = QtWidgets.QLineEdit()
        self.other = QtWidgets.QLineEdit()
        for label, widget in (
            ("Maximum package length:", self.max_length),
            ("Maximum package width:", self.max_width),
            ("Maximum package height:", self.max_height),
            ("Minimum supported package pitch:", self.min_pitch),
            ("Operating temperature min:", self.temp_min),
            ("Operating temperature max:", self.temp_max),
            ("PCB layers:", self.pcb_layers),
            ("Assembly capability:", self.assembly),
            ("Thermal requirement:", self.thermal),
            ("Electrical requirement:", self.electrical),
            ("Other manufacturing constraints:", self.other),
            ("Recommended family:", self.family),
        ):
            cform.addRow(label, widget)
        cform.addRow("", self.hdi)
        root.addWidget(constraints)

        self.results = QtWidgets.QTableWidget(0, 5)
        self.results.setHorizontalHeaderLabels(
            ["Package", "Family", "Pins", "Body (mm)", "Why it fits"])
        self.results.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.results.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.results.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.results.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.results, 1)
        self.status = QtWidgets.QLabel()
        root.addWidget(self.status)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Use selected package")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        for widget in (self.max_length, self.max_width, self.max_height,
                       self.min_pitch, self.family, self.pcb_layers, self.hdi):
            signal = getattr(widget, "valueChanged", None) or getattr(widget, "currentIndexChanged", None)
            if signal:
                signal.connect(self._recommend)

    def _load_detected_chip(self):
        try:
            import FreeCAD
            info = extract_chip_info(self._document or FreeCAD.activeDocument())
        except ImportError:
            info = ChipInfo()
        self.chip_source.setText(info.source)
        self.chip_length.setValue(info.length_mm)
        self.chip_width.setValue(info.width_mm)
        self.chip_thickness.setValue(info.thickness_mm)
        self.chip_pads.setValue(info.pad_count)

    def _requirements(self):
        def optional(widget):
            value = widget.value()
            return value if value > 0 else None
        return ChipInfo(self.chip_length.value(), self.chip_width.value(),
                        self.chip_thickness.value(), self.chip_pads.value(),
                        self.chip_source.text(), self.chip_notes.text()), PackageRequirements(
            max_length_mm=optional(self.max_length),
            max_width_mm=optional(self.max_width),
            max_height_mm=optional(self.max_height),
            operating_temp_min_c=self.temp_min.value(),
            operating_temp_max_c=self.temp_max.value(),
            thermal_requirement=self.thermal.text(),
            electrical_requirement=self.electrical.text(),
            min_supported_pitch_mm=optional(self.min_pitch),
            pcb_layers=self.pcb_layers.value() or None,
            hdi_capable=self.hdi.isChecked(),
            assembly_capability=self.assembly.text(),
            other_constraints=self.other.text(),
            preferred_family=self.family.currentData() or "",
        )

    def _recommend(self):
        chip, req = self._requirements()
        self._recommendations = recommend_packages(chip, req)
        self.results.setRowCount(0)
        for recommendation in self._recommendations:
            pkg = recommendation.package
            row = self.results.rowCount()
            self.results.insertRow(row)
            body = f"{pkg.body_length_mm} × {pkg.body_width_mm} × {pkg.body_height_mm}"
            values = [pkg.name, pkg.family, str(pkg.total_pins), body,
                      ", ".join(recommendation.reasons) or "compatible"]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setData(QtCore.Qt.UserRole, recommendation)
                self.results.setItem(row, col, item)
        self.status.setText(f"{len(self._recommendations)} compatible package(s) found.")

    def selected_package(self):
        items = self.results.selectedItems()
        return items[0].data(QtCore.Qt.UserRole).package if items else None

    def get_config(self):
        chip, requirements = self._requirements()
        package = self.selected_package()
        return {"package": package, "chip": chip, "requirements": requirements}

    def accept(self):
        if self.selected_package() is None:
            QtWidgets.QMessageBox.warning(self, "Select a package",
                                          "Select a recommended package first.")
            return
        super().accept()

