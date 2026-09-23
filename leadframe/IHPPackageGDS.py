"""Extract machine-readable lead geometry from an IHP package GDS."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import gdstk


@dataclass(frozen=True)
class PackageLead:
    pin: int
    centroid_um: Tuple[float, float]
    layer: int
    datatype: int


@dataclass(frozen=True)
class IHPPackageGeometry:
    package_cell: str
    lead_layer: int
    pin_label_layer: int
    leads: Tuple[PackageLead, ...]
    footprint_bbox_um: Tuple[float, float, float, float]
    source: str

    @property
    def pin_numbers(self) -> Tuple[int, ...]:
        return tuple(sorted(lead.pin for lead in self.leads))


@dataclass(frozen=True)
class BondMappingCheck:
    pin: int
    distance_um: float
    within_tolerance: bool


@dataclass(frozen=True)
class IHPPackageBondability:
    coordinate_offset_um: Tuple[float, float]
    tolerance_um: float
    checks: Tuple[BondMappingCheck, ...]

    @property
    def is_valid(self) -> bool:
        return bool(self.checks) and all(
            check.within_tolerance for check in self.checks
        )

    @property
    def mismatched_pins(self) -> Tuple[int, ...]:
        return tuple(
            check.pin for check in self.checks if not check.within_tolerance
        )


def validate_bond_mappings(
    geometry: IHPPackageGeometry,
    mappings: Iterable[object],
    tolerance_um: float = 50.0,
) -> IHPPackageBondability:
    """Validate report coordinates against package leads after layout translation."""
    leads = {lead.pin: lead.centroid_um for lead in geometry.leads}
    mapping_list = tuple(mappings)
    missing = sorted(mapping.pin for mapping in mapping_list if mapping.pin not in leads)
    if missing:
        raise ValueError(f"Package geometry has no leads for pins: {missing}")
    if not mapping_list:
        raise ValueError("No bond mappings supplied for package validation")

    offsets = [
        (
            mapping.package_xy_um[0] - leads[mapping.pin][0],
            mapping.package_xy_um[1] - leads[mapping.pin][1],
        )
        for mapping in mapping_list
    ]
    offset = (
        _median(item[0] for item in offsets),
        _median(item[1] for item in offsets),
    )
    checks = tuple(
        BondMappingCheck(
            pin=mapping.pin,
            distance_um=(
                (mapping.package_xy_um[0] - offset[0] - leads[mapping.pin][0]) ** 2
                + (mapping.package_xy_um[1] - offset[1] - leads[mapping.pin][1]) ** 2
            ) ** 0.5,
            within_tolerance=False,
        )
        for mapping in mapping_list
    )
    checks = tuple(
        BondMappingCheck(
            pin=check.pin,
            distance_um=check.distance_um,
            within_tolerance=check.distance_um <= tolerance_um,
        )
        for check in checks
    )
    return IHPPackageBondability(offset, tolerance_um, checks)


def _median(values: Iterable[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def extract_ihp_package_geometry(
    gds_path: str | Path,
    package_cell: str = "OP_QFN32",
    lead_layer: int = 210,
    pin_label_layer: int = 211,
) -> IHPPackageGeometry:
    """Extract numbered leads from the machine-readable package cell."""
    path = Path(gds_path)
    library = gdstk.read_gds(str(path))
    cell = next((item for item in library.cells if item.name == package_cell), None)
    if cell is None:
        raise ValueError(f"Package GDS cell not found: {package_cell}")

    labels = {
        int(label.text.strip()): label
        for label in cell.labels
        if label.layer == pin_label_layer and label.text.strip().isdigit()
    }
    polygons = [
        polygon for polygon in cell.polygons
        if polygon.layer == lead_layer
    ]
    if len(polygons) != len(labels):
        raise ValueError(
            f"Expected one lead per pin in {package_cell}; "
            f"found {len(polygons)} lead polygons and {len(labels)} pin labels"
        )

    centroids = []
    for polygon in polygons:
        points = polygon.points
        x = sum(point[0] for point in points) / len(points)
        y = sum(point[1] for point in points) / len(points)
        centroids.append((x, y, polygon.layer, polygon.datatype))

    leads = []
    for pin, label in labels.items():
        match = min(
            centroids,
            key=lambda item: abs(item[0] - label.origin[0]) + abs(item[1] - label.origin[1]),
        )
        leads.append(PackageLead(pin, (match[0], match[1]), match[2], match[3]))

    xs = [lead.centroid_um[0] for lead in leads]
    ys = [lead.centroid_um[1] for lead in leads]
    return IHPPackageGeometry(
        package_cell=package_cell,
        lead_layer=lead_layer,
        pin_label_layer=pin_label_layer,
        leads=tuple(sorted(leads, key=lambda lead: lead.pin)),
        footprint_bbox_um=(min(xs), min(ys), max(xs), max(ys)),
        source=str(path),
    )
