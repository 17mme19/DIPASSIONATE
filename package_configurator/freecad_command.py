"""FreeCAD command for selecting and generating a structured BGA package."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import FreeCAD
import FreeCADGui

from compat import QtCore, QtWidgets

from package_configurator.bga_generator import (
    BgaGeometryError,
    build_bga_model,
    get_bga_geometry,
)
from package_configurator.properties import (
    available_value_statuses,
    eligible_value_statuses,
    get_property_value,
)
from package_configurator.bga_generator import GENERATOR_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STRUCTURED_RECORDS = (
    PROJECT_ROOT / "package_configurator" / "data" / "packages" / "structured"
)
CATALOG_PATH = PROJECT_ROOT / "package_configurator" / "data" / "catalog" / "bga-properties.json"
_BALL_DETAILS_DOCK_NAME = "BgaBallDetailsPanel"


class BgaBallDetailsPanel(QtWidgets.QDockWidget):
    """Show measured and generated details for the selected BGA ball."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__("BGA Ball Details", parent)
        self.setObjectName(_BALL_DETAILS_DOCK_NAME)
        self.setMinimumWidth(280)
        self._details = QtWidgets.QFormLayout()
        content = QtWidgets.QWidget()
        content.setLayout(self._details)
        self.setWidget(content)
        self.clear_details()

    def clear_details(self) -> None:
        while self._details.rowCount():
            self._details.removeRow(0)
        label = QtWidgets.QLabel("Select a generated BGA ball.")
        label.setWordWrap(True)
        self._details.addRow(label)

    def show_ball(self, ball: Any) -> None:
        while self._details.rowCount():
            self._details.removeRow(0)

        shape_box = ball.Shape.BoundBox
        center = getattr(ball, "SeatingCenter", None)
        rows = [
            ("Package", getattr(ball, "PackageCode", ball.Name)),
            ("Array coordinate", getattr(ball, "ArrayCoordinate", "Unavailable")),
            ("Diameter", f"{float(ball.BallDiameter):.6g} mm"),
            ("Height", f"{float(ball.BallHeight):.6g} mm"),
            ("Radius", f"{float(ball.BallRadius):.6g} mm"),
            ("Seating center", _format_vector(center)),
            ("Crown sphere center", _format_vector(
                getattr(ball, "CrownSphereCenter", None)
            )),
            ("X bounds", _format_bounds(shape_box.XMin, shape_box.XMax)),
            ("Y bounds", _format_bounds(shape_box.YMin, shape_box.YMax)),
            ("Z bounds", _format_bounds(shape_box.ZMin, shape_box.ZMax)),
            ("Shape X size", f"{shape_box.XLength:.6g} mm"),
            ("Shape Y size", f"{shape_box.YLength:.6g} mm"),
            ("Shape Z size", f"{shape_box.ZLength:.6g} mm"),
        ]
        for name, value in rows:
            self._details.addRow(name + ":", QtWidgets.QLabel(value))


def _format_bounds(minimum: float, maximum: float) -> str:
    return f"{minimum:.6g} to {maximum:.6g} mm"


def _format_vector(vector: Any) -> str:
    if vector is None:
        return "Unavailable"
    return f"({vector.x:.6g}, {vector.y:.6g}, {vector.z:.6g}) mm"


class _BgaSelectionObserver:
    def __init__(self) -> None:
        self._panel: BgaBallDetailsPanel | None = None

    def addSelection(self, document: Any, object_name: str, sub_name: str) -> None:
        if not document:
            return
        ball = document.getObject(object_name)
        if ball is None or not hasattr(ball, "BallDiameter"):
            return
        panel = self._get_panel()
        panel.show_ball(ball)
        panel.show()
        panel.raise_()

    def removeSelection(self, document: Any, object_name: str, sub_name: str) -> None:
        self._clear_if_no_ball_selected()

    def clearSelection(self, document: Any) -> None:
        if self._panel is not None:
            self._panel.clear_details()
            self._panel.hide()

    def _get_panel(self) -> BgaBallDetailsPanel:
        if self._panel is None:
            self._panel = BgaBallDetailsPanel(FreeCADGui.getMainWindow())
            FreeCADGui.getMainWindow().addDockWidget(
                QtCore.Qt.RightDockWidgetArea,
                self._panel,
            )
        return self._panel

    def _clear_if_no_ball_selected(self) -> None:
        selected = FreeCADGui.Selection.getSelection()
        if not any(hasattr(item, "BallDiameter") for item in selected):
            self.clearSelection(None)


