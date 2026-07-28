"""Create a basic parametric BGA model from a structured package record."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from package_configurator.properties import (
    VALID_VALUE_STATUSES,
    available_value_statuses,
    get_property_value,
)


class BgaGeometryError(ValueError):
    """Raised when a package record lacks geometry needed for generation."""


VALID_VALUE_STATUSES = ("NOM", "MIN", "MAX")
BALL_PROFILE = "truncated_spherical_profile"
GENERATOR_VERSION = "1"
DEFAULT_BGA_COLUMN_LABELS = tuple(
    letter for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if letter not in {"I", "O", "Q", "S"}
)
_DEPOPULATION_GROUP_PATTERN = re.compile(
    r"(?P<left>\([^)]*\)|[A-Z0-9,-]+)\s*[Xx]\s*"
    r"(?P<right>\([^)]*\)|[A-Z0-9,-]+)"
)


@dataclass(frozen=True)
class BgaGeometry:
    length_mm: float
    width_mm: float
    height_mm: float
    pitch_mm: float
    ball_diameter_mm: float
    ball_height_mm: float
    columns: int
    rows: int


def parse_depopulation_pattern(pattern: str) -> list[str]:
    """Convert manufacturer row/column notation into coordinate strings."""
    coordinates: set[str] = set()
    for match in _DEPOPULATION_GROUP_PATTERN.finditer(pattern.upper()):
        left = _expand_axis(match.group("left"))
        right = _expand_axis(match.group("right"))
        if not left or not right:
            raise BgaGeometryError(f"Unsupported depopulation pattern: {pattern}")
        if left[0].isdigit() and right[0].isalpha():
            rows, columns = left, right
        elif left[0].isalpha() and right[0].isdigit():
            columns, rows = left, right
        else:
            raise BgaGeometryError(f"Unsupported depopulation pattern: {pattern}")
        coordinates.update(f"{column}{row}" for row in rows for column in columns)
    if not coordinates:
        raise BgaGeometryError(f"Unsupported depopulation pattern: {pattern}")
    return sorted(coordinates, key=lambda item: (int(item[1:]), item[0]))


def _expand_axis(value: str) -> list[str]:
    tokens = value.strip("()").replace(" ", "").split(",")
    expanded: list[str] = []
    for token in tokens:
        if "-" not in token:
            expanded.append(token)
            continue
        start, end = token.split("-", 1)
        if start.isalpha() and end.isalpha():
            expanded.extend(
                chr(code) for code in range(ord(start), ord(end) + 1)
            )
        elif start.isdigit() and end.isdigit():
            expanded.extend(
                str(number) for number in range(int(start), int(end) + 1)
            )
        else:
            raise BgaGeometryError(f"Unsupported axis range: {value}")
    return expanded


def get_bga_geometry(
    record: dict[str, Any],
    *,
    value_status_preferences: dict[str, str] | None = None,
    ball_diameter_status: str | None = None,
) -> BgaGeometry:
    """Extract BGA geometry using explicit preferences for multi-status values."""
    if record.get("package_family") != "BGA":
        raise BgaGeometryError("Only BGA package records are supported.")
    preferences = dict(value_status_preferences or {})
    if ball_diameter_status is not None:
        preferences.setdefault("ball_diameter", ball_diameter_status)
    for property_id, selected in preferences.items():
        if selected.upper() not in VALID_VALUE_STATUSES:
            allowed = ", ".join(VALID_VALUE_STATUSES)
            raise BgaGeometryError(
                f"Invalid value status '{selected}' for '{property_id}'. "
                f"Choose one of: {allowed}."
            )

    def required(property_id: str, label: str) -> float:
        available = available_value_statuses(record, property_id)
        selected = preferences.get(property_id)
        if selected is not None:
            selected = selected.upper()
            if selected not in available:
                raise BgaGeometryError(
                    f"Cannot generate {record.get('package_code', '<unknown>')}: "
                    f"{selected} value for {label} ({property_id}) is unavailable."
                )
        elif len(available) > 1:
            choices = ", ".join(available)
            raise BgaGeometryError(
                f"Cannot generate {record.get('package_code', '<unknown>')}: "
                f"choose a value status for {property_id}: {choices}."
            )
        classifications = (selected,) if selected else available or VALID_VALUE_STATUSES
        value = get_property_value(
            record,
            property_id,
            classifications=classifications,
            value_status_preferences=preferences,
        )
        if value is None:
            raise BgaGeometryError(
                f"Cannot generate {record.get('package_code', '<unknown>')}: "
                f"missing value for {label} ({property_id}). "
                f"Choose another value status if available."
            )
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise BgaGeometryError(
                f"Cannot generate {record.get('package_code', '<unknown>')}: "
                f"{label} must be a positive number."
            )
        return float(value)

    def required_int(property_id: str, label: str) -> int:
        value = required(property_id, label)
        if not value.is_integer():
            raise BgaGeometryError(f"{label} must be an integer.")
        return int(value)

    return BgaGeometry(
        length_mm=required("overall_package_length", "package length"),
        width_mm=required("overall_package_width", "package width"),
        height_mm=required("overall_package_height", "package height"),
        pitch_mm=required("ball_pitch", "ball pitch"),
        ball_diameter_mm=required("ball_diameter", "ball diameter"),
        ball_height_mm=required("ball_height", "ball height"),
        columns=required_int("ball_array_columns", "array columns"),
        rows=required_int("ball_array_rows", "array rows"),
    )


def build_bga_model(
    record: dict[str, Any],
    document: Any | None = None,
    *,
    name: str | None = None,
    ball_diameter_status: str = "NOM",
    value_status_preferences: dict[str, str] | None = None,
) -> Any:
    """Build a basic body-and-ball BGA model in a FreeCAD document.

    Every required property with multiple available MIN/NOM/MAX values must
    have an explicit entry in ``value_status_preferences``.
    Depopulated arrays must provide explicit coordinate lists in the record.
    """
    population = get_property_value(record, "array_population_type")
    unpopulated = get_property_value(record, "unpopulated_array_coordinates")
    if population and str(population).upper() != "FULL" and not isinstance(
        unpopulated, list
    ):
        raise BgaGeometryError(
            f"Cannot generate {record.get('package_code', '<unknown>')}: "
            "depopulation coordinates must be an explicit list."
        )
    geometry = get_bga_geometry(
        record,
        ball_diameter_status=ball_diameter_status,
        value_status_preferences=value_status_preferences,
    )
    if isinstance(unpopulated, list):
        maximum = geometry.columns * geometry.rows
        invalid = [
            coordinate
            for coordinate in unpopulated
            if not _valid_coordinate(coordinate, geometry.columns, geometry.rows)
        ]
        if invalid:
            raise BgaGeometryError(
                f"Cannot generate {record.get('package_code', '<unknown>')}: "
                f"invalid depopulation coordinates: {', '.join(invalid)}."
            )
        actual = get_property_value(record, "actual_terminals")
        if actual is not None and maximum - len(unpopulated) != actual:
            raise BgaGeometryError(
                f"Cannot generate {record.get('package_code', '<unknown>')}: "
                "depopulation coordinates do not match actual terminal count."
            )

    try:
        import FreeCAD
        import Part  
    except ImportError as error:
        raise BgaGeometryError(
            "FreeCAD and Part are required to build a BGA model."
        ) from error

    doc = document or FreeCAD.ActiveDocument or FreeCAD.newDocument(
        name or f"BGA_{record['package_code']}"
    )
    group = doc.addObject("App::DocumentObjectGroup", name or f"BGA_{record['package_code']}")
    group.Label = f"{record['package_code']} BGA"

    body_height = geometry.height_mm - geometry.ball_height_mm
    if body_height <= 0:
        raise BgaGeometryError(
            f"Cannot generate {record['package_code']}: package height must exceed ball height."
        )

    configuration = doc.addObject(
        "App::FeaturePython",
        f"{record['package_code']}_Configuration",
    )
    configuration.Label = f"{record['package_code']} Configuration"
    _add_configuration_properties(
        configuration,
        record,
        geometry,
        value_status_preferences,
        unpopulated,
    )
    group.addObject(configuration)

    body = doc.addObject("Part::Feature", f"{record['package_code']}_Body")
    body.Shape = Part.makeBox(
        geometry.length_mm,
        geometry.width_mm,
        body_height,
        FreeCAD.Vector(-geometry.length_mm / 2, -geometry.width_mm / 2, geometry.ball_height_mm),
    )
    group.addObject(body)

    balls = doc.addObject("App::DocumentObjectGroup", f"{record['package_code']}_Balls")
    group.addObject(balls)
    radius = geometry.ball_diameter_mm / 2
    x0 = -(geometry.columns - 1) * geometry.pitch_mm / 2
    y0 = -(geometry.rows - 1) * geometry.pitch_mm / 2
    column_labels = DEFAULT_BGA_COLUMN_LABELS[: geometry.columns]
    for row in range(geometry.rows):
        for column, column_label in enumerate(column_labels):
            coordinate = f"{column_label}{row + 1}"
            if isinstance(unpopulated, list) and coordinate in unpopulated:
                continue
            ball = doc.addObject(
                "Part::Feature",
                f"{record['package_code']}_Ball_{row + 1:02d}_{column + 1:02d}",
            )
            ball.Label = f"{record['package_code']} Ball {coordinate}"
            ball.addProperty("App::PropertyString", "PackageCode", "BGA")
            ball.PackageCode = record["package_code"]
            ball.addProperty("App::PropertyString", "ArrayCoordinate", "BGA")
            ball.ArrayCoordinate = coordinate
            ball.addProperty("App::PropertyLength", "BallDiameter", "BGA")
            ball.BallDiameter = geometry.ball_diameter_mm
            ball.addProperty("App::PropertyLength", "BallHeight", "BGA")
            ball.BallHeight = geometry.ball_height_mm
            ball.addProperty("App::PropertyLength", "BallRadius", "BGA")
            ball.BallRadius = radius
            ball.addProperty("App::PropertyString", "BallProfile", "BGA")
            ball.BallProfile = BALL_PROFILE
            center = FreeCAD.Vector(
                x0 + column * geometry.pitch_mm,
                y0 + row * geometry.pitch_mm,
                0,
            )
            ball.addProperty("App::PropertyVector", "SeatingCenter", "BGA")
            ball.SeatingCenter = center
            curvature_radius = (
                radius * radius + geometry.ball_height_mm ** 2
            ) / (2 * geometry.ball_height_mm)
            ball.addProperty("App::PropertyVector", "CrownSphereCenter", "BGA")
            ball.CrownSphereCenter = FreeCAD.Vector(
                center.x,
                center.y,
                geometry.ball_height_mm - curvature_radius,
            )
            ball.Shape = _make_truncated_spherical_ball(
                Part,
                FreeCAD,
                center.x,
                center.y,
                geometry.ball_diameter_mm,
                geometry.ball_height_mm,
            )
            balls.addObject(ball)

    doc.recompute()
    return group


def _add_configuration_properties(
    configuration: Any,
    record: dict[str, Any],
    geometry: BgaGeometry,
    value_status_preferences: dict[str, str] | None,
    unpopulated: Any,
) -> None:
    """Persist the source record and choices used to create the model."""
    properties = (
        ("App::PropertyString", "Manufacturer", record.get("manufacturer") or ""),
        ("App::PropertyString", "PackageCode", record.get("package_code") or ""),
        ("App::PropertyString", "PackageFamily", record.get("package_family") or ""),
        (
            "App::PropertyString",
            "PackageSubFamily",
            record.get("package_sub_family") or "",
        ),
        ("App::PropertyString", "DrawingNumber", record.get("drawing_number") or ""),
        ("App::PropertyInteger", "DocumentYear", record.get("document_year") or 0),
        ("App::PropertyString", "BallProfile", BALL_PROFILE),
        ("App::PropertyString", "GeneratorVersion", GENERATOR_VERSION),
        ("App::PropertyLength", "PackageLength", geometry.length_mm),
        ("App::PropertyLength", "PackageWidth", geometry.width_mm),
        ("App::PropertyLength", "PackageHeight", geometry.height_mm),
        ("App::PropertyLength", "BallDiameter", geometry.ball_diameter_mm),
        ("App::PropertyLength", "BallHeight", geometry.ball_height_mm),
        ("App::PropertyLength", "BallPitch", geometry.pitch_mm),
        ("App::PropertyInteger", "ArrayColumns", geometry.columns),
        ("App::PropertyInteger", "ArrayRows", geometry.rows),
        (
            "App::PropertyString",
            "ValueStatusPreferences",
            json.dumps(value_status_preferences or {}, sort_keys=True),
        ),
        (
            "App::PropertyString",
            "UnpopulatedCoordinates",
            json.dumps(unpopulated if isinstance(unpopulated, list) else []),
        ),
    )
    for property_type, property_name, value in properties:
        configuration.addProperty(property_type, property_name, "Configuration")
        setattr(configuration, property_name, value)


def _make_truncated_spherical_ball(
    part_module: Any,
    freecad_module: Any,
    center_x: float,
    center_y: float,
    diameter_mm: float,
    height_mm: float,
) -> Any:
    """Create a spherical crown with the requested diameter and total height."""
    radius_mm = diameter_mm / 2
    curvature_radius_mm = (
        radius_mm * radius_mm + height_mm * height_mm
    ) / (2 * height_mm)
    sphere_center_z = height_mm - curvature_radius_mm
    sphere = part_module.makeSphere(
        curvature_radius_mm,
        freecad_module.Vector(center_x, center_y, sphere_center_z),
    )
    bounds = part_module.makeBox(
        diameter_mm,
        diameter_mm,
        height_mm,
        freecad_module.Vector(
            center_x - radius_mm,
            center_y - radius_mm,
            0,
        ),
    )
    return sphere.common(bounds)


def _valid_coordinate(
    coordinate: str,
    columns: int,
    rows: int,
) -> bool:
    return (
        isinstance(coordinate, str)
        and len(coordinate) >= 2
        and coordinate[0] in DEFAULT_BGA_COLUMN_LABELS[:columns]
        and coordinate[1:].isdigit()
        and 1 <= int(coordinate[1:]) <= rows
    )