_bga_selection_observer = _BgaSelectionObserver()


class BgaPackageDialog(QtWidgets.QDialog):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BGA Package Generator")
        self.setMinimumWidth(420)
        self._records = self._load_records()
        self._catalog = self._load_catalog()
        self._catalog_by_id = {
            item["property_id"]: item for item in self._catalog.get("properties", [])
        }
        self._status_boxes: dict[str, Any] = {}

        layout = QtWidgets.QVBoxLayout(self)
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(QtWidgets.QLabel("Search:"))
        self._search_box = QtWidgets.QLineEdit()
        self._search_box.setPlaceholderText(
            "package code, description, family, manufacturer..."
        )
        self._search_box.textChanged.connect(self._filter_records)
        search_layout.addWidget(self._search_box, 1)
        layout.addLayout(search_layout)

        self._package_table = QtWidgets.QTableWidget(0, 5)
        self._package_table.setHorizontalHeaderLabels(
            ["Package", "Manufacturer", "Family", "Terminals", "Pitch"]
        )
        self._package_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._package_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self._package_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self._package_table.setAlternatingRowColors(True)
        self._package_table.verticalHeader().setVisible(False)
        self._package_table.itemSelectionChanged.connect(self._refresh_statuses)
        layout.addWidget(self._package_table)

        self._details = QtWidgets.QLabel()
        self._details.setWordWrap(True)
        self._details.setTextFormat(QtCore.Qt.RichText)
        self._details.setStyleSheet(
            "background: #1a1a2e; color: #dbeafe; padding: 6px; "
            "font-family: monospace;"
        )
        layout.addWidget(QtWidgets.QLabel("Package details:"))
        layout.addWidget(self._details)

        self._status_layout = QtWidgets.QFormLayout()
        layout.addWidget(QtWidgets.QLabel("Value selections:"))
        layout.addLayout(self._status_layout)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Review and Generate")
        buttons.accepted.connect(self._review_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._populate_package_table(self._records)
        self._refresh_statuses()

    def selected_record(self) -> dict[str, Any]:
        selected = self._package_table.selectedItems()
        if not selected:
            return self._records[0]
        record = selected[0].data(QtCore.Qt.UserRole)
        return record if isinstance(record, dict) else self._records[0]

    def selected_preferences(self) -> dict[str, str]:
        return {
            property_id: box.currentData()
            for property_id, box in self._status_boxes.items()
        }

    def _refresh_statuses(self) -> None:
        while self._status_layout.rowCount():
            self._status_layout.removeRow(0)
        self._status_boxes.clear()
        record = self.selected_record()
        self._update_details(record)
        for property_id, statuses in self._selectable_properties(record):
            definition = self._catalog_by_id[property_id]
            label = f"{definition['property']} ({definition.get('unit', 'unitless')})"
            box = QtWidgets.QComboBox()
            preferred = "NOM" if "NOM" in statuses else statuses[0]
            for status in statuses:
                value = get_property_value(
                    record,
                    property_id,
                    classifications=(status,),
                )
                box.addItem(
                    f"{status}: {self._format_value(value, definition.get('unit'))}",
                    status,
                )
            box.setCurrentIndex(max(0, statuses.index(preferred)))
            box.currentIndexChanged.connect(
                lambda _index, selected_record=record: self._update_details(
                    selected_record
                )
            )
            self._status_boxes[property_id] = box
            self._status_layout.addRow(label, box)

    def _update_details(self, record: dict[str, Any]) -> None:
        selected = self.selected_preferences()
        grouped: dict[str, list[str]] = {}
        for definition in self._catalog.get("properties", []):
            property_id = definition["property_id"]
            entries = self._property_entries(record, property_id)
            if not entries:
                continue
            statuses = {
                classification["code"]
                for entry in entries
                for classification in entry.get("classifications", [])
                if classification.get("category") == "value_status"
            }
            if statuses:
                status_values = []
                for status in ("MIN", "NOM", "MAX"):
                    if status not in statuses:
                        continue
                    value = next(
                        (
                            entry.get("value")
                            for entry in entries
                            if status in {
                                item["code"]
                                for item in entry.get("classifications", [])
                                if item.get("category") == "value_status"
                            }
                        ),
                        None,
                    )
                    display = self._format_value(value, definition.get("unit"))
                    if selected.get(property_id) == status:
                        display = f"<mark>{status}: {escape(display)}</mark>"
                    else:
                        display = f"{status}: {escape(display)}"
                    status_values.append(display)
                value_text = " | ".join(status_values)
            else:
                value = get_property_value(record, property_id)
                if isinstance(value, list):
                    value_text = escape(f"{len(value)} coordinate(s)")
                else:
                    value_text = escape(
                        self._format_value(value, definition.get("unit"))
                    )
            label = escape(definition.get("property", property_id))
            group = definition.get("group", "OTHER")
            grouped.setdefault(group, []).append(
                f"<b>{label}</b>: {value_text}"
            )

        lines: list[str] = []
        for group, properties in grouped.items():
            lines.append(f"<br><b>━━ {escape(group.replace('_', ' '))} ━━</b>")
            lines.extend(properties)
        self._details.setText(
            "<br>".join(lines) or "No package details available."
        )

    @staticmethod
    def _property_entries(
        record: dict[str, Any],
        property_id: str,
    ) -> list[dict[str, Any]]:
        properties = record.get("properties")
        if not isinstance(properties, dict):
            return []
        return [
            entry
            for entries in properties.values()
            if isinstance(entries, list)
            for entry in entries
            if entry.get("property_id") == property_id
        ]

    def _filter_records(self, text: str) -> None:
        query = text.strip().casefold()
        records = [
            record
            for record in self._records
            if not query or query in self._record_search_text(record)
        ]
        self._populate_package_table(records)
        self._refresh_statuses()

    def _populate_package_table(self, records: list[dict[str, Any]]) -> None:
        self._package_table.setRowCount(0)
        for record in records:
            row = self._package_table.rowCount()
            self._package_table.insertRow(row)
            values = (
                record.get("package_code", ""),
                record.get("manufacturer", ""),
                record.get("package_family", ""),
                self._display_property(record, "actual_terminals"),
                self._display_property(record, "ball_pitch"),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, record)
                self._package_table.setItem(row, column, item)
        if self._package_table.rowCount():
            self._package_table.selectRow(0)

    def _record_search_text(self, record: dict[str, Any]) -> str:
        values = [
            record.get("package_code"),
            record.get("package_description"),
            record.get("package_family"),
            record.get("package_sub_family"),
            record.get("manufacturer"),
        ]
        return " ".join(str(value) for value in values if value).casefold()

    @staticmethod
    def _display_property(record: dict[str, Any], property_id: str) -> str:
        value = get_property_value(record, property_id)
        return "" if value is None else str(value)

    def _selectable_properties(
        self,
        record: dict[str, Any],
    ) -> list[tuple[str, tuple[str, ...]]]:
        eligible = eligible_value_statuses(self._catalog)
        return [
            (property_id, statuses)
            for property_id, statuses in eligible.items()
            if len(available_value_statuses(record, property_id)) >= 2
            for statuses in (tuple(
                status
                for status in statuses
                if status in available_value_statuses(record, property_id)
            ),)
            if len(statuses) >= 2
        ]

    def _review_summary(self) -> str:
        record = self.selected_record()
        lines = [
            f"{record['package_code']} — "
            f"{record.get('package_description', '')}",
        ]
        for property_id in self._geometry_property_ids():
            definition = self._catalog_by_id.get(property_id, {})
            status = self._status_boxes[property_id].currentData() if property_id in self._status_boxes else None
            value = get_property_value(
                record,
                property_id,
                classifications=(status,) if status else ("NOM", "MIN", "MAX"),
            )
            if value is not None:
                chosen = f" ({status})" if status else ""
                lines.append(
                    f"{definition.get('property', property_id)}: "
                    f"{self._format_value(value, definition.get('unit'))}{chosen}"
                )
        return "\n".join(lines)

    def _geometry_property_ids(self) -> list[str]:
        return [
            definition["property_id"]
            for definition in self._catalog.get("properties", [])
            if "GEOMETRY_GENERATION" in definition.get("used_for", [])
        ]

    def _review_and_accept(self) -> None:
        errors = self._validate_configuration()
        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid BGA configuration",
                "\n".join(f"- {error}" for error in errors),
            )
            return
        summary = self._review_summary()
        answer = QtWidgets.QMessageBox.question(
            self,
            "Review BGA model",
            summary + "\n\nGenerate this model?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self.accept()

    def _validate_configuration(self) -> list[str]:
        record = self.selected_record()
        preferences = self.selected_preferences()
        errors: list[str] = []
        try:
            geometry = get_bga_geometry(
                record,
                value_status_preferences=preferences,
            )
        except (BgaGeometryError, ValueError) as error:
            return [str(error)]

        population = get_property_value(record, "array_population_type")
        omitted = get_property_value(record, "unpopulated_array_coordinates")
        maximum = geometry.columns * geometry.rows
        if population and str(population).upper() != "FULL":
            if not isinstance(omitted, list):
                errors.append("Depopulated arrays require explicit coordinates.")
            else:
                actual = get_property_value(record, "actual_terminals")
                if actual is not None and maximum - len(omitted) != actual:
                    errors.append(
                        f"Terminal count mismatch: expected {actual}, "
                        f"calculated {maximum - len(omitted)}."
                    )
        elif isinstance(omitted, list) and len(omitted) > maximum:
            errors.append("The omitted-coordinate list exceeds the array size.")

        if geometry.height_mm <= geometry.ball_height_mm:
            errors.append("Overall package height must exceed ball height.")
        return errors

    @staticmethod
    def _format_value(value: Any, unit: str | None) -> str:
        if value is None:
            return "Unavailable"
        if isinstance(value, float):
            text = f"{value:.6g}"
        else:
            text = str(value)
        if unit and unit not in {"text", "count"}:
            text += f" {unit}"
        return text

    @staticmethod
    def _load_records() -> list[dict[str, Any]]:
        records = []
        for path in sorted(STRUCTURED_RECORDS.glob("*.json")):
            records.append(json.loads(path.read_text(encoding="utf-8")))
        if not records:
            raise RuntimeError(f"No structured package records found in {STRUCTURED_RECORDS}")
        return records

    @staticmethod
    def _load_catalog() -> dict[str, Any]:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


class BgaPackageGeneratorCommand:
    def GetResources(self):
        return {
            "MenuText": "BGA Package Generator",
            "ToolTip": "Select a BGA package and generate it in FreeCAD",
        }

    def Activated(self):
        try:
            dialog = BgaPackageDialog()
        except (OSError, json.JSONDecodeError, RuntimeError) as error:
            QtWidgets.QMessageBox.critical(None, "BGA Generator", str(error))
            return
        if not dialog.exec_():
            return

        try:
            document = FreeCAD.ActiveDocument or FreeCAD.newDocument("BGA_Package")
            build_bga_model(
                dialog.selected_record(),
                document=document,
                value_status_preferences=dialog.selected_preferences(),
            )
            document.recompute()
            if FreeCADGui.activeDocument():
                FreeCADGui.activeDocument().activeView().viewAxonometric()
                FreeCADGui.activeDocument().activeView().fitAll()
        except BgaGeometryError as error:
            QtWidgets.QMessageBox.warning(None, "BGA Generator", str(error))
        except Exception as error:
            FreeCAD.Console.PrintError(f"BGA generation failed: {error}\n")
            QtWidgets.QMessageBox.critical(
                None,
                "BGA Generator",
                f"Generation failed: {error}",
            )

    def IsActive(self):
        return True


def _active_document() -> Any | None:
    return FreeCAD.ActiveDocument


def _configuration_for_document(document: Any) -> Any | None:
    for obj in document.Objects:
        if obj.Name.endswith("_Configuration") and hasattr(obj, "PackageCode"):
            return obj
    return None


def _bga_group_for_configuration(document: Any, configuration: Any) -> Any | None:
    for obj in document.Objects:
        if not hasattr(obj, "Group"):
            continue
        if configuration in obj.Group:
            return obj
    return None


def _selected_or_active_bga(document: Any) -> tuple[Any, Any] | None:
    selected = FreeCADGui.Selection.getSelection()
    configuration = next(
        (obj for obj in selected if hasattr(obj, "PackageCode")),
        None,
    )
    if configuration is None:
        configuration = _configuration_for_document(document)
    if configuration is None:
        return None
    group = _bga_group_for_configuration(document, configuration)
    return group, configuration


def _group_shapes(group: Any) -> list[Any]:
    shapes: list[Any] = []
    for child in getattr(group, "Group", []):
        if hasattr(child, "Shape") and not child.Shape.isNull():
            shapes.append(child)
        elif hasattr(child, "Group"):
            shapes.extend(_group_shapes(child))
    return shapes


class SaveBgaDocumentCommand:
    def GetResources(self):
        return {
            "MenuText": "Save BGA Configuration",
            "ToolTip": "Save the generated BGA model and its configuration",
        }

    def Activated(self):
        document = _active_document()
        if document is None:
            QtWidgets.QMessageBox.warning(None, "BGA", "No active document.")
            return
        path = document.FileName
        if path:
            document.save()
        else:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                None,
                "Save BGA Configuration",
                f"{document.Label}.FCStd",
                "FreeCAD Document (*.FCStd)",
            )
            if not path:
                return
            if not path.lower().endswith(".fcstd"):
                path += ".FCStd"
            document.saveAs(path)
        QtWidgets.QMessageBox.information(None, "BGA", f"Saved:\n{path}")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


class ExportBgaStepCommand:
    def GetResources(self):
        return {
            "MenuText": "Export BGA as STEP",
            "ToolTip": "Export the generated BGA body and balls as STEP",
        }

    def Activated(self):
        document = _active_document()
        selected = _selected_or_active_bga(document) if document else None
        if selected is None:
            QtWidgets.QMessageBox.warning(
                None, "BGA", "Generate a BGA model before exporting."
            )
            return
        group, configuration = selected
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            None,
            "Export BGA as STEP",
            f"{configuration.PackageCode}.step",
            "STEP Files (*.step *.stp)",
        )
        if not path:
            return
        if not path.lower().endswith((".step", ".stp")):
            path += ".step"
        try:
            import Part
            Part.export(_group_shapes(group), path)
            QtWidgets.QMessageBox.information(None, "BGA", f"STEP exported:\n{path}")
        except Exception as error:
            FreeCAD.Console.PrintError(f"BGA STEP export failed: {error}\n")
            QtWidgets.QMessageBox.critical(None, "BGA", f"STEP export failed:\n{error}")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


class BgaConfigurationReportCommand:
    def GetResources(self):
        return {
            "MenuText": "Write BGA Configuration Report",
            "ToolTip": "Write the persisted BGA configuration to a text report",
        }

    def Activated(self):
        document = _active_document()
        selected = _selected_or_active_bga(document) if document else None
        if selected is None:
            QtWidgets.QMessageBox.warning(None, "BGA", "No generated BGA configuration found.")
            return
        _, configuration = selected
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            None,
            "Write BGA Configuration Report",
            f"{configuration.PackageCode}_configuration.txt",
            "Text Files (*.txt)",
        )
        if not path:
            return
        if not path.lower().endswith(".txt"):
            path += ".txt"
        lines = [
            "BGA CONFIGURATION REPORT",
            f"Generator version: {GENERATOR_VERSION}",
        ]
        for name in configuration.PropertiesList:
            if name == "Label":
                continue
            lines.append(f"{name}: {getattr(configuration, name)}")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        QtWidgets.QMessageBox.information(None, "BGA", f"Report written:\n{path}")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


class RegenerateBgaCommand:
    def GetResources(self):
        return {
            "MenuText": "Regenerate from BGA Configuration",
            "ToolTip": "Regenerate a BGA model using its saved configuration",
        }

    def Activated(self):
        document = _active_document()
        selected = _selected_or_active_bga(document) if document else None
        if selected is None:
            QtWidgets.QMessageBox.warning(None, "BGA", "No saved BGA configuration found.")
            return
        group, configuration = selected
        record_path = STRUCTURED_RECORDS / f"microchip_lfbga_{configuration.PackageCode.lower()}.json"
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            preferences = json.loads(configuration.ValueStatusPreferences or "{}")
            build_bga_model(
                record,
                document=document,
                name=f"{configuration.PackageCode}_Regenerated",
                value_status_preferences=preferences,
            )
            document.recompute()
        except (OSError, json.JSONDecodeError, BgaGeometryError) as error:
            QtWidgets.QMessageBox.critical(None, "BGA", f"Regeneration failed:\n{error}")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


def _register_command(command_name: str, command: Any) -> None:
    try:
        FreeCADGui.addCommand(command_name, command)
        FreeCAD.Console.PrintMessage(
            f"{command_name} registered\n"
        )
    except Exception as error:
        FreeCAD.Console.PrintWarning(
            f"{command_name} registration skipped: {error}\n"
        )


if FreeCAD.GuiUp:
    _register_command(
        "BgaPackageGeneratorCommand",
        BgaPackageGeneratorCommand(),
    )
    _register_command("SaveBgaDocumentCommand", SaveBgaDocumentCommand())
    _register_command("ExportBgaStepCommand", ExportBgaStepCommand())
    _register_command(
        "BgaConfigurationReportCommand",
        BgaConfigurationReportCommand(),
    )
    _register_command("RegenerateBgaCommand", RegenerateBgaCommand())
    FreeCADGui.Selection.addObserver(_bga_selection_observer)
